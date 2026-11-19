# syntax=docker/dockerfile:1
# Build context: repository root (see docker-compose.yml).
ARG PYTHON_IMAGE=python:3.13-slim
ARG BUILD_IMAGE=debian:trixie-slim

# ---- Vampire: built from a pinned release tag and commit ------------------
FROM ${BUILD_IMAGE} AS vampire
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates cmake g++ git make \
 && rm -rf /var/lib/apt/lists/*
ARG VAMPIRE_TAG=v5.1.0
ARG VAMPIRE_COMMIT=7b2f410ec4430c26217a85db62cf0c4a97042f8d
RUN git clone --depth 1 --branch "${VAMPIRE_TAG}" https://github.com/vprover/vampire.git /src \
 && test "$(git -C /src rev-parse HEAD)" = "${VAMPIRE_COMMIT}"
# BUILD_SHARED_LIBS=OFF produces a fully static binary.
RUN cmake -S /src -B /build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
 && cmake --build /build --target vampire -j"$(nproc)" \
 && /build/vampire --version

# ---- Otter 3.3f: official source, verified by SHA-256 ----------------------
FROM ${BUILD_IMAGE} AS otter
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gcc libc6-dev make \
 && rm -rf /var/lib/apt/lists/*
# Same checksum as FreeBSD ports (misc/otter) and the Ubuntu archive.
ARG OTTER_SHA256=392c8c6557944eaf6958c199c365b43189beab836fb80c716569ea43af0dac9a
WORKDIR /build
RUN (curl -fsSL --retry 3 -o otter.tar.gz https://www.cs.unm.edu/~mccune/otter/otter-3.3f.tar.gz \
     || curl -fsSL --retry 3 -o otter.tar.gz http://archive.ubuntu.com/ubuntu/pool/universe/o/otter/otter_3.3f.orig.tar.gz) \
 && echo "${OTTER_SHA256}  otter.tar.gz" | sha256sum -c - \
 && tar xzf otter.tar.gz \
 && make -C otter-3.3f/source otter CC=gcc CFLAGS="-O2 -std=gnu89 -fcommon -fpermissive -w" \
 && printf 'set(auto).\nformula_list(usable).\np.\n-p.\nend_of_list.\n' > smoke.in \
 && (otter-3.3f/source/otter < smoke.in > smoke.out; test $? -eq 103)

# ---- Python dependencies (hash-verified) -----------------------------------
FROM ${PYTHON_IMAGE} AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --require-hashes -r /tmp/requirements.txt

# ---- runtime -----------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# SPASS 3.9 from Debian; util-linux provides prlimit for the prover sandbox.
RUN apt-get update \
 && apt-get install -y --no-install-recommends spass util-linux \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system app && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=vampire /build/vampire /usr/local/bin/vampire
COPY --from=otter /build/otter-3.3f/source/otter /usr/local/bin/otter
COPY --from=deps /opt/venv /opt/venv
WORKDIR /app
COPY backend/fvp/ fvp/
COPY backend/migrations/ migrations/
COPY backend/alembic.ini backend/gunicorn.conf.py backend/wsgi.py backend/cli.py backend/docker-entrypoint.sh ./
RUN vampire --version && command -v SPASS && command -v otter && command -v prlimit
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status != 200)"]
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# ---- test image: runs the full suite with all three provers (used in CI) ----
FROM runtime AS test
USER root
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install -r /tmp/requirements-dev.txt
COPY backend/tests/ tests/
COPY backend/pyproject.toml ./
USER app
ENTRYPOINT []
CMD ["python", "-m", "pytest", "-q"]
