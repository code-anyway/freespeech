FROM gcr.io/freespeech-343914/base:latest

# Create folder structure, copy, and install package files
RUN mkdir /root/freespeech && \
    mkdir /root/freespeech/freespeech
COPY freespeech /root/freespeech/freespeech/
COPY setup.py /root/freespeech/
COPY README.md /root/freespeech/
RUN cd /root/freespeech && pip install .

VOLUME ["/root/.config", "/root/id/"]
WORKDIR "/root/freespeech"

CMD freespeech start transcript