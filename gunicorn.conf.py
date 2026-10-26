"""Gunicorn settings for the Docker image (`gunicorn -c gunicorn.conf.py app:app`).

One worker process on purpose: the APScheduler reminder jobs run inside the
app process, so extra workers would each run their own copy.  Threads handle
concurrent requests instead, which is plenty for SQLite and a handful of users.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 1
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
# AI calls (Ollama / OpenAI / Anthropic) can take up to 90 s.
timeout = 120
graceful_timeout = 30
accesslog = None
errorlog = "-"
# Gunicorn 25+ opens a control socket in $HOME; not needed here.
control_socket_disable = True
