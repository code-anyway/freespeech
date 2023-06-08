#!/bin/bash
freespeech/discord_bot.py &
python -m http.server 8080 --directory /dev/null > /dev/null