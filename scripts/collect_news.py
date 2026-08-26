import feedparser
import requests
import json
import os
import re
import time

RSSHUB_DOMAINS = [
    "rsshub.rssforever.com",
    "rsshub.feeded.xyz",
    "rss.fwqc.club",
    "hub.slarker.me",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

# Финальные 5 кулинарных каналов
COOKING_CHANNELS = [
    {"path": "/telegram/channel/min2ru", "name": "Кухня наизнанку", "posts": 20},
    {"path": "/telegram/channel/topretsept", "name": "Рецепты Каждый День", "posts": 20},
    {"path": "/telegram/channel/iamcook", "name": "Аймкук", "posts": 20},
    {"path": "/telegram/channel/prostye_recepty", "name": "Простые Рецепты", "posts": 20},
    {"path": "/telegram/channel/FoodTG", "name": "Вкусная кухня", "posts": 20},
]

def get_timestamp(entry):
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            return time.mktime(entry.published_parsed)
        except Exception:
            return 0
    return 0

def extract_image_from_entry(entry):
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if 'image' in media.get('type', ''):
                return media.get('url', '')
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '') or enc.get('url', '')
    if hasattr(entry, 'description'):
        m = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
        if m:
            return m.group(1)
    if hasattr(entry, 'summary'):
        m = re.search(r'<img[^>]+src="([^"]+)"', entry.summary)
        if m:
            return m.group(1)
    return ""

def extract_video_from_entry(entry):
    if hasattr(entry, 'description'):
        m = re.search(r'<video[^>]+src="([^"]+)"', entry.description)
        if m:
            return m.group(1)
    return ""

def parse_rss_with_fallback(base_path, channel_name=None, timeout=15):
    for domain in RSSHUB_DOMAINS:
        url = f"https://{domain}{base_path}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.text)
                if feed.entries:
                    print(f"  ✅ RSSHub [{domain}]: OK ({len(feed.entries)} постов)")
                    return feed
                else:
                    print(f"  ⚠️ [{domain}]: пусто")
            else:
                print(f"  ⚠️ [{domain}]: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  ⚠️ [{domain}]: {type(e).__name__}")
    print(f"  ❌ Все домены RSSHub недоступны для {channel_name or base_path}")
    return None

def collect_from_cooking_channels():
    articles = []
    for channel in COOKING_CHANNELS:
        print(f"  🍳 {channel['name']}...")
        feed = parse_rss_with_fallback(channel['path'], channel['name'])
        if not feed:
            continue
        for entry in feed.entries[:channel['posts']]:
            articles.append({
                "title": entry.title if hasattr(entry, 'title') else '',
                "link": entry.link if hasattr(entry, 'link') else '',
                "published": entry.published if hasattr(entry, 'published') else "",
                "timestamp": get_timestamp(entry),
                "source": f"TG: {channel['name']}",
                "language": "ru",
                "description": entry.description if hasattr(entry, 'description') else "",
                "summary": entry.summary if hasattr(entry, 'summary') else "",
                "image": extract_image_from_entry(entry),
                "video": extract_video_from_entry(entry)
            })
    return articles

def remove_duplicates(articles):
    unique = []
    seen = set()
    for article in articles:
        if article['link'] not in seen:
            seen.add(article['link'])
            unique.append(article)
    return unique

def main():
    print("🍳 Начинаем сбор кулинарных рецептов...")
    
    all_articles = collect_from_cooking_channels()
    print(f"\n📊 Собрано постов: {len(all_articles)}")
    
    print("🔍 Убираем дубликаты...")
    unique_articles = remove_duplicates(all_articles)
    
    unique_articles.sort(key=lambda a: a.get('timestamp', 0), reverse=True)
    
    os.makedirs('src/content', exist_ok=True)
    output_file = 'src/content/news.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_articles, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Собрано {len(unique_articles)} уникальных рецептов")
    print(f"📁 Сохранено в {output_file}")

if __name__ == "__main__":
    main()