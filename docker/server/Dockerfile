FROM python:slim-buster

COPY source /source/

RUN /bin/bash -c 'pip install numpy'

WORKDIR /source
ENTRYPOINT ["python", "./server.py"]