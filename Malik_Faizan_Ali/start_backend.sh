#!/usr/bin/env sh
cd "$(dirname "$0")/backend" && exec .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
