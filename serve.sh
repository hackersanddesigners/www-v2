#!/bin/bash

# PORT can be changed to be another value
PORT=5020

set -e

if [[ $# == 1 ]]; then
    DIR=$1

    echo "serving $DIR at http:localhost:$PORT"
    # python -m http.server --directory $DIR --bind 127.0.0.1 $PORT
    python dev-server.py ./$DIR $PORT

else
    echo "serving current directory $(pwd) at http:localhost:$PORT"
    echo "you can specify a directory to use for the HTTP server"
    echo "by doing ./serve.sh <path/to/directory>"
    echo " "

    python -m http.server --bind 127.0.0.1 $PORT

fi
