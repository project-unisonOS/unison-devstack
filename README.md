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
python scripts/test_multimodal.py
```

Health checks (devstack defaults):
```bash
curl http://localhost:8080/health   # orchestrator
curl http://localhost:8081/health   # context
curl http://localhost:8082/health   # storage
curl http://localhost:8083/health   # policy
curl http://localhost:8093/health   # comms (stub)
```

Payments service (optional):
```bash
docker compose --profile payments up -d payments
# set UNISON_PAYMENTS_HOST/PORT envs in orchestrator if you want proxying to the standalone service
curl http://localhost:8089/health
```

## Wake-Word & Always-On Profile

Devstack can exercise the wake-word and always-on companion path using local services only:

- Set wake-word defaults and Porcupine (optional) in your shell or `.env`:
  - `UNISON_WAKEWORD_DEFAULT=unison`
  - `PORCUPINE_ACCESS_KEY=<your-local-access-key>`
  - `PORCUPINE_KEYWORD_BASE64=<base64-keyword-bytes>`
- To enable an **always-on mic** profile for the experience renderer (where browser/host permissions allow), set:
  - `UNISON_ALWAYS_ON_MIC=true`
- Then bring up the stack and run multimodal smoke tests:
  - `docker compose up -d --build`
  - `python scripts/test_multimodal.py`

All wake-word detection, speech, and companion calls remain on the local machine by default; any cloud STT or model providers must be explicitly configured via the backing services and policy.

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

## Docs

Full docs at https://project-unisonos.github.io
