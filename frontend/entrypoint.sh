#!/bin/sh
yarn build
if [ $? = "1" ]; then
    echo "yarn build failed"
    exit 1
fi
node server.js