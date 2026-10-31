# One container with the three apps (patient /, doctor /doctor/, admin /admin/) behind nginx.
# Used by Render (see render.yaml and docs/DEPLOY_RENDER.md); works on any Docker host.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PERDIA_DATA_DIR=/var/data
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 perdia
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Code is read-only for the app user; runtime data lives in PERDIA_DATA_DIR (the persistent disk).
RUN chmod +x deploy/render-start.sh && mkdir -p /var/data && chown perdia:perdia /var/data
EXPOSE 10000
CMD ["/bin/bash", "deploy/render-start.sh"]
