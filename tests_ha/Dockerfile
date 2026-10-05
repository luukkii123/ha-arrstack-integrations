FROM python:3.14-slim-bookworm AS tests
ARG HA_VERSION=2026.9.2
ARG TEST_PLUGIN=0.13.365
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libffi-dev libssl-dev libpcap0.8 libturbojpeg0 php-cli && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir homeassistant==${HA_VERSION} pytest-homeassistant-custom-component==${TEST_PLUGIN} && pip check
WORKDIR /repo

