#!/bin/bash
# Azure App Service (Linux, Python) runtime runs this as the container's
# startup command. Oryx (Azure's build system) installs requirements.txt
# automatically, then runs whatever's configured as the "Startup Command"
# in Configuration > General settings -- set it to:
#
#   bash startup.sh
#
# gunicorn is the process manager App Service's health checks and restart
# logic expect; uvicorn's worker class is what actually runs the ASGI app
# under it. --timeout is raised well above gunicorn's 30s default because
# a cold LLM call (Gemini/Groq/GitHub Models fallback chain, /extract/file
# or /extract/url) can legitimately take longer than that. App Service sets
# $PORT itself (usually 8000) -- falling back to 8000 keeps this runnable
# unchanged in a plain container too.
exec gunicorn --bind=0.0.0.0:${PORT:-8000} \
  --timeout 120 \
  --workers 2 \
  app.main:app \
  -k uvicorn.workers.UvicornWorker
