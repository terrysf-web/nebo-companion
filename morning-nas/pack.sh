#!/usr/bin/env bash
# Build morning-nas.tar.gz — the folder as it should arrive on the NAS.
# Secrets, tokens and generated data are never packed.
set -euo pipefail
cd "$(dirname "$0")/.."
tar czf morning-nas.tar.gz \
  --exclude='.env' \
  --exclude='tokens/*' \
  --exclude='data' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.tar.gz' \
  morning-nas
echo "wrote $(pwd)/morning-nas.tar.gz"
tar tzf morning-nas.tar.gz | head -30
