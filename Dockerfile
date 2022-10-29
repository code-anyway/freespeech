FROM python:3.10-buster

# Install service-specific packages
RUN apt-get update -qqy && apt-get install -qqy \
    ffmpeg

COPY cert/lets-encrypt-r3.pem /usr/local/share/ca-certificates/lets-encrypt-r3.crt
RUN update-ca-certificates

# Python virtualenv: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --upgrade \
    pip \
    wheel

# Create folder structure, copy, and install package files
RUN mkdir /root/freespeech && \
    mkdir /root/freespeech/freespeech
COPY freespeech /root/freespeech/freespeech/
COPY setup.py /root/freespeech/
COPY README.md /root/freespeech/
RUN cd /root/freespeech && pip install .

VOLUME ["/root/.config", "/root/id/"]
WORKDIR "/root/freespeech"

ENTRYPOINT ["freespeech"]
