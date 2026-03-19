import json
import os
import re
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader

# ── CDS Spreads (10-year, basis points) ──
# Source: Damodaran/NYU Stern, Dec 31 2025
# Countries with "NA" use rating-implied default spreads instead
CDS_SPREADS = {
    "MEX": 166, "CHL": 87,  "BRA": 235, "PAN": 222,
    "PER": 126, "URY": 77,  "ECU": 567, "SLV": 340,
    "ARG": 1800, "DOM": 280, "COL": 334, "PRY": 250,
    "BOL": 600, "VEN": 929, "CRI": 175, "GTM": 200,
    "HND": 350,
}


# ── Country metadata ──
# To add a new country: add an entry here + a news source in SOURCES below.
COUNTRIES = [
    # Investment Grade
    {"country": "Mexico",             "code": "MEX", "iso_a3": "MEX", "rating": "BBB", "category": "IG", "flag": "\U0001f1f2\U0001f1fd", "capital": {"name": "Mexico City",  "lat": 19.43,  "lng": -99.13}},
    {"country": "Chile",              "code": "CHL", "iso_a3": "CHL", "rating": "A",   "category": "IG", "flag": "\U0001f1e8\U0001f1f1", "capital": {"name": "Santiago",      "lat": -33.45, "lng": -70.67}},
    {"country": "Brazil",             "code": "BRA", "iso_a3": "BRA", "rating": "BB",  "category": "IG", "flag": "\U0001f1e7\U0001f1f7", "capital": {"name": "Bras\u00edlia", "lat": -15.79, "lng": -47.88}},
    {"country": "Panama",             "code": "PAN", "iso_a3": "PAN", "rating": "BBB", "category": "IG", "flag": "\U0001f1f5\U0001f1e6", "capital": {"name": "Panama City",  "lat": 8.98,   "lng": -79.52}},
    {"country": "Peru",               "code": "PER", "iso_a3": "PER", "rating": "BBB", "category": "IG", "flag": "\U0001f1f5\U0001f1ea", "capital": {"name": "Lima",          "lat": -12.05, "lng": -77.04}},
    {"country": "Uruguay",            "code": "URY", "iso_a3": "URY", "rating": "BBB", "category": "IG", "flag": "\U0001f1fa\U0001f1fe", "capital": {"name": "Montevideo",    "lat": -34.88, "lng": -56.16}},
    # High Yield
    {"country": "Ecuador",            "code": "ECU", "iso_a3": "ECU", "rating": "B",   "category": "HY", "flag": "\U0001f1ea\U0001f1e8", "capital": {"name": "Quito",         "lat": -0.18,  "lng": -78.47}},
    {"country": "El Salvador",        "code": "SLV", "iso_a3": "SLV", "rating": "B-",  "category": "HY", "flag": "\U0001f1f8\U0001f1fb", "capital": {"name": "San Salvador",  "lat": 13.69,  "lng": -89.19}},
    {"country": "Argentina",          "code": "ARG", "iso_a3": "ARG", "rating": "C",   "category": "HY", "flag": "\U0001f1e6\U0001f1f7", "capital": {"name": "Buenos Aires",  "lat": -34.60, "lng": -58.38}},
    {"country": "Dominican Republic", "code": "DOM", "iso_a3": "DOM", "rating": "BB-", "category": "HY", "flag": "\U0001f1e9\U0001f1f4", "capital": {"name": "Santo Domingo", "lat": 18.47,  "lng": -69.90}},
    {"country": "Colombia",           "code": "COL", "iso_a3": "COL", "rating": "BB+", "category": "HY", "flag": "\U0001f1e8\U0001f1f4", "capital": {"name": "Bogot\u00e1",   "lat": 4.71,   "lng": -74.07}},
    {"country": "Paraguay",           "code": "PRY", "iso_a3": "PRY", "rating": "BB",  "category": "HY", "flag": "\U0001f1f5\U0001f1fe", "capital": {"name": "Asunci\u00f3n", "lat": -25.26, "lng": -57.58}},
    {"country": "Bolivia",            "code": "BOL", "iso_a3": "BOL", "rating": "B-",  "category": "HY", "flag": "\U0001f1e7\U0001f1f4", "capital": {"name": "La Paz",        "lat": -16.50, "lng": -68.15}},
    {"country": "Venezuela",          "code": "VEN", "iso_a3": "VEN", "rating": "D",   "category": "HY", "flag": "\U0001f1fb\U0001f1ea", "capital": {"name": "Caracas",       "lat": 10.48,  "lng": -66.90}},
    {"country": "Costa Rica",         "code": "CRI", "iso_a3": "CRI", "rating": "BB-", "category": "HY", "flag": "\U0001f1e8\U0001f1f7", "capital": {"name": "San Jos\u00e9", "lat": 9.93,   "lng": -84.08}},
    {"country": "Guatemala",          "code": "GTM", "iso_a3": "GTM", "rating": "BB-", "category": "HY", "flag": "\U0001f1ec\U0001f1f9", "capital": {"name": "Guatemala City","lat": 14.63,  "lng": -90.51}},
    {"country": "Honduras",           "code": "HND", "iso_a3": "HND", "rating": "BB-", "category": "HY", "flag": "\U0001f1ed\U0001f1f3", "capital": {"name": "Tegucigalpa",   "lat": 14.07,  "lng": -87.19}},
]

