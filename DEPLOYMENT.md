# Deployment Guide — NANDA Resolver

This guide covers running the NANDA Resolver locally, packaging it for
production, and deploying it to common hosts (Docker, a generic VPS, Render /
Railway / Fly.io, and Kubernetes).

The app is a single FastAPI process exposing one HTTP port. There is no
database — all state lives on disk under `data/` (index + signed AgentFacts +
keypairs) and is produced by `nanda seed`.

---

## 1. Prerequisites

- Python 3.10+
- `pip` and `venv`
- Git (to clone the repo)
- (Production) a reverse proxy (nginx / Caddy / cloud LB) for TLS termination

---

## 2. Local development

```bash
git clone https://github.com/gkganesh12/NANDA_Resolver.git
cd NANDA_Resolver

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Seed the directory with 9 sample agents
nanda seed

# Run the server (http://127.0.0.1:8000)
nanda serve
```

Verify in a second terminal:

```bash
nanda list
nanda resolve '@acme:support/billing-bot'
nanda discover --cap summarize-pdf
pytest -v
```

---

## 3. Configuration

Configuration lives in `nanda/config.py`. The two values you typically override
in production:

| Env var | Default | Purpose |
|---|---|---|
| `NANDA_DATA_DIR` | `./data` | Where `index.json`, `facts/`, and `keys/` are read from |
| `NANDA_BASE_URL` | `http://127.0.0.1:8000` | Public base URL the resolver uses to build links to the facts host |

Example:

```bash
export NANDA_DATA_DIR=/var/lib/nanda/data
export NANDA_BASE_URL=https://resolver.example.com
nanda serve --host 0.0.0.0 --port 8000
```

> **Important:** keep `data/keys/*.priv` out of any image or repo. In
> production, mount keys from a secret store (Docker secrets, k8s Secret,
> cloud KMS) rather than baking them in.

---

## 4. Production process command

Use `uvicorn` directly so you can tune workers and bind addresses:

```bash
uvicorn nanda.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --proxy-headers \
  --forwarded-allow-ips='*'
```

Behind nginx / Caddy, terminate TLS at the proxy and forward to port 8000.

### Minimal Caddyfile

```
resolver.example.com {
  reverse_proxy 127.0.0.1:8000
}
```

### Minimal nginx server block

```nginx
server {
  listen 443 ssl http2;
  server_name resolver.example.com;

  ssl_certificate     /etc/letsencrypt/live/resolver.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/resolver.example.com/privkey.pem;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

---

## 5. Docker

### Dockerfile

Create `Dockerfile` at the repo root:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NANDA_DATA_DIR=/data

WORKDIR /app

# Install deps first (better layer caching)
COPY pyproject.toml ./
COPY nanda ./nanda
RUN pip install --no-cache-dir .

# Optional: bake seeded data for demos; remove for production
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "nanda.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build and run

```bash
docker build -t nanda-resolver:latest .

# Seed once into a named volume
docker run --rm -v nanda-data:/data nanda-resolver:latest nanda seed

# Run
docker run -d --name nanda \
  -p 8000:8000 \
  -v nanda-data:/data \
  -e NANDA_BASE_URL=https://resolver.example.com \
  nanda-resolver:latest
```

### docker-compose.yml

```yaml
services:
  nanda:
    build: .
    ports:
      - "8000:8000"
    environment:
      NANDA_DATA_DIR: /data
      NANDA_BASE_URL: https://resolver.example.com
    volumes:
      - nanda-data:/data
    restart: unless-stopped

volumes:
  nanda-data:
```

---

## 6. Render / Railway / Fly.io (PaaS)

The app is one process and one port, so any PaaS works.

**Render / Railway** — use the Dockerfile above, or set:

- Build command: `pip install -e .`
- Start command: `uvicorn nanda.app:app --host 0.0.0.0 --port $PORT`
- Add a persistent disk mounted at `/data` and set `NANDA_DATA_DIR=/data`
- Run `nanda seed` once from a one-off shell to populate the disk

**Fly.io** — `fly launch` then deploy with the Dockerfile. Attach a volume:

```bash
fly volumes create nanda_data --size 1
```

In `fly.toml`:

```toml
[env]
  NANDA_DATA_DIR = "/data"

[[mounts]]
  source = "nanda_data"
  destination = "/data"

[http_service]
  internal_port = 8000
  force_https = true
```

---

## 7. Kubernetes (sketch)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: nanda }
spec:
  replicas: 2
  selector: { matchLabels: { app: nanda } }
  template:
    metadata: { labels: { app: nanda } }
    spec:
      containers:
        - name: nanda
          image: ghcr.io/<you>/nanda-resolver:latest
          ports: [{ containerPort: 8000 }]
          env:
            - { name: NANDA_DATA_DIR, value: /data }
            - { name: NANDA_BASE_URL, value: https://resolver.example.com }
          volumeMounts:
            - { name: data, mountPath: /data }
          readinessProbe:
            httpGet: { path: /index/list, port: 8000 }
          livenessProbe:
            httpGet: { path: /index/list, port: 8000 }
      volumes:
        - name: data
          persistentVolumeClaim: { claimName: nanda-data }
---
apiVersion: v1
kind: Service
metadata: { name: nanda }
spec:
  selector: { app: nanda }
  ports:
    - { port: 80, targetPort: 8000 }
```

For multi-replica deployments, the `data/` directory must be on a
ReadWriteMany volume (NFS / EFS / GCS Fuse) or moved to object storage. The
POC writes the index file in place during `nanda seed`, so plan a single
"seeder" job rather than re-seeding from every pod.

---

## 8. Hardening checklist

- [ ] Run as a non-root user inside the container (`USER nobody`).
- [ ] Mount `data/keys/` from a secret manager; never commit `.priv` files.
- [ ] Terminate TLS at the proxy / load balancer.
- [ ] Set sensible `--workers` for your CPU count (start with 2× cores).
- [ ] Add request logging at the proxy; the app logs to stdout.
- [ ] Add a health endpoint check on `GET /index/list` (cheap, no external calls).
- [ ] Restrict outbound network from the pod/host — the resolver only needs to
      reach itself for the facts URL in this POC, but a future deployment that
      points `factsUrl` at external hosts will need allowed egress.

---

## 9. CI/CD (GitHub Actions sketch)

`.github/workflows/test.yml`:

```yaml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e ".[dev]"
      - run: pytest -v
```

`.github/workflows/docker.yml` (build & push on tag):

```yaml
name: docker
on:
  push:
    tags: ['v*']
jobs:
  build:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.ref_name }}
```

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `nanda resolve` returns 404 | Handle not in `data/index.json` | Re-run `nanda seed` or verify the handle |
| `verification_failed: ...` | AgentFacts file tampered or key mismatch | Re-seed; check `data/keys/<id>.pub` matches `operatorPublicKey` in the index |
| `Upstream 502` from the resolver | `NANDA_BASE_URL` not reachable from inside the container | Point it at the externally reachable URL or `http://localhost:8000` for single-container runs |
| Browser UI loads but resolve fails on TLS site | Mixed-content: UI on HTTPS calling HTTP base URL | Set `NANDA_BASE_URL` to the public HTTPS URL |
| `pyld` canonicalization is slow on first call | Cold JIT/cache for URDNA2015 | Warm by hitting `/resolve/...` once at boot; subsequent calls are fast |

---

## 11. What is *not* covered here (matches PRD non-goals)

No federation, no live key rotation, no DID resolution, no agent invocation.
The TTL field exists in AgentFacts so a follow-on can add expiry/rotation
without re-architecting the deploy.
