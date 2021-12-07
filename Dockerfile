FROM python:3.8-buster

ENV DEBIAN_FRONTEND noninteractive

COPY packages_setup.bash /
RUN chmod +x /packages_setup.bash && /packages_setup.bash

COPY base_requirements.txt /
RUN pip install -r /base_requirements.txt