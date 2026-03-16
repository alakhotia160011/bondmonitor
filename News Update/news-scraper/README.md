# The Bond Monitor

LATAM sovereign bond news aggregator. Scrapes major local news outlets across 9 Latin American countries, summarizes them through Claude for bond-market relevance, and displays results on a static site.

**Live site:** [bondmonitor.vercel.app](https://bondmonitor.vercel.app)

## Architecture

```
GitHub Actions (daily cron) → Python scraper → data.json → Vercel (static site)
```

No backend server — GitHub Actions runs the scraper on a schedule, commits `data.json` to the repo, and Vercel auto-deploys the static frontend.

## Countries Tracked

| Category           | Country            | Rating |
|--------------------|--------------------|--------|
| Investment Grade   | Mexico             | BBB    |
| Investment Grade   | Chile              | A      |
| Investment Grade   | Brazil             | BB     |
| Investment Grade   | Panama             | BBB    |
| High Yield         | Ecuador            | B      |
| High Yield         | El Salvador        | B-     |
| High Yield         | Argentina          | C      |
| High Yield         | Dominican Republic | BB-    |
| High Yield         | Colombia           | BB+    |

## How It Works

1. **Scraper** (`News Update/news-scraper/scraper.py`) — Uses LangChain's `WebBaseLoader` to pull content from local news sites (El Universal, O Globo, El Universo, etc.), then sends it to Claude (Anthropic API) to extract a 2-line country summary and the top 5 bond-relevant headlines.

2. **GitHub Actions** (`.github/workflows/refresh.yml`) — Runs every weekday at 7:00 AM ET. Installs dependencies, runs the scraper, and commits `public/data.json` back to the repo.

3. **Frontend** (`News Update/news-scraper/public/index.html`) — Static HTML page styled in NYT editorial style (Playfair Display, Source Serif 4, Barlow Condensed). Fetches `data.json` on load and renders IG/HY sections with rating badges, summaries, and numbered headlines.

4. **Vercel** (`vercel.json`) — Serves `News Update/news-scraper/public/` as the static root.

## Setup

1. **Clone and push** to GitHub
2. **Add `ANTHROPIC_API_KEY`** as a GitHub repository secret (Settings > Secrets > Actions)
3. **Connect to Vercel** — import the repo, leave Root Directory empty, framework preset "Other"
4. **Run the workflow** — Go to Actions > Refresh Bond Monitor Data > Run workflow

## Local Development

```bash
cd "News Update/news-scraper"
pip install anthropic python-dotenv langchain-community beautifulsoup4
```

Create a `.env` file:

```
ANTHROPIC_API_KEY=your-key-here
```

Run the scraper:

```bash
python scraper.py
```

Open `public/index.html` in a browser to view results.
