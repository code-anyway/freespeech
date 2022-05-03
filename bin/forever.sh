#!/usr/bin/env bash
until $1; do
    echo "Attempted to run $1 with return code $?"
    sleep 5
done