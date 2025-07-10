#!/usr/bin/env python3
"""
中日スポーツスクレイパーのテスト（完全依存回避版）
"""
import sys
import os
import importlib.util

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# scraper/chunichi.pyを直接import
scraper_path = os.path.join(os.path.dirname(__file__), '../scraper/chunichi.py')
spec = importlib.util.spec_from_file_location('chunichi', scraper_path)
chunichi = importlib.util.module_from_spec(spec)
sys.modules['chunichi'] = chunichi
spec.loader.exec_module(chunichi)


def test_chunichi():
    print("=== 中日スポーツ記事取得テスト ===")
    try:
        articles = chunichi.fetch_all_chunichi_articles()
        print(f"\n取得結果: {len(articles)}件")
        for i, article in enumerate(articles, 1):
            print(f"\n--- 記事 {i} ---")
            print(f"タイトル: {article.get('title', '')}")
            print(f"URL: {article.get('url', '')}")
            print(f"日付: {article.get('date', '')}")
            print(f"カテゴリ: {article.get('category', '')}")
            print(f"本文: {article.get('body', '')[:100]}...")
            print(f"キーワードあり: {article.get('has_keywords', False)}")
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")

if __name__ == "__main__":
    test_chunichi() 