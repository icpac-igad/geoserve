# titiler — dynamic raster tiles + /feature clip from the pgstac catalog.
#
# The upstream titiler-pgstac image ships a working FastAPI app at
# `titiler.pgstac.main:app`. We mount our extension package next to it
# and launch our own app entry point so we can register additional
# routes (scope-tile mask, country-clip, project-specific tilesets…)
# without forking the upstream codebase.
#
# Custom code goes in `app/`. The upstream `titiler.pgstac.main:app`
# is composed with our routers in `app/main.py`, which becomes the
# uvicorn entry point.

FROM ghcr.io/stac-utils/titiler-pgstac:1.7.2

# Extra runtime deps for the scope-tile mask router. The base image ships
# shapely + rasterio + numpy + httpx + psycopg, but Pillow is not bundled.
RUN pip install --no-cache-dir --no-deps Pillow==11.0.0

# Mount the custom package one level above PYTHONPATH so Python sees
# `geoserve_titiler` as an importable package (its __init__.py lives at
# /opt/geoserve_titiler/__init__.py, the parent /opt must be on sys.path).
COPY app/ /opt/geoserve_titiler/

ENV PYTHONPATH=/opt:${PYTHONPATH}

# Cloud Run + local dev: PORT env wins, defaults to 8082 for compose.
# WEB_CONCURRENCY defaults to 4 workers (1.5 GB mem limit ≈ 375 MB/worker).
ENV PORT=8082 \
    WEB_CONCURRENCY=4
EXPOSE 8082
CMD ["sh", "-c", "exec uvicorn geoserve_titiler.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY}"]
