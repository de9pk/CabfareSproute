# Cab Fare Comparator — Uber vs Ola vs Rapido

> Automated fare comparison for Jaipur routes. Selenium scrapes Uber, Ola, and Rapido; Streamlit shows live comparison and trends. History lives in SQLite (CSV export kept as a backup).

**Educational / local-only.** Scraping may violate platform Terms of Service. Use your own accounts. Do not deploy this dashboard publicly.

---

## Features

| Feature | Description |
|---|---|
| Live fare scraping | Selenium fetches Uber, Ola, and Rapido estimates |
| Demo mode | Mock fares for UI work without logging in |
| Cheapest highlight | Shows which platform is cheapest and estimated savings |
| Cookie login | Log in once, reuse the session |
| SQLite history | Routes, scrape runs, and quotes with error messages |
| Dedup | Skips identical successful quotes within a short window |
| Retries | Transient scrape failures retry with backoff |
| Scheduler | `python scheduler.py` collects fares on an interval |
| Analytics | Hour-of-day, day-of-week, and cheapest-platform win rate |
| Logs | Failures go to `logs/app.log` instead of failing silently |

---

## Architecture

```
app.py                 Streamlit UI (compare / history / analytics / login)
scheduler.py           APScheduler worker (runs without the dashboard)
jobs/fetch_fares.py    Shared scrape pipeline: sequential + retries + log
scrapers/              Uber / Ola / Rapido (Selenium + BeautifulSoup)
utils/storage.py       SQLite schema (routes, scrape_runs, fare_quotes)
utils/analytics.py     Trend aggregations
logs/app.log           Rotating application log
data/fares.db          Local database (created on first run)
```

Dashboard fetches and the scheduler both call `fetch_and_log()`, so storage and retry behaviour stay consistent.

SQLite is used instead of MySQL so the project runs locally with no database server. The table layout matches the earlier MySQL plan (`routes` → `scrape_runs` → `fare_quotes`) if you migrate later.

---

## Project structure

```
cab_fare_comparator/
├── app.py
├── scheduler.py
├── requirements.txt
├── .env.example
├── jobs/
│   └── fetch_fares.py
├── scrapers/
│   ├── base_scraper.py
│   ├── uber_scraper.py
│   ├── ola_scraper.py
│   └── rapido_scraper.py
├── utils/
│   ├── storage.py
│   ├── analytics.py
│   ├── logging_config.py
│   ├── retry.py
│   ├── cookie_manager.py
│   ├── location_helper.py
│   └── data_logger.py          # compatibility wrapper around storage
├── data/                       # fares.db + CSV export (gitignored)
└── logs/                       # app.log + debug screenshots
```

---

## Setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Install Google Chrome. ChromeDriver is installed by `webdriver-manager`.

```bash
cp .env.example .env
# Edit .env with phone numbers if you use credential login
```

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**. On Windows you can also use `start.bat`.

---

## Scheduled collection

The dashboard only auto-refreshes while it is open. For unattended collection:

```bash
python scheduler.py --once
python scheduler.py
```

Defaults (overridable in `.env` or CLI):

- Interval: `SCHEDULE_INTERVAL_MINUTES` (15)
- Route: `DEFAULT_PICKUP` → `DEFAULT_DESTINATION`
- Headless: `HEADLESS`

```bash
python scheduler.py --pickup "JECRC University, Vidhani, Jaipur" --destination "Jaipur International Airport, Sanganer" --interval 10 --headed
```

On Windows you can point Task Scheduler at `python scheduler.py --once` if you prefer OS scheduling over APScheduler.

---

## Login

1. Dashboard → **Login Manager**, or `python cli_login.py uber`
2. Complete OTP in the browser
3. Cookies are saved under `cookies/`
4. Later runs can use headless mode

Rapido only saves cookies after a real login check (phone/OTP prompt gone).

---

## Environment variables

See `.env.example`. Important keys:

| Variable | Meaning |
|---|---|
| `HEADLESS` | Browser window hidden |
| `REFRESH_INTERVAL_MINUTES` | Dashboard auto-refresh |
| `SCRAPE_RETRIES` | Attempts per platform (login failures are not retried) |
| `DEDUP_WINDOW_MINUTES` | Skip duplicate successful quotes |
| `SCHEDULE_INTERVAL_MINUTES` | Background job interval |

---

## When scrapers break

Sites change HTML often. Then:

```bash
python debug_selectors.py --platform uber
python debug_selectors.py --elements --platform ola
```

Update selectors in `scrapers/*_scraper.py`. Screenshots land in `logs/`.

---

## Tech stack

Python 3.10+, Selenium 4, BeautifulSoup4, Streamlit, SQLite, APScheduler, pandas, Plotly, python-dotenv, geopy, webdriver-manager.

---

**Built by Deepak** — B.Tech CSE semester / portfolio project.
