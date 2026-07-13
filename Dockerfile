FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install \
    --no-cache-dir \
    --disable-pip-version-check \
    -r requirements.txt

COPY --chown=10001:10001 gpx_checkpoint_report.py web_app.py checkpoints_300.json ./
COPY --chown=10001:10001 templates ./templates

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2).close()"]

CMD ["gunicorn", "--bind=0.0.0.0:8000", "--timeout=120", "--access-logfile=-", "--error-logfile=-", "web_app:app"]
