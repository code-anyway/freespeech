#!/usr/bin/env sh

# Example Usage:
#
# ingest_synthesize_mix \
    # https://youtu.be/wl26_J700sA \
    # https://docs.google.com/document/d/1atdjoPsrk8KVPyspZpDyIqoC_n0usVNWmKGnMYXnNLA/edit \
    # ru-RU \
    # ru-RU-Wavenet-D
#
# ingest_synthesize_mix \
#     https://youtu.be/wl26_J700sA \
#     https://docs.google.com/document/d/1atdjoPsrk8KVPyspZpDyIqoC_n0usVNWmKGnMYXnNLA/edit \
#     en-EN \
#     en-EN-Wavenet-I


freespeech ingest --url=$1 --output_dir=output/
freespeech synthesize \
    --text_file=$2 \
    --output=output/speech-$3-$4.wav \
    --language=$3 \
    --voice=$4 \
    --duration=$(freespeech probe output/video.mp4 | jq -r .format.duration)
freespeech mix \
    --video=output/video.mp4 \
    --output=output/video-$3-$4.mp4 \
    --weights=1,10 -- \
    output/audio.webm output/speech-$3-$4.wav
