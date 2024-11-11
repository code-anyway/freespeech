#!/usr/bin/env bash

echo $GOOGLE_APPLICATION_CREDENTIALS_BASE64 | base64 -d > $GOOGLE_APPLICATION_CREDENTIALS
source .venv/bin/activate

freespeech/run/telegram.py
