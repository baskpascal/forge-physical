ARG TOOLCHAIN_IMAGE=coup-worker-toolchain:local
FROM python:3.13-slim AS backend-builder
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /src
COPY services/build-worker/pyproject.toml ./services/build-worker/pyproject.toml
COPY services/build-worker/src ./services/build-worker/src
RUN pip install --no-cache-dir --retries 10 --timeout 60 ./services/build-worker

FROM python:3.13-slim AS runtime-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080
COPY --from=backend-builder /opt/venv /opt/venv
WORKDIR /app
RUN useradd --create-home --uid 10001 forge && mkdir -p /app/artifacts /app/data && chown -R forge:forge /app
USER forge
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["sh", "-c", "uvicorn hardware_build.api:app --host 0.0.0.0 --port ${PORT}"]

FROM runtime-base AS api-runtime
LABEL org.opencontainers.image.description="Forge Physical lightweight API runtime"

FROM ${TOOLCHAIN_IMAGE} AS tooling-runtime

FROM runtime-base AS worker-runtime
LABEL org.opencontainers.image.description="Forge Physical prewarmed hardware worker runtime"
ENV PLATFORMIO_CMD=/opt/platformio-venv/bin/platformio \
    PLATFORMIO_LIBDEPS_DIR=/home/forge/.platformio/libdeps \
    PLATFORMIO_BUILD_CACHE_DIR=/home/forge/.platformio/build-cache
COPY --from=tooling-runtime /opt/platformio-venv /opt/platformio-venv
COPY --from=tooling-runtime /usr/local/bin/wokwi-cli /usr/local/bin/wokwi-cli
COPY --from=tooling-runtime --chown=forge:forge /root/.platformio /home/forge/.platformio
