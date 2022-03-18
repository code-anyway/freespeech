#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

OUTPUT_DIR=$2
PROJECT_ID=$3
BUCKET=$4

gcloud auth activate-service-account --key-file $GOOGLE_APPLICATION_CREDENTIALS

IFS=$'\n'
for line in $(cat "$1" | tr -d '\r')
do
    echo "$line"
    IFS=',' read -r URL TRANSCRIPT LANGUAGE VOICE <<< "$line"
    FILE_PREFIX="$(echo -n "$URL" | sha256sum | sed 's/  -//')"
    UNIQUE_OUTPUT_DIR="$OUTPUT_DIR/$FILE_PREFIX"

    mkdir -p $UNIQUE_OUTPUT_DIR
    $SCRIPT_DIR/ingest_synthesize_mix.sh "$URL" "$TRANSCRIPT" "$LANGUAGE" "$VOICE" "$UNIQUE_OUTPUT_DIR"
    mv "$UNIQUE_OUTPUT_DIR/voiceover.mp4" "$UNIQUE_OUTPUT_DIR/voiceover-$LANGUAGE-$VOICE.mp4"
    gsutil cp "$UNIQUE_OUTPUT_DIR/voiceover-$LANGUAGE-$VOICE.mp4" "gs://$BUCKET/$FILE_PREFIX-$LANGUAGE-$VOICE.mp4"
    freespeech meta --url=$URL --output="$UNIQUE_OUTPUT_DIR/meta.json"
    mv "$UNIQUE_OUTPUT_DIR/meta.json" "$UNIQUE_OUTPUT_DIR/meta-$LANGUAGE.json"
    gsutil cp "$UNIQUE_OUTPUT_DIR/meta-$LANGUAGE.json" "gs://$BUCKET/$FILE_PREFIX-$LANGUAGE.json"
done