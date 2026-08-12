import feedparser
import requests
import json
import os
from datetime import datetime

def collect_from_rss():
    """Собирает новости из RSS лент"""
    
    # Список RSS лент для сбора новостей
    feeds = [
        "https://techcrunch.com/feed/",           # TechCrunch - технологии
        "https://www.theverge.com/rss/index.xml", # The Verge - новости технологий
        "https://feeds.feedburner.com/TechCrunch/" # Ещё одна лента TechCrunch
    ]
    
    articles = []
    
    # Проходим по каждой RSS ленте
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            
            # Берём только 5 последних статей из каждой ленты
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published if hasattr(entry, 'published') else "",
                    "source": feed.feed.title if hasattr(feed, 'feed') else "Unknown",
                    "language": "en"
                })
                
        except Exception as e:
            print(f"Ошибка при обработке {feed_url}: {e}")
    
    return articles

def collect_from_hackernews():
    """Собирает новости из Hacker News"""
    
    try:
        # Получаем список топ-новостей
        response = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        story_ids = response.json()[:10]  # Берём только топ-10
        
        articles = []
        
        # Для каждой новости получаем детали
        for story_id in story_ids:
            try:
                story_response = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                )
                story = story_response.json()
                
                # Добавляем только если есть ссылка на статью
                if story.get('url'):
                    articles.append({
                        "title": story.get('title', ''),
                        "link": story.get('url', ''),
                        "published": datetime.fromtimestamp(story.get('time', 0)).isoformat(),
                        "source": "Hacker News",
                        "language": "en"
                    })
                    
            except Exception as e:
                print(f"Ошибка при обработке истории {story_id}: {e}")
        
        return articles
        
    except Exception as e:
        print(f"Ошибка при получении Hacker News: {e}")
        return []

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
    
    # Собираем из всех источников
    all_articles = []
    
    print("📰 Собираем из RSS лент...")
    all_articles.extend(collect_from_rss())
    
    print("🔥 Собираем из Hacker News...")
    all_articles.extend(collect_from_hackernews())
    
    # Убираем дубликаты
    print("🔍 Убираем дубликаты...")
    unique_articles = remove_duplicates(all_articles)
    
    # Создаём папку если её нет
    os.makedirs('src/content', exist_ok=True)
    
    # Сохраняем в файл
    output_file = 'src/content/news.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_articles, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Собрано {len(unique_articles)} уникальных статей")
    print(f"📁 Сохранено в {output_file}")

# Запуск скрипта
if __name__ == "__main__":
    main()