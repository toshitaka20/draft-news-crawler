import os
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

FEEDS = {
    "高校野球": "https://www.nikkansports.com/baseball/highschool/atom.xml",
    "大学・社会人": "https://www.nikkansports.com/baseball/amateur/atom.xml"
}

KEYWORDS = ["ドラフト", "スカウト", "コメント", "視察"]

# credentials.jsonがなければ環境変数から生成
if not os.path.exists('credentials.json'):
    google_creds = os.environ.get('GOOGLE_CREDENTIALS')
    if google_creds:
        with open('credentials.json', 'w', encoding='utf-8') as f:
            f.write(google_creds)

# デバッグ用: credentials.jsonの先頭10行だけ出力（機密情報に注意！）
if os.path.exists('credentials.json'):
    with open('credentials.json', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print('--- credentials.json 先頭10行（デバッグ用・機密情報注意）---')
        print(''.join(lines[:10]))
        print('--- end ---')

# Google Sheets認証とシート準備
def setup_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)  # type: ignore
    client = gspread.authorize(creds)
    # 既存スプレッドシートのIDまたは新規作成
    try:
        sheet = client.open("DraftNews").sheet1
    except gspread.SpreadsheetNotFound:
        sheet = client.create("DraftNews").sheet1
    # ヘッダー行
    sheet.update([['カテゴリ', 'タイトル', '公開日', 'リンク', '本文', 'フラグ']])
    return sheet

def fetch_body(url):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        body = soup.select_one('.article-body')
        return body.get_text(strip=True) if body else ''
    except:
        return ''

def main():
    sheet = setup_sheet()
    rows = []
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            published = entry.get("published", "")
            content = fetch_body(link)
            # フラグ判定
            flag = ''
            for kw in KEYWORDS:
                if kw in content:
                    flag = '⚑'
                    break
            print(f"\n📰 {category} / {title}")
            print(f"📅 {published}")
            print(f"🔗 {link}")
            print(f"📝 本文:\n{content[:300]}...")
            if flag:
                print(f"🚩 フラグ: {flag}")
            # スプレッドシート用データ
            rows.append([category, title, published, link, content, flag])
    # スプレッドシートに一括書き込み
    if rows:
        sheet.append_rows(rows)

if __name__ == "__main__":
    main()
