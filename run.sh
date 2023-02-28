#!/bin/bash
echo $GOOGLE_APPLICATION_CREDENTIALS_BASE64 | base64 -d - > /tmp/google-id.json && freespeech/telegram.py