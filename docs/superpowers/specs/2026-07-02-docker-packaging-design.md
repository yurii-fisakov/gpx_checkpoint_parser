# Docker Packaging Design

## Goal

Package the GPX checkpoint web application and its web server into a Docker
image. Support equivalent startup through Docker Compose and direct Docker
commands while keeping the service accessible only from the local computer by
default.

## Scope

The change will add:

- a production WSGI server inside the image;
- a `Dockerfile`;
- a `.dockerignore`;
- a `compose.yaml`;
- a read-only runtime mount for `checkpoints.json`;
- container health checking; and
- Docker startup documentation.

Public deployment, TLS termination, authentication, orchestration platforms,
and persistent GPX or report storage are out of scope.

## Runtime Architecture

Use Gunicorn as the container's web server. It imports the existing
`web_app:app` Flask application, binds to `0.0.0.0:8000`, and uses a 120-second
request timeout so larger GPX uploads are not constrained by Gunicorn's
shorter default timeout.

The host publishes container port `8000` as `127.0.0.1:5000`. Binding the
published port to loopback keeps the local-first behavior and prevents Docker
from exposing the service on every host interface by default.

The image uses `python:3.12-slim` and runs the application as a non-root user.
Python bytecode generation is disabled and application output is unbuffered.
Gunicorn is the only new direct runtime dependency.

## Image Contents

The Docker build installs dependencies before copying application files so
dependency layers remain reusable when application code changes.

The runtime image contains only:

- `gpx_checkpoint_report.py`;
- `web_app.py`;
- `templates/`;
- `requirements.txt`; and
- a fallback `checkpoints.json`.

The fallback configuration makes the image runnable by itself. Normal Docker
and Compose instructions mount the host's `checkpoints.json` over that file as
read-only, allowing default checkpoints to change without rebuilding.

The `.dockerignore` excludes Git metadata, Python caches, tests, documentation,
GPX samples, generated reports, editor files, and other content not required
at runtime.

## Filesystem and Data Lifecycle

The application already stores uploads in request-scoped temporary
directories. Inside the container, these directories live under `/tmp` and
are removed after each request.

Docker Compose makes the container root filesystem read-only and supplies
`/tmp` as a temporary filesystem. The only bind mount is:

```text
./checkpoints.json:/app/checkpoints.json:ro
```

No uploaded GPX files, generated reports, or application state persist after
a request or container removal.

## Docker Compose

`compose.yaml` defines one service named `web` that:

- builds the local `Dockerfile`;
- publishes `127.0.0.1:5000:8000`;
- mounts `checkpoints.json` read-only;
- makes the root filesystem read-only;
- provides a temporary `/tmp`; and
- enables the image health check.

The primary startup command is:

```bash
docker compose up --build
```

No Compose version field is needed.

## Direct Docker Usage

The documented direct workflow will be equivalent:

```bash
docker build -t gpx-checkpoint-report .
docker run --rm \
  -p 127.0.0.1:5000:8000 \
  --read-only \
  --tmpfs /tmp \
  -v "$PWD/checkpoints.json:/app/checkpoints.json:ro" \
  gpx-checkpoint-report
```

The page remains available at `http://127.0.0.1:5000`.

## Health Check and Failure Behavior

The image health check requests `http://127.0.0.1:8000/` using Python's
standard library, avoiding an additional HTTP client package in the image.

A successful page response marks the container healthy. A missing, unreadable,
or invalid `checkpoints.json`, a failed Gunicorn process, or an unresponsive
application causes health checks to fail. Existing Flask error handling
continues to return a clear configuration error to HTTP clients.

## Dependency Management

Add Gunicorn to `requirements.txt` alongside Flask. Keep bounded compatible
version ranges rather than adding a separate container-only requirements file;
the web application has the same runtime dependencies inside and outside the
container.

The command-line report generator remains dependency-free when invoked
directly and does not import Flask or Gunicorn.

## Validation

Retain the existing Python test suite. Validate the container boundary with:

1. `docker compose config`;
2. a clean image build;
3. an assertion that the image's configured user is non-root;
4. container startup and health status;
5. an HTTP request to the page; and
6. a multipart report request with a repository GPX sample.

The smoke test must stop and remove its container after validation. If the
local Docker daemon is unavailable, report container validation as blocked
rather than treating static file inspection as equivalent.

## Documentation

Update `README.md` to make Docker Compose the primary web startup path and add
the equivalent direct Docker commands. Preserve the existing native Python
instructions for users who do not want Docker.
