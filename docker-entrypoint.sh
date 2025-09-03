#!/bin/bash

if [ "$APP_ENV" = "local" ]; then
  mkdir -p /s3/recordings || exit 1
  mkdir -p /s3/files || exit 1
  mkdir -p /s3/file-operations || exit 1
fi

pip install -e /app/grisera-api-dev-packages

# Start the application
uvicorn main:app --reload --host 0.0.0.0 --port 80
