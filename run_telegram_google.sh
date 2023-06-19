#!/bin/bash
python -m http.server 8080 --directory /dev/null > /dev/null 2>&1 &
freespeech/telegram.py