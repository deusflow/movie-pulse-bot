# Movie Pulse Bot

A Telegram bot that compiles daily movie and TV trends from TMDB and Reddit, summarizes sentiment with Gemini, and posts a formatted update.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env` and fill in your API keys.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run locally

```bash
python main.py
```

## Smoke test (no network)

```bash
python scripts/smoke_test.py
```

