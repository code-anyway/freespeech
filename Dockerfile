# FROM gcr.io/freespeech-343914/base:latest
FROM python:3.11-buster

# Install service-specific packages
RUN apt-get update -qqy && apt-get install -qqy \
    ffmpeg \
    aria2

COPY cert/lets-encrypt-r3.pem /usr/local/share/ca-certificates/lets-encrypt-r3.crt
RUN update-ca-certificates

RUN pip install uv


# Create folder structure, copy, and install package files
RUN mkdir /root/freespeech && \
    mkdir /root/freespeech/freespeech

WORKDIR "/root/freespeech"
ENV PYTHONPATH="/root/freespeech/"


RUN uv venv --python 3.11


COPY pyproject.toml /root/freespeech/
COPY LICENSE /root/freespeech/
COPY README.md /root/freespeech/

RUN uv sync

COPY freespeech /root/freespeech/freespeech/
RUN uv pip install -e .


COPY run.sh /root/freespeech/
COPY run_discord.sh /root/freespeech/
COPY run_web.sh /root/freespeech/
COPY run_discord_google.sh /root/freespeech/
COPY run_telegram_google.sh /root/freespeech/

VOLUME ["/root/.config", "/root/id/"]
WORKDIR "/root/freespeech"
