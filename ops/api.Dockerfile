FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-app.lock.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-app.lock.txt
RUN useradd --uid 1000 --create-home launch && mkdir /data && chown launch:launch /data
COPY --chown=launch:launch packages packages
COPY --chown=launch:launch services services
COPY --chown=launch:launch implementation implementation
COPY --chown=launch:launch ops ops
COPY --chown=launch:launch migrations migrations
COPY --chown=launch:launch spec/contracts spec/contracts
COPY --chown=launch:launch data/gazetteer data/gazetteer
COPY --chown=launch:launch data/registry data/registry
COPY --chown=launch:launch data/profiles data/profiles
COPY --chown=launch:launch evidence/build/dependency-manifest.json evidence/build/dependency-manifest.json
COPY alembic.ini .
USER launch
