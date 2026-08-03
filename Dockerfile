# Run TriHumanizer outside Vercel: a small, non-root image.
#
# The hosted deployment is serverless, so this file covers what Vercel does not:
# a VPS, a homelab box, or a reviewer who wants the whole app in one command.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so editing code does not invalidate the pip layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

COPY . .

# The app only reads its own files and writes data/, so it never runs as root.
# A fixed uid keeps volume permissions predictable across hosts.
RUN useradd --create-home --uid 10001 trihumanizer \
 && mkdir -p /app/data \
 && chown -R trihumanizer:trihumanizer /app
USER trihumanizer

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]
