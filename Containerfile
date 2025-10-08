FROM --platform=linux/arm64 docker.io/python:3.11-slim


COPY .  /app

RUN pip3 install -r /app/requirements.txt

WORKDIR /app

ENTRYPOINT [ "python3", "/app/index.py" ]
