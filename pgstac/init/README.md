# pgstac/init/

SQL and shell scripts dropped here run on the **first boot** of a fresh
pgstac volume (Postgres's `/docker-entrypoint-initdb.d/` convention).
Names sort lexicographically — prefix with `NN-` to control ordering.

Suggested layout once we migrate:

```
00-extensions.sql        – CREATE EXTENSION postgis_topology, etc.
10-schemas.sql           – CREATE SCHEMA gha, etc.
20-scope-extents.sql     – gha.gha_extent, gha.whca_extent (the geoserve
                           equivalent of MapServer's gha_admin_extent_mask)
30-vector-functions.sql  – gha.admin_overlay() and other tipg-exposed funcs
50-stac-collections.sql  – pgstac.create_collection({...}) calls
```

These bootstrap inputs are the source of truth — re-creating the volume
should produce the same catalog. Items that flow in continuously (daily
WRF, weekly inundation) come from the jobs pipeline, not from here.
