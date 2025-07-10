#!/usr/bin/env python3
"""
Test script for Sports Hochi direct paragraph extraction
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.hochi import fetch_hochi_article_links, fetch_hochi_article_body

def test_hochi_direct():
    """Test direct paragraph extraction from Sports Hochi"""
    print("Testing Sports Hochi direct paragraph extraction...")
    
    # Fetch article links from the first URL
    from config import HOCHI_URLS
    test_url = list(HOCHI_URLS.values())[0]  # Use the first URL for testing
    article_links = fetch_hochi_article_links(test_url)
    print(f"Found {len(article_links)} article links")
    
    if not article_links:
        print("No article links found")
        return
    
    # Test first 3 articles
    for i, url in enumerate(article_links[:3]):
        print(f"\n--- Article {i+1} ---")
        print(f"URL: {url}")
        
        article_body = fetch_hochi_article_body(url)
        print(f"Article body length: {len(article_body)}")
        print(f"First 200 chars: {article_body[:200]}...")
        print("-" * 50)

if __name__ == "__main__":
    test_hochi_direct() 