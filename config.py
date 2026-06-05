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
    "高校野球": "https://hochi.news/tag/%E9%AB%98%E6%A0%A1%E9%87%8E%E7%90%83",
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
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite')

# スクレイピング設定
MAX_ARTICLES_PER_SOURCE = 20
SLEEP_SECONDS = 1 

# Yahoo!スポーツナビ設定
YAHOO_SPONAVI_CONFIG = {
    'enabled': True,
    'max_articles_per_category': 30,
    'categories': ['高校野球', '大学野球'],
    'request_timeout': 15,
    'sleep_between_requests': 1.5,
    'sleep_between_categories': 2,
    'max_retries': 3
}

# Yahoo!スポーツナビURL
YAHOO_SPONAVI_URLS = {
    "高校野球": "https://sports.yahoo.co.jp/list/news/?genre=hsb",
    "大学野球": "https://sports.yahoo.co.jp/list/news/?genre=baseball_univ"
}

# Yahoo!スポーツナビ記事取得数（高頻度実行のため少なめ）
YAHOO_SPONAVI_MAX_ARTICLES = 20

# 重複除去設定
DEDUPLICATION_CONFIG = {
    'similarity_threshold': 0.8,  # 類似度の閾値
    'yahoo_similarity_threshold': 0.7,  # Yahoo重複判定の閾値（より厳しく）
    'enable_hash_deduplication': True,  # ハッシュベース重複除去
    'enable_similarity_deduplication': True,  # 類似度ベース重複除去
    'filter_yahoo_duplicates': True,  # Yahoo重複記事フィルタ
    'preserve_original_sources': True  # オリジナルソース優先
}

# ソース優先度設定
SOURCE_PRIORITY = {
    'スポニチ': 1,
    'スポーツ報知': 1,
    '日刊スポーツ': 1,
    'サンスポ': 1,
    '中日スポーツ': 1,
    'Yahoo!スポーツナビ': 10,
    'その他': 5
} 

# 重複除去設定の統合
DUPLICATE_REMOVAL_SETTINGS = {
    'similarity_threshold': 0.8,
    'yahoo_filter_threshold': 0.7,
    'content_min_length': {
        'title': 10,
        'body': 50
    }
} 
