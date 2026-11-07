# ---- build: validate the catalogue, then compile it -------------------------
FROM python:3.12-alpine AS build
WORKDIR /src
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY tools/  ./tools/
COPY config/ ./config/
COPY site/   ./site/
# a broken config fails the image, not the browser
RUN python tools/build.py

# ---- run: static files, unprivileged, read-only -----------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/site/ /usr/share/nginx/html/
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
