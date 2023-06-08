#!/bin/bash
freespeech/discord.py &
python -m http.server 8080 --directory /dev/null