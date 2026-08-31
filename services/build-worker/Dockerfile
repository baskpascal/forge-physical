ARG TOOLCHAIN_IMAGE=coup-worker-toolchain:local
FROM python:3.13-slim AS backend-builder
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /src
COPY services/build-worker/pyproject.toml ./services/build-worker/pyproject.toml
RUN python -c "import pathlib, subprocess, sys, tomllib; metadata = tomllib.loads(pathlib.Path('services/build-worker/pyproject.toml').read_text()); subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', '--retries', '10', '--timeout', '60', *metadata['project']['dependencies']])"
COPY services/build-worker/src ./services/build-worker/src
RUN pip install --no-cache-dir --no-deps ./services/build-worker

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

FROM ${TOOLCHAIN_IMAGE} AS worker-runtime
LABEL org.opencontainers.image.description="Forge Physical prewarmed hardware worker runtime"
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:/opt/platformio-venv/bin:$PATH" \
    PLATFORMIO_CMD=/opt/platformio-venv/bin/platformio \
    PLATFORMIO_CORE_DIR=/opt/platformio \
    PLATFORMIO_LIBDEPS_DIR=/opt/platformio/libdeps \
    PLATFORMIO_BUILD_CACHE_DIR=/opt/platformio/build-cache \
    PORT=8080
COPY --from=backend-builder --chown=forge:forge /opt/venv /opt/venv
