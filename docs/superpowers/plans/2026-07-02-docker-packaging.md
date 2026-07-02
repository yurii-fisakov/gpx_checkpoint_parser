# Docker Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the Flask web application and Gunicorn web server into a non-root Docker image runnable through Docker Compose or direct Docker commands.

**Architecture:** A Python 3.12 slim image installs the web dependencies, copies only runtime files, and runs Gunicorn on container port 8000. Compose exposes the service only on host loopback, mounts `checkpoints.json` read-only, makes the root filesystem read-only, and provides ephemeral `/tmp` storage for request uploads.

**Tech Stack:** Docker, Docker Compose, Python 3.12, Flask 3.1.x, Gunicorn 23.x

## Global Constraints

- Preserve the existing native CLI and web startup paths.
- Publish the service as `127.0.0.1:5000`.
- Run Gunicorn inside the container on `0.0.0.0:8000` with a 120-second timeout.
- Run the image as a non-root numeric user.
- Include a fallback `checkpoints.json` and mount the host file read-only in normal usage.
- Keep uploaded GPX files request-scoped under an ephemeral `/tmp`.
- Do not persist reports or GPX uploads.
- Do not stage or alter the existing permission-bit changes or GPX sample replacement.

---

### Task 1: Build the production container image

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: image `gpx-checkpoint-report:local`
- Produces: Gunicorn service on container port `8000`
- Produces: image health check for `http://127.0.0.1:8000/`

- [ ] **Step 1: Verify the image build is RED**

Run:

```bash
docker build -t gpx-checkpoint-report:local .
```

Expected: failure because `Dockerfile` does not exist.

- [ ] **Step 2: Add the Gunicorn dependency**

Change `requirements.txt` to:

```text
Flask>=3.1,<3.2
gunicorn>=23,<24
```

Gunicorn 23 is intentionally bounded below 24 because it supports the
project's Python 3.9 native runtime as well as the Python 3.12 container.

- [ ] **Step 3: Create the Docker build context exclusions**

Create `.dockerignore`:

```text
.git
.gitignore
.DS_Store
__pycache__/
*.py[cod]
.pytest_cache/
docs/
test_*.py
*.gpx
report.csv
```

- [ ] **Step 4: Create the non-root runtime image**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install \
    --no-cache-dir \
    --disable-pip-version-check \
    -r requirements.txt

COPY --chown=10001:10001 gpx_checkpoint_report.py web_app.py checkpoints.json ./
COPY --chown=10001:10001 templates ./templates

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2).close()"]

CMD ["gunicorn", "--bind=0.0.0.0:8000", "--timeout=120", "--access-logfile=-", "--error-logfile=-", "web_app:app"]
```

- [ ] **Step 5: Build and inspect the image**

Run:

```bash
docker build -t gpx-checkpoint-report:local .
test "$(docker image inspect \
  --format '{{.Config.User}}' \
  gpx-checkpoint-report:local)" = "10001:10001"
docker image inspect \
  --format '{{json .Config.Healthcheck.Test}}' \
  gpx-checkpoint-report:local
```

Expected: the build succeeds, the user assertion exits zero, and the health
check contains the Python standard-library request.

- [ ] **Step 6: Commit the image definition without user changes**

```bash
git add Dockerfile .dockerignore requirements.txt
git commit -m "FB_DEVOPS-0_fisakov package web service image"
```

### Task 2: Add hardened Docker Compose startup

**Files:**
- Create: `compose.yaml`

**Interfaces:**
- Consumes: local `Dockerfile`
- Consumes: `./checkpoints.json`
- Produces: Compose service `web`
- Produces: host endpoint `http://127.0.0.1:5000`

- [ ] **Step 1: Verify Compose configuration is RED**

Run:

```bash
docker compose config
```

Expected: failure because no Compose file exists.

- [ ] **Step 2: Create the Compose service**

Create `compose.yaml`:

```yaml
services:
  web:
    build:
      context: .
    ports:
      - "127.0.0.1:5000:8000"
    volumes:
      - type: bind
        source: ./checkpoints.json
        target: /app/checkpoints.json
        read_only: true
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777
```

- [ ] **Step 3: Validate the resolved Compose model**

Run:

```bash
bash -o pipefail -c 'rtk docker compose config 2>&1 | tail -c 4000'
```

