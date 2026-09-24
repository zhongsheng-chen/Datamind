# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=24.21.0
ARG NODE_BASE_DIGEST=sha256:5cbc7caba8c2c0f0bca675d1b61b9f2857e1cf1853c6164ee9dd409501a936e7
ARG PYTHON_VERSION=3.12
ARG PYTHON_BASE_DIGEST=sha256:1aaa65a85fda306ffb8b910824d4e93bdce61e212c7e87168123ea3073b41a1a

FROM node:${NODE_VERSION}-bookworm-slim@${NODE_BASE_DIGEST} AS console-builder

WORKDIR /build

COPY package.json package-lock.json vite.config.mjs ./
RUN npm ci

COPY datamind/console/static ./datamind/console/static
RUN npm run build:console


FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST} AS package-builder

ARG DATAMIND_BUILD_COMMIT
ARG DATAMIND_BUILD_DATE
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY build_support ./build_support
COPY datamind ./datamind
COPY --from=console-builder \
    /build/datamind/console/dist \
    /build/datamind/console/dist

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --index-url "${PIP_INDEX_URL}" \
        "build>=1.2.0" "setuptools>=77.0.3" wheel \
    && DATAMIND_BUILD_COMMIT="${DATAMIND_BUILD_COMMIT}" \
       DATAMIND_BUILD_DATE="${DATAMIND_BUILD_DATE}" \
        python -m build --wheel --no-isolation --outdir /dist


FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST} AS runtime

ARG PYTHON_VERSION
ARG PYTHON_BASE_DIGEST
ARG DATAMIND_BUILD_COMMIT
ARG DATAMIND_BUILD_DATE
ARG DATAMIND_TITLE
ARG DATAMIND_DESCRIPTION
ARG DATAMIND_VERSION
ARG DATAMIND_AUTHORS
ARG DATAMIND_VENDOR
ARG DATAMIND_LICENSES
ARG DATAMIND_SOURCE_URL
ARG DATAMIND_PROJECT_URL
ARG DATAMIND_DOCUMENTATION_URL
ARG DATAMIND_PYTHON_EXTRA=full
ARG PIP_INDEX_URL=https://pypi.org/simple

LABEL org.opencontainers.image.title="${DATAMIND_TITLE}" \
      org.opencontainers.image.description="${DATAMIND_DESCRIPTION}" \
      org.opencontainers.image.version="${DATAMIND_VERSION}" \
      org.opencontainers.image.revision="${DATAMIND_BUILD_COMMIT}" \
      org.opencontainers.image.created="${DATAMIND_BUILD_DATE}" \
      org.opencontainers.image.source="${DATAMIND_SOURCE_URL}" \
      org.opencontainers.image.authors="${DATAMIND_AUTHORS}" \
      org.opencontainers.image.vendor="${DATAMIND_VENDOR}" \
      org.opencontainers.image.documentation="${DATAMIND_DOCUMENTATION_URL}" \
      org.opencontainers.image.url="${DATAMIND_PROJECT_URL}" \
      org.opencontainers.image.licenses="${DATAMIND_LICENSES}" \
      org.opencontainers.image.base.name="docker.io/library/python:${PYTHON_VERSION}-slim-bookworm" \
      org.opencontainers.image.base.digest="${PYTHON_BASE_DIGEST}" \
      io.github.zhongsheng-chen.datamind.framework="${DATAMIND_PYTHON_EXTRA}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    BENTOML_HOME=/home/datamind/bentoml

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 datamind \
    && useradd \
        --uid 10001 \
        --gid datamind \
        --create-home \
        --shell /usr/sbin/nologin \
        datamind \
    && mkdir --parents "${BENTOML_HOME}" \
    && chown --recursive datamind:datamind /home/datamind

COPY --from=package-builder /dist/ /tmp/dist/

RUN --mount=type=cache,target=/root/.cache/pip \
    wheel_path="$(find /tmp/dist -maxdepth 1 -type f \
        -name '*.whl' -print -quit)" \
    && test -n "${wheel_path}" \
    && python -m pip install --index-url "${PIP_INDEX_URL}" \
        "${wheel_path}[${DATAMIND_PYTHON_EXTRA}]" \
    && rm --recursive --force /tmp/dist

WORKDIR /home/datamind
USER datamind

EXPOSE 8700 8701

CMD ["python", "-m", "bentoml", "serve", "datamind.runtime.server.service:DatamindRuntimeService", "--host", "0.0.0.0", "--port", "8700"]
