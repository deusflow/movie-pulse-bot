# Movie Pulse Bot 🎬

A robust Telegram bot that compiles daily movie and TV trends from TMDB, aggregates scores and reviews from across the web, summarizes sentiment using Google's Gemini AI, and posts a beautifully formatted update.

This project was built as part of the **"Deploy Or Die"** educational course, demonstrating the integration of multiple APIs, database usage, background task scheduling, and the application of Generative AI.

---

## 🏗 Architecture & Data Sources

The bot uses a modular architecture with distinct fetchers, an AI analyzer, a formatter, and a PostgreSQL database for state management.

### 1. Data Fetchers
- **TMDB (The Movie Database)**: Primary source for trending movies and TV shows. Provides titles, genres, posters, release years, overviews, and streaming availability (`get_watch_providers`).
- **OMDb API**: Retrieves critical scores including Rotten Tomatoes (%), Metascore, and IMDb ratings.
- **YouTube Data API v3**: Fetches top comments from movie and TV show trailers to gauge audience reaction.
- **Google News RSS**: Measures buzz by counting recent article mentions.
- **Movie Press RSS (Letterboxd/Roger Ebert/etc.)**: Aggregates coverage from major film publications.

### 2. AI Sentiment Analysis (Gemini)
Uses the official `google-genai` Python SDK to analyze the movie's overview, genres, and a compilation of user reviews (TMDB + YouTube).
Gemini synthesizes the data to generate:
- An overall sentiment score (0-100).
- One short, human-sounding **positive** comment.
- One short, human-sounding **negative** comment.
- A concise one-line summary of the audience's consensus.

### 3. Database (PostgreSQL / Neon)
Tracks publications to avoid duplicate posts in the same week.
- **`publications` table**: Stores `title`, `media_type`, `tmdb_id`, `score`, `posted_at`.
- **`genres` & `publication_genres` tables**: Normalizes genres to allow querying top movies by genre over time.

### 4. Formatter & Sender
Generates rich HTML-formatted Telegram messages (handling max length constraints) and posts them to configured channels. Supports **English** and **Ukrainian** localization.

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- A PostgreSQL database (e.g., [Neon.tech](https://neon.tech/) serverless Postgres)
- Telegram Bot Token
- API Keys: TMDB, Google Gemini, OMDb (optional), YouTube (optional)

### 2. Local Environment Setup

Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:
```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=@your_channel_handle
TMDB_API_KEY=your_tmdb_key
GEMINI_API_KEY=your_gemini_key

# Database
DATABASE_URL=postgresql://user:password@host/dbname

# Optional (Enhances data)
OMDB_API_KEY=your_omdb_key
YOUTUBE_API_KEY=your_youtube_key
```

---

## 🛠 Running the Bot

### Run locally (Manual trigger)
```bash
python main.py
```

### Testing (No DB or Telegram needed)

**Dry Run:** Simulates the entire pipeline, calls the APIs, and prints the formatted HTML posts to the console.
```bash
python scripts/dry_run.py
```

**Smoke Test:** Quickly verifies connectivity to all APIs.
```bash
python scripts/smoke_test.py
```

---

## 📦 Deployment (Upcoming)

This project is designed to be easily containerized and deployed.
Future iterations in the "Deploy Or Die" course will include:
- `Dockerfile` for containerization.
- `docker-compose.yml` for local testing with a Postgres container.
- CI/CD pipelines for automated testing and deployment.