SOURCES = {
    "Mexico":             {"name": "El Universal",       "url": "https://www.eluniversal.com.mx/"},
    "Chile":              {"name": "El Pa\u00eds Chile",  "url": "https://elpais.com/noticias/chile/"},
    "Brazil":             {"name": "O Globo",            "url": "https://oglobo.globo.com/"},
    "Panama":             {"name": "La Prensa",          "url": "https://www.prensa.com/"},
    "Peru":               {"name": "El Comercio",        "url": "https://elcomercio.pe/"},
    "Uruguay":            {"name": "El Pa\u00eds Uruguay","url": "https://www.elpais.com.uy/"},
    "Ecuador":            {"name": "El Universo",        "url": "https://www.eluniverso.com/"},
    "El Salvador":        {"name": "El Salvador",        "url": "https://www.elsalvador.com/"},
    "Argentina":          {"name": "El Pa\u00eds Argentina","url": "https://elpais.com/noticias/argentina/"},
    "Dominican Republic": {"name": "Diario Libre",       "url": "https://www.diariolibre.com/?noredirect=1"},
    "Colombia":           {"name": "El Pa\u00eds Colombia","url": "https://elpais.com/noticias/colombia/"},
    "Paraguay":           {"name": "ABC Color",          "url": "https://www.abc.com.py/"},
    "Bolivia":            {"name": "El Deber",           "url": "https://eldeber.com.bo/"},
    "Venezuela":          {"name": "El Nacional",        "url": "https://www.elnacional.com/"},
    "Costa Rica":         {"name": "La Naci\u00f3n CR",  "url": "https://www.nacion.com/"},
    "Guatemala":          {"name": "Prensa Libre",       "url": "https://www.prensalibre.com/"},
    "Honduras":           {"name": "La Prensa HN",       "url": "https://www.laprensa.hn/"},
}


def parse_response(raw: str) -> dict:
    """Parse Claude's structured response into summary + headlines list."""
    m = re.search(r'\[SUMMARY START\](.*?)\[SUMMARY END\]', raw, re.DOTALL)
    summary = m.group(1).strip() if m else ""

    headlines = []
    hl_block = re.split(r'Top Bond-Relevant Headlines:', raw, flags=re.IGNORECASE)
    if len(hl_block) > 1:
        items = re.split(r'\n\s*\d+\.\s+', hl_block[1])
        for item in items:
            item = item.strip()
            if not item:
                continue
            first_line = item.split('\n')[0].strip().strip('<>').strip('*')
            if first_line:
                headlines.append(first_line)

    return {"summary": summary, "headlines": headlines[:5]}


def scrape_news():
    """Scrape and summarize bond-relevant news for all tracked countries."""
    load_dotenv(override=True)

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found")

    client = anthropic.Anthropic(api_key=api_key)

    # Try to load previous data for spread history
    out_dir = Path(__file__).resolve().parent / "public"
    out_path = out_dir / "data.json"
    prev_data = {}
    if out_path.exists():
        try:
            prev = json.loads(out_path.read_text())
            prev_data = {c["iso_a3"]: c for c in prev.get("countries", [])}
        except Exception:
            pass

    results = []

    for meta in COUNTRIES:
        name = meta["country"]
        source = SOURCES.get(name)
        if not source:
            continue

        print(f"\nProcessing {name}...")
        parsed = {"summary": "", "headlines": []}

        try:
            loader = WebBaseLoader(source["url"])
            docs = loader.load()
            content = docs[0].page_content if docs else None

            if content:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system="You are a financial analyst focused on sovereign bond markets. Extract the most relevant local news that could impact government bond prices. ALL output must be in English — translate any non-English headlines.",
                    messages=[{
                        "role": "user",
                        "content": f"""Analyze the following news content from {name} and provide:
1. A two-line English summary of the overall situation in the country
2. The top 5 most important headlines that could affect government bond prices

IMPORTANT:
- ALL headlines and the summary MUST be in English. Translate from the original language.
- Rank headlines in descending order of importance to bond markets (most impactful first)
- Focus on: fiscal policy, debt, central bank actions, GDP/inflation, political stability, trade
- Only include recent/current news, not old stories

Content:
{content[:15000]}

Format your response with exactly these markers:
[SUMMARY START]
[Your two-line English summary here]
[SUMMARY END]

Top Bond-Relevant Headlines:
1. <most impactful headline in English>
<impact explanation>

2. <second most impactful headline in English>
<impact explanation>

(continue for all 5 headlines)"""
                    }]
                )
                parsed = parse_response(response.content[0].text)
        except Exception as e:
            print(f"  Error: {e}")

        prev = prev_data.get(meta["iso_a3"], {})
        current_spread = CDS_SPREADS.get(meta["iso_a3"], 0)
        prev_spread = prev.get("spread", current_spread)
        spread_change = current_spread - prev_spread

        # Build spread history (rolling 30 days)
        spread_history = prev.get("spread_history", [])
        if current_spread:
            spread_history = (spread_history + [current_spread])[-30:]

        # Auto-assign signal based on spread level and change
        if current_spread >= 800:
            signal = "AVOID"
        elif spread_change <= -10:
            signal = "BUY"
        elif spread_change >= 10:
            signal = "WATCH"
        else:
            signal = prev.get("signal", "NEUTRAL")

        entry = {
            **meta,
            "spread": current_spread,
            "spread_change": spread_change,
            "signal": signal,
            "spread_history": spread_history,
            "summary": parsed["summary"],
            "headlines": parsed["headlines"],
            "source_name": source["name"],
            "source_url": source["url"],
        }
        results.append(entry)
        print(f"  Got {len(parsed['headlines'])} headlines")

    output = {
        "timestamp": datetime.now().isoformat(),
        "countries": results,
    }

    out_dir.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nWrote results to {out_path}")
    return output


if __name__ == "__main__":
    scrape_news()
