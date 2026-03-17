import json
import os
import re
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader


# ── Country metadata ──
# To add a new country: add an entry here + a news source in SOURCES below.
COUNTRIES = [
    {"country": "Mexico",             "code": "MEX", "iso_a3": "MEX", "rating": "BBB", "category": "IG", "flag": "\U0001f1f2\U0001f1fd", "capital": {"name": "Mexico City",  "lat": 19.43,  "lng": -99.13}},
    {"country": "Chile",              "code": "CHL", "iso_a3": "CHL", "rating": "A",   "category": "IG", "flag": "\U0001f1e8\U0001f1f1", "capital": {"name": "Santiago",      "lat": -33.45, "lng": -70.67}},
    {"country": "Brazil",             "code": "BRA", "iso_a3": "BRA", "rating": "BB",  "category": "IG", "flag": "\U0001f1e7\U0001f1f7", "capital": {"name": "Bras\u00edlia", "lat": -15.79, "lng": -47.88}},
    {"country": "Panama",             "code": "PAN", "iso_a3": "PAN", "rating": "BBB", "category": "IG", "flag": "\U0001f1f5\U0001f1e6", "capital": {"name": "Panama City",  "lat": 8.98,   "lng": -79.52}},
    {"country": "Ecuador",            "code": "ECU", "iso_a3": "ECU", "rating": "B",   "category": "HY", "flag": "\U0001f1ea\U0001f1e8", "capital": {"name": "Quito",         "lat": -0.18,  "lng": -78.47}},
    {"country": "El Salvador",        "code": "SLV", "iso_a3": "SLV", "rating": "B-",  "category": "HY", "flag": "\U0001f1f8\U0001f1fb", "capital": {"name": "San Salvador",  "lat": 13.69,  "lng": -89.19}},
    {"country": "Argentina",          "code": "ARG", "iso_a3": "ARG", "rating": "C",   "category": "HY", "flag": "\U0001f1e6\U0001f1f7", "capital": {"name": "Buenos Aires",  "lat": -34.60, "lng": -58.38}},
    {"country": "Dominican Republic", "code": "DOM", "iso_a3": "DOM", "rating": "BB-", "category": "HY", "flag": "\U0001f1e9\U0001f1f4", "capital": {"name": "Santo Domingo", "lat": 18.47,  "lng": -69.90}},
    {"country": "Colombia",           "code": "COL", "iso_a3": "COL", "rating": "BB+", "category": "HY", "flag": "\U0001f1e8\U0001f1f4", "capital": {"name": "Bogot\u00e1",   "lat": 4.71,   "lng": -74.07}},
]

SOURCES = {
    "Mexico":             {"name": "El Universal",       "url": "https://www.eluniversal.com.mx/"},
    "Chile":              {"name": "La Tercera",         "url": "https://elpais.com/noticias/chile/"},
    "Brazil":             {"name": "O Globo",            "url": "https://oglobo.globo.com/"},
    "Panama":             {"name": "La Prensa",          "url": "https://www.prensa.com/"},
    "Ecuador":            {"name": "El Universo",        "url": "https://www.eluniverso.com/"},
    "El Salvador":        {"name": "El Salvador",        "url": "https://www.elsalvador.com/"},
    "Argentina":          {"name": "El Pais Argentina",  "url": "https://elpais.com/noticias/argentina/"},
    "Dominican Republic": {"name": "Diario Libre",       "url": "https://www.diariolibre.com/?noredirect=1"},
    "Colombia":           {"name": "El Pais Colombia",   "url": "https://elpais.com/noticias/colombia/"},
}


def parse_response(raw: str) -> dict:
    """Parse Claude's structured response into summary + headlines list."""
    # Extract summary
    m = re.search(r'\[SUMMARY START\](.*?)\[SUMMARY END\]', raw, re.DOTALL)
    summary = m.group(1).strip() if m else ""

    # Extract headlines (just the headline text, not the impact explanation)
    headlines = []
    hl_block = re.split(r'Top Bond-Relevant Headlines:', raw, flags=re.IGNORECASE)
    if len(hl_block) > 1:
        items = re.split(r'\n\s*\d+\.\s+', hl_block[1])
        for item in items:
            item = item.strip()
            if not item:
                continue
            # First line is the headline, rest is impact
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
            # Scrape
            loader = WebBaseLoader(source["url"])
            docs = loader.load()
            content = docs[0].page_content if docs else None

            if content:
                # Summarize via Claude
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system="You are a financial analyst focused on sovereign bond markets. Extract the most relevant local news that could impact government bond prices.",
                    messages=[{
                        "role": "user",
                        "content": f"""Analyze the following news content and provide:
1. A two-line summary of the overall situation in the country
2. The top 5 most important local headlines that could affect government bond prices, focusing on:
   - Fiscal policy and budget news
   - Political developments affecting economic policy
   - Monetary policy and central bank actions
   - Major economic indicators (GDP, inflation, debt)
   - Significant infrastructure or energy projects

Content:
{content[:15000]}

Format your response with exactly these markers:
[SUMMARY START]
[Your two-line summary here]
[SUMMARY END]

Top Bond-Relevant Headlines:
1. <headline>
<impact explanation>

2. <headline>
<impact explanation>

(continue for all 5 headlines)"""
                    }]
                )
                parsed = parse_response(response.content[0].text)
        except Exception as e:
            print(f"  Error: {e}")

        # Carry forward spread history from previous run, or use defaults
        prev = prev_data.get(meta["iso_a3"], {})
        spread = prev.get("spread", 0)
        spread_history = prev.get("spread_history", [])

        entry = {
            **meta,
            "spread": spread,
            "spread_change": prev.get("spread_change", 0),
            "signal": prev.get("signal", "NEUTRAL"),
            "spread_history": spread_history,
            "summary": parsed["summary"],
            "headlines": parsed["headlines"],
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
