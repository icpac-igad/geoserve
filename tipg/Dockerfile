# tipg — dynamic OGC vector tiles + features over the pgstac DB.
#
# tipg auto-discovers tables, views, and functions in configured schemas
# and exposes them as OGC API – Tiles / Features collections.
#
# We extend the upstream image with:
#   - sql/  custom server-side functions tipg should expose as collections
#           (mounted into the pgstac DB at boot — kept here so they live
#            next to the service that consumes them).
#   - config.toml  tipg configuration (schema allowlist, function exposure).

FROM ghcr.io/developmentseed/tipg:1.0.1

COPY config.toml /opt/geoserve_tipg/config.toml

ENV TIPG_CUSTOM_SQL_DIRECTORY=/opt/geoserve_tipg/sql \
    TIPG_DEBUG=False
COPY sql/ /opt/geoserve_tipg/sql/

# Cloud Run + local dev: PORT env wins, defaults to 8083 for compose.
# WEB_CONCURRENCY defaults to 4 workers; Cloud Run can override.
ENV PORT=8083 \
    WEB_CONCURRENCY=4
EXPOSE 8083
CMD ["sh", "-c", "exec uvicorn tipg.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY}"]
