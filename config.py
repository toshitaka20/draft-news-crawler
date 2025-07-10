"""
設定・定数管理
"""

import os
from typing import Dict, List

# 日刊フィードURL
NIKKAN_FEEDS = {
    "高校野球": "https://www.nikkansports.com/baseball/highschool/atom.xml",
    "大学・社会人野球": "https://www.nikkansports.com/baseball/amateur/atom.xml"
}

# スポニチURL
SPONICHI_URLS = {
    "高校野球": "https://www.sponichi.co.jp/baseball/tokusyu/highschool/",
    "大学野球": "https://www.sponichi.co.jp/baseball/tokusyu/university/",
    "社会人野球": "https://www.sponichi.co.jp/baseball/tokusyu/shakaijin/"
}

# スポーツ報知URL
HOCHI_URLS = {
    "高校野球": "https://hochi.news/hsb/",
    "大学・社会人野球": "https://hochi.news/tag/%E3%82%A2%E3%83%9E%E9%87%8E%E7%90%83"
}

# キーワード
SCOUT_KEYWORDS = ["draft", "scout", "comment", "ドラフト", "スカウト", "コメント"]
AI_KEYWORDS = ["ドラフト", "スカウト", "コメント", "視察", "熱視線"]

# Google Sheets設定
SPREADSHEET_NAME = 'DraftNews'
CREDENTIALS_FILE = 'credentials.json'

# Gemini API設定
GEMINI_API_KEY = os.getenv('GOOGLE_GENAI_API_KEY', '')
GEMINI_MODEL = 'gemini-2.0-flash'

# スクレイピング設定
MAX_ARTICLES_PER_SOURCE = 20
SLEEP_SECONDS = 1 