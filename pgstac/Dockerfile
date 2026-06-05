# pgstac — Postgres + PostGIS + pgstac extension.
#
# We start from the upstream pgstac image (which already bundles a
# Postgres build with the pgstac SQL extension) and layer in project-
# specific SQL bootstrap that runs once on a fresh data volume:
#
#   1. PostGIS + topology extensions  (provided by the base image)
#   2. pgstac collections + functions (provided by the base image)
#   3. /docker-entrypoint-initdb.d/   ← our SQL (collections, scope
#                                       extent tables, vector funcs)
#
# Anything in `init/` ending in .sql or .sh is executed by the official
# Postgres entrypoint on first boot. Re-running with a populated volume
# is a no-op (the entrypoint only runs init scripts when PGDATA is empty).

FROM ghcr.io/stac-utils/pgstac:v0.9.6

COPY init/ /docker-entrypoint-initdb.d/
