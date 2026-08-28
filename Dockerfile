FROM python:3.14-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV DEBIAN_FRONTEND noninteractive
ENV PATH="/setup/src/data_common/.venv/bin:${PATH}"

# Run the common package install
# splitting up allows layer caching and faster recreation
COPY /bin/packages_setup.bash pyproject.toml uv.lock /setup/src/data_common/
RUN cd /setup/src/data_common/ \
    && chmod +x packages_setup.bash \
    && ./packages_setup.bash \
    && uv sync --frozen --no-dev --extra dataset --no-install-project
