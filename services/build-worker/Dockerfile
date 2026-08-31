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

FROM python:3.13-slim AS tooling-builder
ARG WOKWI_CLI_VERSION=0.26.1
ARG WOKWI_CLI_SHA256=72d968150babaf7532c47ab7741eb85a95a6c3e3cfef91ffbcfdb677fd38e811
RUN python -m venv /opt/platformio-venv
ENV PATH="/opt/platformio-venv/bin:$PATH" \
    PLATFORMIO_LIBDEPS_DIR=/root/.platformio/libdeps \
    PLATFORMIO_BUILD_CACHE_DIR=/root/.platformio/build-cache
RUN pip install --no-cache-dir --retries 10 --timeout 60 platformio==6.1.19
RUN platformio platform install "espressif32@6.12.0" \
    && platformio pkg install --global --library "adafruit/Adafruit GFX Library@^1.11.11" \
    && platformio pkg install --global --library "adafruit/Adafruit SSD1306@^2.5.13" \
    && platformio pkg install --global --library "adafruit/DHT sensor library@^1.4.6"
COPY services/build-worker/tooling/platformio-cache /tmp/platformio-cache
RUN platformio run --project-dir /tmp/platformio-cache \
    && rm -rf /tmp/platformio-cache
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl \
    && curl --fail --location --silent --show-error \
      "https://github.com/wokwi/wokwi-cli/releases/download/v${WOKWI_CLI_VERSION}/wokwi-cli-linuxstatic-x64" \
      --output /usr/local/bin/wokwi-cli \
    && echo "${WOKWI_CLI_SHA256}  /usr/local/bin/wokwi-cli" | sha256sum --check --strict \
    && chmod 0755 /usr/local/bin/wokwi-cli \
    && rm -rf /var/lib/apt/lists/*

FROM tooling-builder AS tooling-runtime
RUN rm -rf \
    /root/.platformio/lib \
    /root/.platformio/packages/toolchain-xtensa-esp32

FROM runtime-base AS worker-runtime
LABEL org.opencontainers.image.description="Forge Physical prewarmed hardware worker runtime"
ENV PLATFORMIO_CMD=/opt/platformio-venv/bin/platformio \
    PLATFORMIO_LIBDEPS_DIR=/home/forge/.platformio/libdeps \
    PLATFORMIO_BUILD_CACHE_DIR=/home/forge/.platformio/build-cache
COPY --from=tooling-runtime /opt/platformio-venv /opt/platformio-venv
COPY --from=tooling-runtime /usr/local/bin/wokwi-cli /usr/local/bin/wokwi-cli
COPY --from=tooling-runtime --chown=forge:forge /root/.platformio /home/forge/.platformio
