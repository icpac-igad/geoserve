"""FastAPI port of the WHCA scope-tile mask proxy.

Equivalent to the previous Django view at `geomanager-web/home/scope_tile.py`,
moved here so the mask lives in the same process that just rendered the
upstream tile — no HTTP round-trip back to CMS, no rasterio/shapely/PIL
imports inside the Django app.

URL pattern (path-based, query string passes through verbatim):

    /scope-tile/<scope>/collections/<col>/items/<item>/tiles/<tms>/{z}/{x}/{y}.png?<qs>

Mount this router on titiler-pgstac's app at prefix=/scope-tile and it
inherits titiler's existing tile factories via an internal HTTP self-call
on `localhost:8082`. nginx fronts the route with the existing `tile_cache`
zone so repeat requests don't re-enter Python.

Static scopes:
    whca → gha.whca_extent
    gha  → gha.gha_extent  (passthrough)
    all  → gha.gha_extent  (passthrough)
    gadm → gha.gadm_extent (passthrough)

Dynamic scopes:
    c-<iso3>   → gha.admin0 WHERE gid_0 = iso3
    a1-<id>    → gha.admin1 WHERE id = id
    a2-<id>    → gha.admin2 WHERE id = id
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re

import httpx
import numpy as np
import psycopg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry


LOG = logging.getLogger("geoserve_titiler.scope_tile")

# Self-call into this process's tile factory. Inside the container the
# loopback is free; no need to go back out through nginx.
INTERNAL_TITILER = "http://127.0.0.1:8082"

# Connection string to the DB that hosts the admin-boundary tables used
# for masking.  Defaults to the same pgstac DB; override only if the
# geometry tables live in a separate database.
GEOM_DB_URL = os.environ.get("GEOM_DB_URL", "")


SCOPE_TABLE = {
    "whca": "gha.whca_extent",
    "gha":  "gha.gha_extent",
    "all":  "gha.gha_extent",
    "gadm": "gha.gadm_extent",
}
PASSTHROUGH_SCOPES = {"gha", "all", "gadm"}

DYNAMIC_SCOPE_RE = re.compile(r"^(?P<kind>c|a1|a2)-(?P<id>[A-Za-z0-9._\-]+)$")
_DYNAMIC_LOOKUP = {
    "c":  ("gha.admin0", "gid_0"),
    "a1": ("gha.admin1", "id"),
    "a2": ("gha.admin2", "id"),
}

TILE_RE = re.compile(
    r"/tiles/[^/]+/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)"
    r"(?:@(?P<scale>\d+)x)?(?:\.(?P<fmt>[a-z]+))?$"
)

WM_HALF = 20037508.342789244

_geom_cache: dict[str, BaseGeometry] = {}
_geom_lock = asyncio.Lock()


async def _scope_geom_3857(scope: str) -> BaseGeometry | None:
    """Lazy-load the scope extent in EPSG:3857 (matches XYZ tile bounds).

    Double-checked-locking inside an asyncio.Lock so two concurrent requests
    for the same uncached scope don't both hit the DB.
    """
    cached = _geom_cache.get(scope)
    if cached is not None:
        return cached

    table = SCOPE_TABLE.get(scope)
    where_clause = ""
    where_params: tuple = ()

    if not table:
        m = DYNAMIC_SCOPE_RE.match(scope)
        if not m:
            return None
        kind = m.group("kind")
        ident = m.group("id")
        if kind not in _DYNAMIC_LOOKUP:
            return None
        table, key_col = _DYNAMIC_LOOKUP[kind]
        # Identifier is a SQL identifier from a hardcoded dict, ident is
        # parameterised. The {table} interpolation is safe because the
        # dict values are not caller-controlled.
        where_clause = f"WHERE {key_col} = %s"
        where_params = (ident,)

    async with _geom_lock:
        cached = _geom_cache.get(scope)
        if cached is not None:
            return cached
        if not GEOM_DB_URL:
            LOG.warning("scope-tile: GEOM_DB_URL not configured; cannot resolve scope=%s", scope)
            return None
        sql = (
            f"SELECT ST_AsGeoJSON(ST_Transform(ST_Union(geom), 3857)) "
            f"FROM {table} {where_clause}"
        )
        try:
            async with await psycopg.AsyncConnection.connect(GEOM_DB_URL) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, where_params)
                    row = await cur.fetchone()
        except psycopg.Error as exc:
            LOG.warning("scope-tile: DB error resolving scope=%s: %s", scope, exc)
            return None
        if not row or not row[0]:
            return None
        geom = shapely_shape(json.loads(row[0]))
        _geom_cache[scope] = geom
        return geom


def _tile_bounds_3857(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    n = 1 << z
    res = (2.0 * WM_HALF) / n
    minx = -WM_HALF + x * res
    maxx = -WM_HALF + (x + 1) * res
    maxy = WM_HALF - y * res
    miny = WM_HALF - (y + 1) * res
    return (minx, miny, maxx, maxy)


def _build_alpha_mask(geom_3857, bbox_3857, size) -> np.ndarray | None:
    """(H, W) uint8 mask: 255 inside scope, 0 outside. None if no overlap."""
    minx, miny, maxx, maxy = bbox_3857
    gminx, gminy, gmaxx, gmaxy = geom_3857.bounds
    if gmaxx < minx or gminx > maxx or gmaxy < miny or gminy > maxy:
        return None
    w, h = size
    transform = from_bounds(minx, miny, maxx, maxy, w, h)
    return rasterize(
        [(geom_3857, 255)],
        out_shape=(h, w),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    )


def _blank_png(size) -> bytes:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


router = APIRouter()


@router.get("/")
async def list_scopes():
    """Debug helper — enumerates known scope keys + cache state.

    Reached at /scope-tile/ (trailing slash, no path segments) — a literal
    that can't be confused with the catch-all `/<scope>/<titiler_path>`
    below, which requires at least two segments after the prefix.
    """
    return {
        "static": sorted(SCOPE_TABLE.keys()),
        "passthrough": sorted(PASSTHROUGH_SCOPES),
        "dynamic_prefixes": sorted(_DYNAMIC_LOOKUP.keys()),
        "cached": sorted(_geom_cache.keys()),
        "geom_db_configured": bool(GEOM_DB_URL),
    }


@router.get("/{scope}/{titiler_path:path}")
async def scope_tile(scope: str, titiler_path: str, request: Request):
    if scope not in SCOPE_TABLE and not DYNAMIC_SCOPE_RE.match(scope):
        raise HTTPException(status_code=400, detail=f"Unknown scope: {scope}")

    qs = request.url.query
    upstream = f"{INTERNAL_TITILER}/{titiler_path}"
    if qs:
        upstream = f"{upstream}?{qs}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(upstream)
    except httpx.HTTPError as exc:
        LOG.warning("scope-tile upstream failed: %s", exc)
        return Response(status_code=502)

    upstream_ct = r.headers.get("Content-Type", "image/png")
    body = r.content or b""

    if r.status_code != 200:
        # Out-of-bounds tiles return 404 from titiler with body containing
        # "outside bounds". Translate to a transparent 200 so the browser
        # console stays clean and the map renders a blank where there's no
        # data — same as the previous Django behaviour.
        looks_out_of_bounds = (r.status_code == 404 and b"outside bounds" in body)
        m = TILE_RE.search(titiler_path)
        if looks_out_of_bounds and m:
            scale = int(m.group("scale") or 1)
            size = (256 * scale, 256 * scale)
            return Response(
                content=_blank_png(size),
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=300"},
            )
        return Response(content=body, status_code=r.status_code, media_type=upstream_ct)

    # Passthrough scopes: 'all'/'gha'/'gadm' deliberately do not mask —
    # same bytes as /titiler/, routed through here so clients use one URL template.
    if scope in PASSTHROUGH_SCOPES:
        return Response(
            content=body,
            media_type=upstream_ct,
            headers={"Cache-Control": "public, max-age=300"},
        )

    m = TILE_RE.search(titiler_path)
    if not m:
        # Non-tile endpoint (preview, /statistics, /feature, …) — proxy as-is.
        return Response(content=body, media_type=upstream_ct)

    z, x, y = int(m.group("z")), int(m.group("x")), int(m.group("y"))
    scale = int(m.group("scale") or 1)
    size = (256 * scale, 256 * scale)

    geom = await _scope_geom_3857(scope)
    if geom is None or geom.is_empty:
        # Scope didn't resolve — fall back to the unmasked tile rather than 500.
        return Response(content=body, media_type=upstream_ct)

    bbox = _tile_bounds_3857(z, x, y)
    mask = _build_alpha_mask(geom, bbox, size)

    if mask is None:
        # Scope polygon doesn't intersect this tile at all → fully transparent.
        return Response(
            content=_blank_png(size),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300"},
        )

    img = Image.open(io.BytesIO(body)).convert("RGBA")
    if img.size != size:
        img = img.resize(size)
    arr = np.array(img)
    arr[..., 3] = (arr[..., 3].astype(np.uint16) * mask // 255).astype(np.uint8)

    out_img = Image.fromarray(arr, "RGBA")
    buf = io.BytesIO()
    out_img.save(buf, format="PNG", optimize=True)
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )
