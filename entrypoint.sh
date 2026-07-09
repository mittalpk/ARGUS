#!/usr/bin/env bash
set -e

# If the first argument is a command that exists on PATH (e.g. uvicorn, pytest, bash), exec it.
# Otherwise, default to executing the reproducibility submission script.
if [ -n "$1" ] && command -v "$1" >/dev/null 2>&1; then
    exec "$@"
else
    exec python /app/prepare_submission.py "$@"
fi
