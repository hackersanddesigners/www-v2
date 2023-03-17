#!/bin/bash

gunicorn app.main:app \
         --workers 4 \
         --worker-class uvicorn.workers.UvicornWorker \
         --bind 127.0.0.1:5005
