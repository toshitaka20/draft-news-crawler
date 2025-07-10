#!/usr/bin/env python3
"""
Test script to check Nikkan Sports RSS feeds directly
"""

import feedparser
import requests
from config import NIKKAN_FEEDS

def test_nikkan_rss():
    """Test Nikkan Sports RSS feeds directly"""
    print("Testing Nikkan Sports RSS feeds...")
    
    for category, url in NIKKAN_FEEDS.items():
        print(f"\n=== {category} ===")
        print(f"URL: {url}")
        
        try:
            # Try direct feedparser
            feed = feedparser.parse(url)
            print(f"Feed entries: {len(feed.entries)}")
            
            if feed.entries:
                print("Sample entries:")
                for i, entry in enumerate(feed.entries[:3]):
                    print(f"  {i+1}. {entry.get('title', 'No title')}")
                    print(f"     Link: {entry.get('link', 'No link')}")
                    print(f"     Published: {entry.get('published', 'No date')}")
            else:
                print("No entries found")
                
                # Try direct HTTP request
                print("\nTrying direct HTTP request...")
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(url, headers=headers, timeout=10)
                print(f"HTTP Status: {response.status_code}")
                print(f"Content length: {len(response.text)}")
                print(f"Content preview: {response.text[:500]}...")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_nikkan_rss() 