# tipg/sql/

`*.sql` files dropped here are loaded into the pgstac DB by tipg on
startup (via `TIPG_CUSTOM_SQL_DIRECTORY`). Each `CREATE FUNCTION` here
becomes a tipg-exposed collection at:

    /tipg/collections/<schema>.<function_name>/tiles/{tms}/{z}/{x}/{y}

Migrate the remaining pg_tileserv functions here as tipg-native ones —
they need to return `bytea` (MVT) and accept the standard `(z, x, y, ...)`
signature for tile functions, or return SETOF a GeoJSON-shaped row for
feature functions.

Targets queued for migration (task #31):
- `gha.admin_overlay(z, x, y, scope)` — progressive admin0/1/2 in one tile
- any others surfaced once we retire pg_tileserv
