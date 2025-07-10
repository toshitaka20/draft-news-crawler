#!/usr/bin/env python3
"""
Test script to inspect HTML classes in Sports Hochi articles
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
from bs4 import BeautifulSoup
from config import HOCHI_URLS

def inspect_hochi_classes():
    """Inspect HTML classes in Sports Hochi articles"""
    print("Inspecting HTML classes in Sports Hochi articles...")
    
    # Get first URL
    test_url = list(HOCHI_URLS.values())[0]
    
    # Fetch article links
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(test_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Find article links
    article_list = soup.find('ul', class_='article-list')
    if article_list:
        found_links = article_list.find_all('a', class_='article-list__unit', href=True)
        if found_links:
            # Test first article
            first_article_url = 'https://hochi.news' + found_links[0]['href']
            print(f"Testing article: {first_article_url}")
            
            # Fetch article content
            article_res = requests.get(first_article_url, headers=headers)
            article_soup = BeautifulSoup(article_res.content, 'html.parser')
            
            # Look for all p tags and their classes
            all_p_tags = article_soup.find_all('p')
            print(f"Found {len(all_p_tags)} p tags")
            
            # Check for article__text class
            article_text_p = article_soup.find_all('p', class_='article__text')
            print(f"Found {len(article_text_p)} p tags with article__text class")
            
            # Check for other common classes
            classes_found = set()
            for p in all_p_tags:
                if p.get('class'):
                    classes_found.update(p.get('class'))
            
            print(f"All p tag classes found: {classes_found}")
            
            # Show first few p tags with their classes
            print("\nFirst 5 p tags:")
            for i, p in enumerate(all_p_tags[:5]):
                classes = p.get('class', [])
                text_preview = p.get_text()[:50] + "..." if len(p.get_text()) > 50 else p.get_text()
                print(f"  {i+1}. Classes: {classes}, Text: {text_preview}")

if __name__ == "__main__":
    inspect_hochi_classes() 