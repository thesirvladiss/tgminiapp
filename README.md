PL Mini App
===========

Stack: FastAPI, Jinja2 templates, SQLite (SQLAlchemy), static assets.

Quickstart
----------

1) Create virtualenv and install deps

    python -m venv .venv
    .venv\\Scripts\\activate
    pip install -r requirements.txt

2) Run DB migrations (create tables) and seed demo data

    python -m tools.seed

3) Start dev server

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

4) Open in browser

    http://127.0.0.1:8000/

Routes
------

- / — Главная (карточки проектов)
- /podcasts — Список подкастов
- /podcasts/{id} — Детали подкаста и плеер
- /checkout — Выбор тарифа (заглушка)
- /success — Экран успеха

Static assets are served from /static
Environment example (.env)
--------------------------

Copy and adjust:

    SECRET_KEY=change-me
    ADMIN_LOGIN=admin
    ADMIN_PASSWORD=admin123
    UPLOADS_DIR=uploads
    BOT_TOKEN=
    WEBAPP_URL=http://127.0.0.1:8000/


Admin panel
-----------

- URL: /admin
- Default credentials: admin / admin123 (configure via .env: SECRET_KEY, ADMIN_LOGIN, ADMIN_PASSWORD)
- Features:
  - Dashboard with counters
  - Projects CRUD (главный экран Mini App)
  - Podcasts CRUD (обложка, preview/full mp3, дата, категории, публикация, «бесплатный»)
  - Transactions (read-only)
  - Users (read-only)

Uploads
-------

Files are uploaded to `uploads/`. Paths are stored as web paths like `/uploads/filename` and served by static file server.

Deployment
----------

1) Environment

Create `.env` with at least:

    SECRET_KEY=change-me
    ADMIN_LOGIN=admin
    ADMIN_PASSWORD=admin123

2) Run with uvicorn or gunicorn+uvicorn workers behind reverse proxy

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Nginx snippet (example):

    server {
      server_name example.com;
      location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
      }
    }

Telegram Mini App auth
----------------------

The app currently creates a guest user for local testing. For production Mini App, pass Telegram WebApp `initData` and extract `user.id` to persist `telegram_id`. For example, inject JS on frontend to send `initData` as a header or query param, or implement an auth endpoint that sets the session. Next step can be wiring official `initData` validation.

Telegram Bot
------------

Env variables (.env):

    BOT_TOKEN=123456:ABC...   # BotFather token
    WEBAPP_URL=https://example.com/

Install deps and run bot:

    pip install -r requirements.txt
    python tools/bot.py

In BotFather:
- Set a Web App button in your menu/command, or use the inline button provided by the bot `/start` message.


