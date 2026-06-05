# geoserve

Four services that turn a pgstac Postgres into raster tiles, vector tiles,
and a STAC catalog. Bundles its own Postgres so `docker compose up` works
from a fresh clone — but every service is env-driven, so embedding into
an existing stack is one `.env` override.

| Service    | Port | Serves                                            | Built on                                                                       |
|------------|------|---------------------------------------------------|--------------------------------------------------------------------------------|
| `pgdb`     | 5439 | Postgres 17 + postgis + pgstac (bundled)          | [stac-utils/pgstac](https://github.com/stac-utils/pgstac)                      |
| `stac-api` | 8081 | STAC catalog (OGC API – Features)                 | [stac-fastapi-pgstac](https://github.com/stac-utils/stac-fastapi)              |
| `titiler`  | 8082 | Raster tiles + `/scope-tile/<id>/...` mask router | [titiler-pgstac](https://github.com/stac-utils/titiler-pgstac)                 |
| `tipg`     | 8083 | Vector tiles (MVT) + features from PostGIS        | [tipg](https://github.com/developmentseed/tipg)                                |

## Run

```bash
git clone https://github.com/icpac-igad/geoserve.git
cd geoserve
cp .env.example .env
docker compose up -d --build
```

Endpoints:

- <http://127.0.0.1:8081/api.html> — STAC API
- <http://127.0.0.1:8082/api.html> — titiler
- <http://127.0.0.1:8083/api.html> — tipg

Empty catalog at first. Register a COG and serve a tile:

```bash
# 1. create a collection
curl -X POST http://127.0.0.1:8081/collections \
  -H 'content-type: application/json' \
  -d '{
    "id":"my-rasters","type":"Collection","stac_version":"1.0.0",
    "description":"my COGs","license":"proprietary",
    "extent":{"spatial":{"bbox":[[-180,-90,180,90]]},
              "temporal":{"interval":[[null,null]]}}
  }'

# 2. register a STAC item pointing at a COG
curl -X POST http://127.0.0.1:8081/collections/my-rasters/items \
  -H 'content-type: application/json' \
  -d '{
    "type":"Feature","id":"sample-1","collection":"my-rasters",
    "stac_version":"1.0.0",
    "geometry":{"type":"Polygon","coordinates":[[[0,0],[10,0],[10,10],[0,10],[0,0]]]},
    "bbox":[0,0,10,10],
    "properties":{"datetime":"2024-01-01T00:00:00Z"},
    "assets":{"data":{"href":"file:///cogs/sample.tif"}}
  }'

# 3. open a rendered tile
xdg-open 'http://127.0.0.1:8082/collections/my-rasters/items/sample-1/tiles/WebMercatorQuad/5/16/16@1x?assets=data'
```

## Env vars

| Var             | Default          | Purpose |
|-----------------|------------------|---------|
| `PG_HOST`       | `pgdb`           | pgstac Postgres hostname (container DNS) |
| `PG_PORT`       | `5432`           |  |
| `PG_USER`       | `postgres`       | pgstac role |
| `PG_PASSWORD`   | `pgstac_local`   |  |
| `PG_DBNAME`     | `pgstac`         | pgstac database name |
| `COGS_HOST_DIR` | `./data/cogs`    | Host path bind-mounted into titiler as `/cogs` |

See [`.env.example`](.env.example) for optional knobs (`TIPG_SCHEMAS`,
`TITILER_WORKERS`, container names, GDAL cache, etc.).

## Embedding in another project

If you already have a pgstac Postgres, set `PG_HOST` in your `.env` to
that container, then skip the bundled DB:

```bash
docker compose up -d titiler tipg stac-api
```

To pin geoserve at a specific commit inside another repo, use a git
submodule:

```bash
cd your-project
git submodule add https://github.com/icpac-igad/geoserve.git geoserve
```

Then either `include: geoserve/docker-compose.yml` in your compose, or
inline service blocks pointing at the build contexts:

```yaml
services:
  my_titiler:
    build: { context: ./geoserve/titiler }
    environment: { POSTGRES_HOST: pgdb, POSTGRES_USER: postgres, ... }
    volumes: ["./data/cogs:/cogs:ro"]
```

`git submodule update --remote` pulls newer geoserve versions when you
want them.

## Where do the COG bytes live?

Up to you — titiler resolves whatever URI you put in each STAC item's
`assets.<key>.href`:

| Href pattern              | titiler reads via |
|---------------------------|-------------------|
| `file:///cogs/foo.tif`    | local mount (`COGS_HOST_DIR`) |
| `https://.../foo.tif`     | HTTP range reads (GDAL VSI) |
| `s3://bucket/foo.tif`     | S3 (configure AWS creds via env) |
| `gs://bucket/foo.tif`     | GCS (configure GCP creds via env) |

## Customizing

- **New raster route or colormap preset** → edit `titiler/app/main.py`.
- **New vector layer** → create a PostGIS view in a schema listed in
  `TIPG_SCHEMAS`; tipg auto-discovers it.
- **Pin to a newer upstream** → bump the `FROM` line in each service's
  Dockerfile.

## Layout

```
.
├── pgstac/      pgstac DB image (postgis + pgstac + init scripts)
├── stac-api/    stac-fastapi-pgstac
├── titiler/     titiler-pgstac + custom scope-tile mask router
├── tipg/        tipg + config.toml + sql/
├── data/        bind-mount target for COG storage
├── docker-compose.yml
└── .env.example
```

## License

MIT.
