import json
import os
from pathlib import Path

from datetime import datetime

import anthropic
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader

def scrape_news():
    """Main function to scrape and summarize news for all countries."""
    
    # Load environment variables
    load_dotenv(override=True)

    # Get API key and verify it exists
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in .env file")

    client = anthropic.Anthropic(api_key=api_key)

    # Country Groups
    IG_COUNTRIES = {
        'Mexico': 'BBB',
        'Chile': 'A',
        'Brazil': 'BB',
        'Panama': 'BBB',
    }

    HY_COUNTRIES = {
        'Ecuador': 'B',
        'El Salvador': 'B-',
        'Argentina': 'C',
        'Dominican Republic': 'BB-',
        'Colombia': 'BB+'
    }

    class NewsSource:
        def __init__(self, name, url, country):
            self.name = name
            self.url = url
            self.country = country

    class NewsScraper:
        def __init__(self):
            self.sources = {
                'Ecuador': [NewsSource('El Universo', 'https://www.eluniverso.com/', 'Ecuador')],
                'Brazil': [NewsSource('O Globo', 'https://oglobo.globo.com/', 'Brazil')],
                'El Salvador': [NewsSource('El Salvador', 'https://www.elsalvador.com/', 'El Salvador')],
                'Argentina': [NewsSource('El Pais Argentina', 'https://elpais.com/noticias/argentina/', 'Argentina')],
                'Panama': [NewsSource('La Prensa', 'https://www.prensa.com/', 'Panama')],
                'Chile': [NewsSource('La Tercera', 'https://elpais.com/noticias/chile/', 'Chile')],
                'Mexico': [NewsSource('El Universal', 'https://www.eluniversal.com.mx/', 'Mexico')],
                'Dominican Republic': [NewsSource('Diario Libre', 'https://www.diariolibre.com/?noredirect=1', 'Dominican Republic')],
                'Colombia': [NewsSource('El Pais Colombia', 'https://elpais.com/noticias/colombia/', 'Colombia')]
            }
        
        def scrape_article(self, url):
            try:
                loader = WebBaseLoader(url)
                docs = loader.load()
                return docs[0].page_content
            except Exception as e:
                print(f"Error scraping article: {e}")
                return None

        def summarize_article(self, article_data):
            """Summarize article content using Anthropic Claude."""
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system="You are a financial analyst focused on sovereign bond markets. Extract the most relevant local news that could impact government bond prices.",
                    messages=[
                        {
                            "role": "user",
                            "content": f"""Analyze the following news content and provide:
                            1. A two-line summary of the overall situation in the country
                            2. The top 5 most important local headlines that could affect government bond prices, focusing on:
                            - Fiscal policy and budget news
                            - Political developments affecting economic policy
                            - Monetary policy and central bank actions
                            - Major economic indicators (GDP, inflation, debt)
                            - Significant infrastructure or energy projects

                            Content:\n{article_data}

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
                        }
                    ]
                )
                return response.content[0].text
            except Exception as e:
                print(f"Error summarizing article: {e}")
                return None

        def get_summaries(self, country=None):
            results = {}
            
            if country:
                if country not in self.sources:
                    raise ValueError(f"No sources available for {country}")
                countries_to_scrape = [country]
            else:
                countries_to_scrape = list(self.sources.keys())
                
            for country in countries_to_scrape:
                country_summaries = []
                for source in self.sources[country]:
                    article_data = self.scrape_article(source.url)
                    if article_data:
                        article_data_with_url = f"The article's url is {source.url}. \n The article data is:\n {article_data}"
                        summary = self.summarize_article(article_data_with_url)
                        if summary:
                            country_summaries.append({
                                'source': source.name,
                                'summary': summary
                            })
                results[country] = country_summaries
                
            return results

    # Initialize scraper and get summaries
    scraper = NewsScraper()
    all_summaries = {}
    
    # Process all countries
    for country in list(IG_COUNTRIES.keys()) + list(HY_COUNTRIES.keys()):
        try:
            print(f"\nProcessing {country}...")
            country_summaries = scraper.get_summaries(country)
            if country_summaries.get(country):
                all_summaries[country] = country_summaries[country]
            else:
                print(f"No summaries available for {country}")
        except Exception as e:
            print(f"Error processing {country}: {str(e)}")
    
    # Split results into IG and HY
    ig_summaries = {country: all_summaries.get(country, []) for country in IG_COUNTRIES.keys()}
    hy_summaries = {country: all_summaries.get(country, []) for country in HY_COUNTRIES.keys()}
    
    # Build results with rating info included per country
    results = {
        'timestamp': datetime.now().isoformat(),
        'investment_grade': {
            country: {'rating': IG_COUNTRIES[country], 'articles': ig_summaries.get(country, [])}
            for country in IG_COUNTRIES
        },
        'high_yield': {
            country: {'rating': HY_COUNTRIES[country], 'articles': hy_summaries.get(country, [])}
            for country in HY_COUNTRIES
        },
    }

    # Write to public/data.json
    out_dir = Path(__file__).resolve().parent / "public"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "data.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nWrote results to {out_path}")

    return results

if __name__ == "__main__":
    scrape_news()
