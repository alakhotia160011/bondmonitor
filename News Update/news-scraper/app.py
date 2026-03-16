from flask import Flask, render_template
from scraper import scrape_news
import os

app = Flask(__name__)

@app.route("/")
def index():
    # run your notebook logic on each request
    news = scrape_news()
    return render_template("news.html", news=news)

if __name__ == "__main__":
    # For local dev
    app.run(host="0.0.0.0", port=5000, debug=True)
