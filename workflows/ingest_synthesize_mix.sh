#!/usr/bin/env sh

# Example Usage:
#
# ingest_synthesize_mix \
#   https://youtu.be/wl26_J700sA \
#   https://docs.google.com/document/d/1atdjoPsrk8KVPyspZpDyIqoC_n0usVNWmKGnMYXnNLA/edit \
#   ru-RU \
#   ru-RU-Wavenet-D \
#   /root/data
#
# ingest_synthesize_mix \
#     https://youtu.be/wl26_J700sA \
#     https://docs.google.com/document/d/1atdjoPsrk8KVPyspZpDyIqoC_n0usVNWmKGnMYXnNLA/edit \
#     en-EN \
#     en-EN-Wavenet-I \
#     /root/data

freespeech ingest --url=$1 --output_dir=$5
freespeech synthesize \
    --text_file=$2 \
    --output=$5/speech-$3-$4.wav \
    --language=$3 \
    --voice=$4 \
    --duration=$(freespeech probe $5/video.mp4 | jq -r .format.duration)
freespeech mix \
    --video=$5/video.mp4 \
    --output=$5/video-$3-$4.mp4 \
    --weights=1,10 -- \
    $5/audio.webm $5/speech-$3-$4.wav
