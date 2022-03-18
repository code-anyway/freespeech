FROM docker:20.10.12 as static-docker-source
FROM python:3.9-buster

# Install Google Cloud SDK
# Source: https://github.com/GoogleCloudPlatform/cloud-sdk-docker/blob/master/debian_slim/Dockerfile
ARG CLOUD_SDK_VERSION=377.0.0
ENV CLOUD_SDK_VERSION=$CLOUD_SDK_VERSION
ENV PATH "$PATH:/opt/google-cloud-sdk/bin/"
COPY --from=static-docker-source /usr/local/bin/docker /usr/local/bin/docker
RUN groupadd -r -g 1000 cloudsdk && \
    useradd -r -u 1000 -m -s /bin/bash -g cloudsdk cloudsdk
ARG INSTALL_COMPONENTS
RUN mkdir -p /usr/share/man/man1/
RUN apt-get update -qqy && apt-get install -qqy \
        curl \
        gcc \
        apt-transport-https \
        lsb-release \
        openssh-client \
        git \
        gnupg && \
    pip3 install -U crcmod && \
    export CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)" && \
    echo "deb https://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" > /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update && apt-get install -y google-cloud-sdk=${CLOUD_SDK_VERSION}-0 $INSTALL_COMPONENTS && \
    gcloud config set core/disable_usage_reporting true && \
    gcloud config set component_manager/disable_update_check true && \
    gcloud config set metrics/environment github_docker_image && \
    gcloud --version

RUN git config --system credential.'https://source.developers.google.com'.helper gcloud.sh

# Install service-specific packages
RUN apt-get install -qqy \
    ffmpeg \
    jq

# Python virtualenv: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --upgrade \
    pip \
    wheel

# Create folder structure, copy, and install package files
RUN mkdir /root/freespeech && \
    mkdir /root/freespeech/freespeech && \
    mkdir /root/freespeech/workflows
COPY freespeech /root/freespeech/freespeech
COPY workflows  /root/freespeech/workflows  
COPY setup.py /root/freespeech/
COPY README.md /root/freespeech/
RUN cd /root/freespeech && pip install .

VOLUME ["/root/.config", "/root/id/", "/root/data/"]