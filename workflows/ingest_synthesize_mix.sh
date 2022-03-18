#!/usr/bin/env bash

# Example Usage:
#
# ./workflows/ingest_synthesize_mix.sh \
#     https://youtu.be/wl26_J700sA \
#     https://docs.google.com/document/d/1EUUIfHvzXGwK8zllv1JE8jZkZm1S9dBJHK7U-DHPGNg/edit \
#     en-EN \
#     en-EN-Wavenet-I \
#     $(pwd)/output \
#     freespeech-343914 \
#     freespeech-output

OUTPUT_DIR=$5

rm -rf $OUTPUT_DIR/*

freespeech ingest --url=$1 --output_dir=$OUTPUT_DIR
freespeech synthesize \
    --text_file=$2 \
    --output=$OUTPUT_DIR/speech-$3-$4.wav \
    --language=$3 \
    --voice=$4 \
    --duration=$(freespeech probe $OUTPUT_DIR/video.mp4 | jq -r .format.duration)
freespeech mix \
    --video=$OUTPUT_DIR/video.mp4 \
    --output=$OUTPUT_DIR/video-$3-$4.mp4 \
    --weights=1,10 -- \
    $OUTPUT_DIR/audio.webm $OUTPUT_DIR/speech-$3-$4.wav
gcloud auth activate-service-account --key-file $GOOGLE_APPLICATION_CREDENTIALS
FREESPEECH_SOURCE="$OUTPUT_DIR/video-$3-$4.mp4"
FREESPEECH_DESTINATION="gs://$7/$(echo "$1" | sha256sum | sed 's/  -//')-$3-$4.mp4"
echo "Destination: $FREESPEECH_DESTINATION"
gsutil cp $FREESPEECH_SOURCE $FREESPEECH_DESTINATION