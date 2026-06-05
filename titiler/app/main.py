"""Custom titiler-pgstac entry point.

Re-exports the upstream FastAPI app so the default tile/feature routes
remain available, and mounts our extensions on top.

Routers:
  /scope-tile/<scope>/...   Server-side polygon mask. Static keys (whca,
                            gha, all, gadm) or dynamic (c-<iso3>,
                            a1-<id>, a2-<id>). The titiler equivalent
                            of MapServer's `MASK "gha_admin_extent_mask"`.

Add new routers below `app.include_router(...)`.
"""
from __future__ import annotations

from titiler.pgstac.main import app  # upstream ASGI app, kept as the entrypoint

from .scope_tile import router as scope_tile_router

app.include_router(scope_tile_router, prefix="/scope-tile", tags=["scope-tile"])
