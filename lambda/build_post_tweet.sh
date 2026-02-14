#!/bin/bash
# Build post_tweet.zip with tweepy for Lambda. Run from lambda/ before terraform apply.
set -e
cd "$(dirname "$0")"
rm -rf build post_tweet.zip
pip3 install -r requirements.txt -t build --quiet
cp post_tweet.py build/
cd build && zip -r ../post_tweet.zip . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*" && cd ..
rm -rf build
echo "Built post_tweet.zip"
