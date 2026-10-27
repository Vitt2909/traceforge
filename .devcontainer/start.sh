#!/usr/bin/env bash
set -eu
if ! curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
  nohup python -m traco.web --host 0.0.0.0 >/tmp/traceforge-web.log 2>&1 &
fi
