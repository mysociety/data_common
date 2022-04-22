FROM python:3.10-buster

ENV DEBIAN_FRONTEND noninteractive

# Run the common package install
# splitting up allows layer caching and faster recreation
COPY /bin/packages_setup.bash pyproject.toml poetry.lock /setup/
RUN cd /setup/ \
    && chmod +x packages_setup.bash \
    && ./packages_setup.bash \
    && mkdir --parents /setup/src/data_common && touch /setup/src/data_common/__init__.py \
    && export PATH="$HOME/.poetry/bin:$PATH" \
    && cd /setup/ && poetry install 