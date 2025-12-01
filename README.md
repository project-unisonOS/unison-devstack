# Unison Devstack

[![E2E Smoke](https://github.com/project-unisonos/unison-devstack/actions/workflows/e2e-smoke.yml/badge.svg)](https://github.com/project-unisonos/unison-devstack/actions/workflows/e2e-smoke.yml)

Docker Compose setup for core Unison services.

Using the meta repo: if you cloned `unison-workspace`, you can run devstack from the root with `./scripts/up.sh` and `./scripts/smoke.sh` (those delegate to this compose file).

## Status
Core DX stack (active) — canonical Docker Compose for local development and testing.

See `../unison-docs/dev/developer-guide.md` for the end-to-end workflow.

## Testing
With Docker running:
```bash
docker compose up -d --build
python scripts/e2e_smoke.py
```

Health checks (devstack defaults):
```bash
curl http://localhost:8080/health   # orchestrator
curl http://localhost:8081/health   # context
curl http://localhost:8082/health   # storage
curl http://localhost:8083/health   # policy
```

Payments service (optional):
```bash
docker compose --profile payments up -d payments
# set UNISON_PAYMENTS_HOST/PORT envs in orchestrator if you want proxying to the standalone service
curl http://localhost:8089/health
```

## Build speed tip: shared unison-common wheel

A prebuilt `unison-common` wheel is used by all Python services. Build/pull it once before composing:
```bash
# Build locally (from repo root)
docker build -f unison-common/Dockerfile.wheel -t ghcr.io/project-unisonos/unison-common-wheel:latest unison-common
# Or pull if published to GHCR
# docker pull ghcr.io/project-unisonos/unison-common-wheel:latest

# Then build services (wheel is consumed in Dockerfiles)
docker compose build
```
