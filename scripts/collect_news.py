import feedparser
import requests
import json
import os
from datetime import datetime

# Рабочие инстансы RSSHub (мосты Telegram → RSS)
RSSHUB_INSTANCES = [
    "https://rsshub.rssforever.com",
    "https://rsshub.app",
]

# Telegram-каналы для мониторинга
TELEGRAM_CHANNELS = [
    {"username": "topor", "name": "Топор"},
    {"username": "lentach", "name": "Лентач"},
    # Добавляйте свои каналы по образцу:
    # {"username": "ria_kremlinpool", "name": "Кремлёвский пул"},
    # {"username": "oldskaza", "name": "Старая сказа"},
]

def collect_from_russian_rss():
    """Собирает новости из русскоязычных RSS лент"""
    
    feeds = [
        {"url": "https://lenta.ru/rss", "name": "Лента.ру"},
        {"url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "name": "РБК"},
        {"url": "https://tass.ru/rss/v2.xml", "name": "ТАСС"},
        {"url": "https://ria.ru/export/rss2/archive/index.xml", "name": "РИА Новости"},
        {"url": "https://www.kommersant.ru/RSS/news.xml", "name": "Коммерсантъ"},
        {"url": "https://habr.com/ru/rss/news/", "name": "Хабр"},
        {"url": "https://dtf.ru/rss", "name": "DTF"},
        {"url": "https://tjournal.ru/rss", "name": "TJ"},
        {"url": "https://vc.ru/rss", "name": "VC.ru"},
        {"url": "https://pikabu.ru/xmlfeeds.php?cmd=rss", "name": "Пикабу"},
        {"url": "https://nplus1.ru/rss", "name": "N+1"},
        {"url": "https://www.vedomosti.ru/rss/news", "name": "Ведомости"},
        {"url": "https://www.forbes.ru/newrss.xml", "name": "Forbes Россия"},
    ]
    
    articles = []
    
    for feed_info in feeds:
        try:
            print(f"  📰 Собираем из {feed_info['name']}...")
            feed = feedparser.parse(feed_info['url'])
            
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published if hasattr(entry, 'published') else "",
                    "source": feed_info['name'],
                    "language": "ru",
                    "description": entry.description if hasattr(entry, 'description') else "",
                    "summary": entry.summary if hasattr(entry, 'summary') else ""
                })
                
        except Exception as e:
            print(f"  ⚠️ Ошибка при обработке {feed_info['name']}: {e}")
    
    return articles

def collect_from_telegram_channels():
    """Собирает посты из Telegram-каналов через RSSHub"""
    
    articles = []
    
    for channel in TELEGRAM_CHANNELS:
        collected = False
        
        # Пробуем инстансы по очереди, пока не сработает
        for instance in RSSHUB_INSTANCES:
            feed_url = f"{instance}/telegram/channel/{channel['username']}"
            
            try:
                print(f"  📱 Собираем из TG: {channel['name']} ({instance})...")
                feed = feedparser.parse(feed_url)
                
                # Если в фиде есть записи — инстанс работает
                if len(feed.entries) > 0:
                    for entry in feed.entries[:5]:
                        articles.append({
                            "title": entry.title,
                            "link": entry.link,
                            "published": entry.published if hasattr(entry, 'published') else "",
                            "source": channel['name'],
                            "language": "ru",
                            "description": entry.description if hasattr(entry, 'description') else "",
                            "summary": entry.summary if hasattr(entry, 'summary') else ""
                        })
                    collected = True
                    break  # Инстанс сработал, переходим к следующему каналу
                    
            except Exception as e:
                print(f"  ⚠️ Ошибка {instance}: {e}")
        
        if not collected:
            print(f"  ❌ Не удалось собрать {channel['name']}")
    
    return articles

def remove_duplicates(articles):
    """Убирает дубликаты по ссылке"""
    
    unique_articles = []
    seen_links = set()
    
    for article in articles:
        if article['link'] not in seen_links:
            seen_links.add(article['link'])
            unique_articles.append(article)
    
    return unique_articles

def main():
    """Главная функция"""
    
    print("🚀 Начинаем сбор новостей...")
    
    all_articles = []
    
    print("\n📰 Новостные сайты:")
    all_articles.extend(collect_from_russian_rss())
    
    print("\n📱 Telegram-каналы:")
    all_articles.extend(collect_from_telegram_channels())
    
    print("\n🔍 Убираем дубликаты...")
    unique_articles = remove_duplicates(all_articles)
    
    os.makedirs('src/content', exist_ok=True)
    
    output_file = 'src/content/news.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_articles, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Собрано {len(unique_articles)} уникальных статей")
    print(f"📁 Сохранено в {output_file}")

if __name__ == "__main__":
    main()