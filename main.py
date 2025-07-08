import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime

FEEDS = {
    "高校野球": "https://www.nikkansports.com/baseball/highschool/atom.xml",
    "大学・社会人": "https://www.nikkansports.com/baseball/amateur/atom.xml"
}

def fetch_body(url):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        body = soup.select_one('.article-body')
        return body.get_text(strip=True) if body else ''
    except:
        return ''

def main():
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            published = entry.get("published", "")
            content = fetch_body(link)
            print(f"\n📰 {category} / {title}")
            print(f"📅 {published}")
            print(f"🔗 {link}")
            print(f"📝 本文:\n{content[:300]}...")

if __name__ == "__main__":
    main()
