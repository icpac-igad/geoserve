# stac-api — OGC API – Features over the pgstac catalog.
#
# Mostly a passthrough on top of stac-fastapi-pgstac. The `app/` slot is
# here so we can add validators, hooks, or product-specific filters
# without forking upstream when the time comes.

FROM ghcr.io/stac-utils/stac-fastapi-pgstac:5.0.2

COPY app/ /opt/geoserve_stac/

ENV PYTHONPATH=/opt:${PYTHONPATH}

# Cloud Run + local dev: PORT env wins, defaults to 8081 for compose.
ENV PORT=8081 \
    WEB_CONCURRENCY=2
EXPOSE 8081
CMD ["sh", "-c", "exec uvicorn stac_fastapi.pgstac.app:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY}"]
