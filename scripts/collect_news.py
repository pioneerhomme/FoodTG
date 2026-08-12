import feedparser
import requests
import json
import os
from datetime import datetime

def collect_from_russian_rss():
    """Собирает новости из русскоязычных RSS лент"""
    
    # Русскоязычные RSS ленты
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
        {"url": "https://tjournal.ru/rss", "name": "TJ"},
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
            print(f"  📰 Собираем из {feed_info['name']}...")
            feed = feedparser.parse(feed_info['url'])
            
            # Берём 5 последних статей из каждой ленты
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published if hasattr(entry, 'published') else "",
                    "source": feed_info['name'],
                    "language": "ru"
                })
                
        except Exception as e:
            print(f"  ⚠️ Ошибка при обработке {feed_info['name']}: {e}")
    
    return articles

def collect_from_telegram_channels():
    """
    Собирает новости из Telegram каналов через RSS-мосты
    
    Для Telegram каналов используем сервисы-мосты:
    - https://rss.app (бесплатно до 3 каналов)
    - https://telegramposts.com (бесплатно)
    - https://rsshub.app (бесплатный open-source)
    """
    
    # Список Telegram каналов для мониторинга
    # Для каждого нужно создать RSS-ссылку через rss.app или подобный сервис
    telegram_channels = [
        # {"url": "https://rss.app/r/feed/QwpECECOcc6JtXji.xml", "name": "Топор"},
    ]
    
    articles = []
    
    for channel in telegram_channels:
        try:
            print(f"  📱 Собираем из Telegram: {channel['name']}...")
            feed = feedparser.parse(channel['url'])
            
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published if hasattr(entry, 'published') else "",
                    "source": f"TG: {channel['name']}",
                    "language": "ru"
                })
                
        except Exception as e:
            print(f"  ⚠️ Ошибка при обработке {channel['name']}: {e}")
    
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
    
    print("🚀 Начинаем сбор новостей с русскоязычных источников...")
    
    all_articles = []
    
    # Собираем из русских RSS лент
    print("\n📰 Собираем из новостных сайтов:")
    all_articles.extend(collect_from_russian_rss())
    
    # Собираем из Telegram каналов (если настроены)
    print("\n📱 Собираем из Telegram каналов:")
    all_articles.extend(collect_from_telegram_channels())
    
    # Убираем дубликаты
    print("\n🔍 Убираем дубликаты...")
    unique_articles = remove_duplicates(all_articles)
    
    # Создаём папку если её нет
    os.makedirs('src/content', exist_ok=True)
    
    # Сохраняем в файл
    output_file = 'src/content/news.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_articles, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Собрано {len(unique_articles)} уникальных статей")
    print(f"📁 Сохранено в {output_file}")

# Запуск скрипта
if __name__ == "__main__":
    main()