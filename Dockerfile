FROM python:3.10-buster

ENV DEBIAN_FRONTEND noninteractive

COPY packages_setup.bash pyproject.toml /
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python - && chmod +x /packages_setup.bash && /packages_setup.bash