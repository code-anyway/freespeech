#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

OUTPUT_DIR=$2
PROJECT_ID=$3
BUCKET=$4

IFS=$'\n'
for line in $(cat "$1")
do
    echo "$line"
    IFS=',' read -r url transcript language voice <<< "$line"
    SCRIPT_DIR/ingest_synthesize_mix.sh "$url" "$transcript" "$language" "$voice" "$OUTPUT_DIR" "$PROJECT_ID" "$BUCKET"
done
