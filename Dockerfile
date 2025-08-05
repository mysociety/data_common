FROM python:3.10-bookworm

ENV DEBIAN_FRONTEND noninteractive

# Run the common package install
# splitting up allows layer caching and faster recreation
COPY /bin/packages_setup.bash pyproject.toml poetry.lock /setup/src/data_commmon/
RUN cd /setup/src/data_commmon/ \
    && chmod +x packages_setup.bash \
    && ./packages_setup.bash \
    && mkdir --parents /setup/src/data_common/src/data_common \
    && touch /setup/src/data_common/src/data_common__init__.py \
    && export PATH="/root/.local/bin:$PATH" \
    && cd /setup/src/data_commmon/ && poetry install --no-root
