from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import json
import re
import time
import threading
import os
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# In-memory cache configuration
cache = {
    'news': [],
    'last_update': None,
    'cache_duration': 300,  # 5 minutes in seconds
}

class NewsCache:
    def __init__(self):
        self.cache = {}
        
    def get(self, key):
        if key in self.cache:
            item = self.cache[key]
            if datetime.now() < item['expiry']:
                return item['data']
        return None
        
    def set(self, key, value, ttl_seconds):
        self.cache[key] = {
            'data': value,
            'expiry': datetime.now() + timedelta(seconds=ttl_seconds)
        }

news_cache = NewsCache()

def cache_response(ttl_seconds=300):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cache_key = f.__name__ + str(args) + str(kwargs)
            response = news_cache.get(cache_key)
            
            if response is None:
                response = f(*args, **kwargs)
                news_cache.set(cache_key, response, ttl_seconds)
            
            return response
        return wrapper
    return decorator

def clean_html(raw_html):
    """Remove HTML tags and decode entities"""
    cleanr = re.compile('<.*?>')
    text = re.sub(cleanr, '', raw_html)
    return ' '.join(text.split())

def extract_link(html_text):
    """Extract the first link from HTML content"""
    soup = BeautifulSoup(html_text, 'lxml')
    link = soup.find('a')
    return link.get('href') if link else ''

def fetch_news():
    """Fetch crypto news from Google News RSS feed"""
    url = "https://news.google.com/rss/search?q=cryptocurrency+OR+bitcoin+OR+crypto&hl=en-US&gl=US&ceid=US:en"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, features='xml')
        items = soup.find_all('item')
        
        news_items = []
        for item in items:
            summary_html = item.description.text if item.description else ''
            summary = clean_html(summary_html)
            source = clean_html(summary_html.split('</a>')[-1]) if summary_html else ''
            
            news_item = {
                'title': item.title.text if item.title else '',
                'link': extract_link(summary_html),
                'published_date': item.pubDate.text if item.pubDate else '',
                'summary': summary,
                'source': source.strip()
            }
            news_items.append(news_item)
            
        return news_items
            
    except Exception as e:
        logger.error(f"Error fetching news: {str(e)}")
        return []

def update_cache():
    """Update the news cache"""
    while True:
        try:
            news_items = fetch_news()
            if news_items:
                cache['news'] = news_items
                cache['last_update'] = datetime.now()
                logger.info(f"Cache updated at {cache['last_update']}")
        except Exception as e:
            logger.error(f"Error updating cache: {str(e)}")
        
        time.sleep(cache['cache_duration'])

# Start the cache update thread
update_thread = threading.Thread(target=update_cache, daemon=True)
update_thread.start()

@app.route('/')
def home():
    """Home page with API information"""
    return jsonify({
        'status': 'active',
        'endpoints': {
            '/news': 'Get all crypto news',
            '/news/latest/<count>': 'Get latest n news items',
            '/status': 'Get API status'
        },
        'github': 'https://github.com/yourusername/crypto-news-api'
    })

@app.route('/news', methods=['GET'])
@cache_response(ttl_seconds=300)
def get_news():
    """Get all news with CDN-friendly headers"""
    response = jsonify({
        'status': 'success',
        'last_update': cache['last_update'].strftime('%Y-%m-%d %H:%M:%S') if cache['last_update'] else None,
        'count': len(cache['news']),
        'news': cache['news']
    })
    
    # Add CDN-friendly headers
    response.headers['Cache-Control'] = 'public, max-age=300'
    response.headers['X-Cache-Hit'] = 'true' if cache['news'] else 'false'
    response.headers['Last-Modified'] = cache['last_update'].strftime('%a, %d %b %Y %H:%M:%S GMT') if cache['last_update'] else ''
    
    return response

@app.route('/news/latest/<int:count>', methods=['GET'])
@cache_response(ttl_seconds=300)
def get_latest_news(count):
    """Get latest n news items"""
    response = jsonify({
        'status': 'success',
        'last_update': cache['last_update'].strftime('%Y-%m-%d %H:%M:%S') if cache['last_update'] else None,
        'count': min(count, len(cache['news'])),
        'news': cache['news'][:count]
    })
    
    response.headers['Cache-Control'] = 'public, max-age=300'
    return response

@app.route('/status', methods=['GET'])
def get_status():
    """Get service status"""
    return jsonify({
        'status': 'active',
        'last_update': cache['last_update'].strftime('%Y-%m-%d %H:%M:%S') if cache['last_update'] else None,
        'total_news_count': len(cache['news']),
        'cache_duration': cache['cache_duration'],
        'uptime': 'Running on Render'
    })

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)