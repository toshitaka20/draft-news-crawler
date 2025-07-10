"""
スクレイピング関連のモジュール
"""

from .sponichi import fetch_sponichi_articles
from .hochi import fetch_hochi_articles
from .nikkan_sports import fetch_nikkan_sports_articles

__all__ = [
    'fetch_sponichi_articles',
    'fetch_hochi_articles', 
    'fetch_nikkan_sports_articles'
] 