#!/usr/bin/env python3
"""
AI処理精度向上テストスクリプト
キーワードを含む記事のみを対象に、改善されたAI処理をテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.sponichi import fetch_sponichi_articles
from ai.gemini import process_articles_with_ai
from config import SPONICHI_URLS

def test_ai_improvement():
    """
    AI処理精度向上テスト
    """
    print("=== AI処理精度向上テスト ===\n")
    
    # 1. スポニチ記事取得（キーワード記事のみ）
    print("1. スポニチ記事取得中...")
    sponichi_articles = []
    for category, url in SPONICHI_URLS.items():
        print(f"\n=== スポニチ {category} ===")
        articles = fetch_sponichi_articles(url, [], limit=5)  # テスト用に5件に制限
        sponichi_articles.extend(articles)
    
    # キーワード記事のみをフィルタリング
    keyword_articles = [article for article in sponichi_articles if article.get('has_keywords', False)]
    print(f"\nスポニチキーワード記事数: {len(keyword_articles)}")
    
    if not keyword_articles:
        print("キーワード記事が見つかりませんでした。")
        return
    
    # 2. AI処理実行
    print("\n2. AI処理実行中...")
    processed_articles = process_articles_with_ai(keyword_articles)
    
    # 3. 結果表示
    print("\n3. AI処理結果:")
    print("=" * 80)
    
    for i, article in enumerate(processed_articles, 1):
        print(f"\n{i}. {article.get('title', '')[:60]}...")
        print(f"   カテゴリ: {article.get('category', 'N/A')}")
        print(f"   キーワードフラグ: {article.get('has_keywords', False)}")
        print(f"   スカウトコメント:")
        
        scout_comments = article.get('scout_comments', '')
        if scout_comments and scout_comments != "キーワードなし":
            # CSV形式の場合は整形して表示
            if "選手名," in scout_comments:
                lines = scout_comments.strip().split('\n')
                if len(lines) > 1:
                    print("   " + "=" * 50)
                    for line in lines[1:]:  # ヘッダーをスキップ
                        if line.strip():
                            print(f"   {line}")
                    print("   " + "=" * 50)
                else:
                    print(f"   {scout_comments}")
            else:
                print(f"   {scout_comments}")
        else:
            print("   コメントなし")
    
    print(f"\n=== テスト完了 ===")
    print(f"処理記事数: {len(processed_articles)}")
    print(f"スカウトコメント抽出結果を上記で確認してください。")

if __name__ == "__main__":
    test_ai_improvement() 