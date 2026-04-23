#!/bin/bash
rsync -rlptDv --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='.pytest_cache/' \
  --exclude='data/' \
  --exclude='tags' \
  --exclude='cscope.*' \
  --no-perms \
  --omit-dir-times \
  -e "ssh -p 10022" \
  ../invest-site/ Ryan@119.77.172.195:/volume1/docker/invest-site/
