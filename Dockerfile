FROM python:3.10-buster

ENV DEBIAN_FRONTEND noninteractive

# Run the common library install
COPY . /setup/src/data_common/
RUN cd /setup/src/data_common/bin \
    && chmod +x packages_setup.bash \
    && ./packages_setup.bash \
    && export PATH="$HOME/.poetry/bin:$PATH" \
    && cd /setup/src/data_common && poetry install