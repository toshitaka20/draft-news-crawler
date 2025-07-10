"""
野球記事収集・AIコメント抽出システム
メインエントリーポイント
"""

from typing import List, Dict, Any
from scraper.sponichi import fetch_all_sponichi_articles
from scraper.hochi import fetch_hochi_articles
from scraper.nikkan_sports import fetch_all_nikkan_sports_articles
from ai.gemini import process_articles_with_ai
from sheets.google_sheets import update_sheets, get_existing_urls_by_source
from utils import deduplicate_articles

def main():
    """
    メイン処理
    """
    print("=== 野球記事収集・AIコメント抽出システム ===")
    
    all_articles = []
    
    try:
        # 1. スポニチ記事取得
        print("\n1. スポニチ記事取得中...")
        sponichi_existing_urls = get_existing_urls_by_source('スポニチ')
        sponichi_articles = fetch_all_sponichi_articles(exclude_urls=sponichi_existing_urls)
        all_articles.extend(sponichi_articles)
        print(f"スポニチ記事数: {len(sponichi_articles)}")
        
        # 2. スポーツ報知記事取得
        print("\n2. スポーツ報知記事取得中...")
        hochi_existing_urls = get_existing_urls_by_source('スポーツ報知')
        hochi_articles = []
        from config import HOCHI_URLS
        for category, url in HOCHI_URLS.items():
            print(f"  {category}記事取得中...")
            category_articles = fetch_hochi_articles(url, exclude_urls=hochi_existing_urls, category=category)
            hochi_articles.extend(category_articles)
        all_articles.extend(hochi_articles)
        print(f"スポーツ報知記事数: {len(hochi_articles)}")
        
        # 3. 日刊スポーツ記事取得
        print("\n3. 日刊スポーツ記事取得中...")
        nikkan_existing_urls = get_existing_urls_by_source('日刊スポーツ')
        nikkan_articles = fetch_all_nikkan_sports_articles(exclude_urls=nikkan_existing_urls)
        all_articles.extend(nikkan_articles)
        print(f"日刊スポーツ記事数: {len(nikkan_articles)}")
        
        # 4. 重複除去
        print("\n4. 重複除去中...")
        unique_articles = deduplicate_articles(all_articles)
        print(f"重複除去後記事数: {len(unique_articles)}")
        
        # 5. AIコメント抽出（キーワードあり記事のみ）
        print("\n5. AIコメント抽出中...")
        keyword_articles = [a for a in unique_articles if a.get('has_keywords', False)]
        processed_keyword_articles = process_articles_with_ai(keyword_articles)
        print(f"AI処理完了記事数: {len(processed_keyword_articles)}")
        
        # 6. キーワードなし記事にもscout_comments/scout_rowsをセット
        no_keyword_articles = [a for a in unique_articles if not a.get('has_keywords', False)]
        for a in no_keyword_articles:
            a['scout_comments'] = "キーワードなし"
            a['scout_rows'] = []
        
        # 7. 全記事をマージしてGoogle Sheets更新
        all_processed = processed_keyword_articles + no_keyword_articles
        print("\n6. Google Sheets更新中...")
        update_sheets(all_processed)
        
        print(f"\n=== 処理完了 ===")
        print(f"総記事数: {len(all_processed)}")
        
        # 結果サマリー
        sources = {}
        for article in all_processed:
            source = article.get('source', '不明')
            sources[source] = sources.get(source, 0) + 1
        
        print("\n=== ソース別記事数 ===")
        for source, count in sources.items():
            print(f"{source}: {count}件")
        
    except Exception as e:
        print(f"[エラー] メイン処理失敗: {e}")
        raise

if __name__ == "__main__":
    main() 