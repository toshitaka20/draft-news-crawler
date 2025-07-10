#!/usr/bin/env python3
"""
Test script for Nikkan Sports scraping
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.nikkan_sports import fetch_all_nikkan_sports_articles

def test_nikkan_sports():
    """Test Nikkan Sports article fetching"""
    print("Testing Nikkan Sports article fetching...")
    
    try:
        articles = fetch_all_nikkan_sports_articles()
        print(f"Found {len(articles)} articles from Nikkan Sports")
        
        if articles:
            print("\n=== Sample Articles ===")
            for i, article in enumerate(articles[:3]):
                print(f"\n--- Article {i+1} ---")
                print(f"Title: {article.get('title', 'N/A')}")
                print(f"URL: {article.get('url', 'N/A')}")
                print(f"Date: {article.get('date', 'N/A')}")
                print(f"Body length: {len(article.get('body', ''))}")
                print(f"Body preview: {article.get('body', '')[:200]}...")
                print("-" * 50)
        else:
            print("No articles found from Nikkan Sports")
            
    except Exception as e:
        print(f"Error testing Nikkan Sports: {e}")

if __name__ == "__main__":
    test_nikkan_sports() 