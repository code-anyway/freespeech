#!/bin/bash
echo $GOOGLE_APPLICATION_CREDENTIALS_BASE64 | base64 -d -i - > /tmp/google-id.json && freespeech/telegram.py