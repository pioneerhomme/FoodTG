import feedparser
import requests
import json
import os
import re
from datetime import datetime

# Список доменов RSSHub для фолбэка (если один не работает, пробуем следующий)
RSSHUB_DOMAINS = [
    "rsshub.rssforever.com",
    "rsshub.feeded.xyz",
    "rss.fwqc.club",
    "hub.slarker.me",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def extract_image_from_entry(entry):
    """Достаёт картинку из RSS-записи"""
    # Проверяем media_content
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if 'image' in media.get('type', ''):
                return media.get('url', '')
    # Проверяем media_thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    # Проверяем enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '') or enc.get('url', '')
    # Ищем img в description
    if hasattr(entry, 'description'):
        m = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
        if m:
            return m.group(1)
    if hasattr(entry, 'summary'):
        m = re.search(r'<img[^>]+src="([^"]+)"', entry.summary)
        if m:
            return m.group(1)
    return ""

def parse_rss_with_fallback(base_path, channel_name=None, timeout=15):
    """
    Пробует получить RSS по всем доменам RSSHub по очереди.
    base_path — путь после домена, например: /telegram/channel/topor
    """
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

def collect_from_telegram_channels():
    """Собирает новости из Telegram каналов через RSSHub (ПРИОРИТЕТ)"""
    
    # Список Telegram каналов с путями
    telegram_channels = [
        {"path": "/telegram/channel/topor", "name": "ТОПОР", "posts": 15},
        {"path": "/telegram/channel/lentach", "name": "Лентач", "posts": 15},
        {"path": "/telegram/channel/krovavaya_bar", "name": "Кровавая барыня", "posts": 15},
        {"path": "/telegram/channel/mash", "name": "Mash", "posts": 15},
        {"path": "/telegram/channel/bazabazon", "name": "Baza", "posts": 15},
        {"path": "/telegram/channel/breakingmash", "name": "112", "posts": 15},
        {"path": "/telegram/channel/lifeshot", "name": "Life Shot", "posts": 15},
        {"path": "/telegram/channel/shtorm24", "name": "Шторм", "posts": 15},
        {"path": "/telegram/channel/readovka", "name": "Readovka", "posts": 15},
        {"path": "/telegram/channel/ranishvseh", "name": "Раньше всех", "posts": 15},
    ]
    
    articles = []
    
    for channel in telegram_channels:
        print(f"  📱 Telegram: {channel['name']}...")
        feed = parse_rss_with_fallback(channel['path'], channel['name'])
        
        if not feed:
            continue
        
        # Берём указанное количество постов
        for entry in feed.entries[:channel['posts']]:
            title = entry.title if hasattr(entry, 'title') else ''
            link = entry.link if hasattr(entry, 'link') else ''
            description = entry.description if hasattr(entry, 'description') else ''
            summary = entry.summary if hasattr(entry, 'summary') else ''
            image = extract_image_from_entry(entry)
            
            # Для TG постов используем description как основной текст
            # (обычно он уже содержит сам пост)
            articles.append({
                "title": title,
                "link": link,
                "published": entry.published if hasattr(entry, 'published') else "",
                "source": f"TG: {channel['name']}",
                "language": "ru",
                "description": description,
                "summary": summary,
                "image": image
            })
    
    print(f"\n📊 Из Telegram собрано: {len(articles)} постов")
    return articles

def collect_from_russian_rss():
    """Собирает новости из русскоязычных RSS лент"""
    
    feeds = [
        # Крупные новостные сайты
        {"url": "https://lenta.ru/rss", "name": "Лента.ру"},
        {"url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "name": "РБК"},
        {"url": "https://tass.ru/rss/v2.xml", "name": "ТАСС"},
        {"url": "https://ria.ru/export/rss2/archive/index.xml", "name": "РИА Новости"},
        {"url": "https://www.kommersant.ru/RSS/news.xml", "name": "Коммерсантъ"},
        
        # Технологические и развлекательные
        {"url": "https://habr.com/ru/rss/news/", "name": "Хабр"},
        {"url": "https://dtf.ru/rss", "name": "DTF"},
        {"url": "https://vc.ru/rss", "name": "VC.ru"},
        {"url": "https://pikabu.ru/xmlfeeds.php?cmd=rss", "name": "Пикабу"},
        
        # Научные и образовательные
        {"url": "https://nplus1.ru/rss", "name": "N+1"},
        {"url": "https://indicator.ru/rss.xml", "name": "Indicator"},
        
        # Бизнес и финансы
        {"url": "https://www.vedomosti.ru/rss/news", "name": "Ведомости"},
        {"url": "https://www.forbes.ru/newrss.xml", "name": "Forbes Россия"},
    ]
    
    articles = []
    
    for feed_info in feeds:
        try:
            print(f"  📰 Сайт: {feed_info['name']}...")
            feed = feedparser.parse(feed_info['url'])
            
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published if hasattr(entry, 'published') else "",
                    "source": feed_info['name'],
                    "language": "ru",
                    "description": entry.description if hasattr(entry, 'description') else "",
                    "summary": entry.summary if hasattr(entry, 'summary') else "",
                    "image": extract_image_from_entry(entry)
                })
        except Exception as e:
            print(f"  ⚠️ Ошибка {feed_info['name']}: {e}")
    
    print(f"\n📊 Из сайтов собрано: {len(articles)} статей")
    return articles

def remove_duplicates(articles):
    """Убирает дубликаты по ссылке"""
    unique = []
    seen = set()
    for article in articles:
        if article['link'] not in seen:
            seen.add(article['link'])
            unique.append(article)
    return unique

def main():
    """Главная функция — порядок важен!"""
    
    print("🚀 Начинаем сбор новостей...")
    
    all_articles = []
    
    # 📱 1. СНАЧАЛА Telegram-каналы (приоритет)
    print("\n" + "="*50)
    print("📱 ПРИОРИТЕТ 1: Telegram-каналы")
    print("="*50)
    all_articles.extend(collect_from_telegram_channels())
    
    # 📰 2. ПОТОМ обычные сайты
    print("\n" + "="*50)
    print("📰 ПРИОРИТЕТ 2: Сайты")
    print("="*50)
    all_articles.extend(collect_from_russian_rss())
    
    # Удаляем дубликаты
    print("\n🔍 Убираем дубликаты...")
    unique_articles = remove_duplicates(all_articles)
    
    # Сохраняем
    os.makedirs('src/content', exist_ok=True)
    output_file = 'src/content/news.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_articles, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Собрано {len(unique_articles)} уникальных статей")
    print(f"📁 Сохранено в {output_file}")

if __name__ == "__main__":
    main()