Expected: exit zero with one `web` service, loopback port `5000`, read-only
configuration mount, read-only root filesystem, and `/tmp` tmpfs.

- [ ] **Step 4: Start the service and verify health and hardening**

Run:

```bash
docker compose up --build --detach
container_id="$(docker compose ps -q web)"
health=""
for attempt in $(seq 1 30); do
  health="$(docker inspect --format '{{.State.Health.Status}}' "$container_id")"
  test "$health" = "healthy" && break
  sleep 1
done
test "$health" = "healthy"
test "$(docker inspect \
  --format '{{.HostConfig.ReadonlyRootfs}}' \
  "$container_id")" = "true"
test "$(docker inspect \
  --format '{{range .Mounts}}{{if eq .Destination "/app/checkpoints.json"}}{{.RW}}{{end}}{{end}}' \
  "$container_id")" = "false"
curl --fail --silent --show-error http://127.0.0.1:5000/ >/dev/null
```

Expected: every assertion exits zero.

- [ ] **Step 5: Verify a real multipart report request**

Run:

```bash
configuration="$(jq -c '.timezone = "Europe/Chisinau"' checkpoints.json)"
response="$(curl --fail-with-body --silent --show-error \
  -F "configuration=$configuration" \
  -F "gpx_files=@Oleg Sat.gpx" \
  http://127.0.0.1:5000/api/report)"
test "$(jq '.rows | length' <<<"$response")" = "1"
test "$(jq -r '.rows[0][0]' <<<"$response")" = "Oleg Sat"
```

Expected: both assertions exit zero.

- [ ] **Step 6: Stop the service and commit Compose**

Run:

```bash
docker compose down
git add compose.yaml
git commit -m "FB_DEVOPS-0_fisakov add Docker Compose service"
```

### Task 3: Document Docker startup and run final verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: `docker compose up --build`
- Documents: direct `docker build` and hardened `docker run`
- Preserves: native Python startup instructions

- [ ] **Step 1: Verify Docker documentation is RED**

Run:

```bash
rtk rg -n -m 10 \
  'docker compose up --build|docker build -t gpx-checkpoint-report' \
  README.md
```

Expected: no matches and a non-zero exit status.

- [ ] **Step 2: Add Docker as the primary web startup path**

Insert before the existing native web instructions:

````markdown
## Docker web application

Start the service with Docker Compose:

```bash
docker compose up --build
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Compose mounts the local
`checkpoints.json` read-only, so changes to the default checkpoints do not
require rebuilding the image. Stop the service with `docker compose down`.

To run without Compose:

```bash
docker build -t gpx-checkpoint-report .
docker run --rm \
  -p 127.0.0.1:5000:8000 \
  --read-only \
  --tmpfs /tmp \
  -v "$PWD/checkpoints.json:/app/checkpoints.json:ro" \
  gpx-checkpoint-report
```

The container stores uploaded GPX files only in temporary memory and does not
persist reports.
````

Rename the existing `## Local web application` heading to:

```markdown
## Native web application
```

- [ ] **Step 3: Verify documentation and Python regressions**

Run:

```bash
rtk rg -n -m 10 \
  'docker compose up --build|docker build -t gpx-checkpoint-report|Native web application' \
  README.md
bash -o pipefail -c 'rtk python3 -m unittest \
  test_gpx_checkpoint_report test_web_app 2>&1 | tail -c 4000'
git diff --check
```

Expected: all three documentation phrases are found, all 15 Python tests pass,
and the diff check exits zero.

- [ ] **Step 4: Rebuild and smoke-test the documented Compose path**

Run:

```bash
docker compose up --build --detach
container_id="$(docker compose ps -q web)"
health=""
for attempt in $(seq 1 30); do
  health="$(docker inspect --format '{{.State.Health.Status}}' "$container_id")"
  test "$health" = "healthy" && break
  sleep 1
done
test "$health" = "healthy"
curl --fail --silent --show-error http://127.0.0.1:5000/ >/dev/null
docker compose down
```

Expected: the rebuilt service becomes healthy, the page responds successfully,
and Compose removes the service container.

- [ ] **Step 5: Commit documentation without user changes**

```bash
git add README.md
git commit -m "FB_DEVOPS-0_fisakov document Docker startup"
```
