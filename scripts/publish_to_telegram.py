import json
import requests
import os
from datetime import datetime

# Получаем настройки из переменных окружения (из секретов GitHub)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')

def send_to_telegram(message):
    """Отправляет сообщение в Telegram канал"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False  # Показывать превью ссылок
    }
    
    try:
        response = requests.post(url, data=data)
        result = response.json()
        
        if result.get('ok'):
            return True
        else:
            print(f"  ❌ Ошибка Telegram: {result.get('description', 'Неизвестная ошибка')}")
            return False
            
    except Exception as e:
        print(f"  ❌ Ошибка при отправке: {e}")
        return False

def format_article(article):
    """Форматирует статью для публикации"""
    
    # Используем переведённый заголовок если есть, иначе оригинальный
    title = article.get('title_ru', article.get('title', 'Без заголовка'))
    
    # Формируем сообщение
    message = f"""📰 <b>{title}</b>

🔗 <a href="{article['link']}">Читать оригинал</a>

📍 Источник: {article.get('source', 'Неизвестен')}
🕐 {article.get('published', '')[:16] if article.get('published') else ''}

#новости #ai"""
    
    return message

def load_published():
    """Загружает список уже опубликованных статей"""
    
    published_file = 'src/content/published.json'
    
    if os.path.exists(published_file):
        with open(published_file, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    
    return set()

def save_published(published):
    """Сохраняет список опубликованных статей"""
    
    published_file = 'src/content/published.json'
    
    with open(published_file, 'w', encoding='utf-8') as f:
        json.dump(list(published), f, ensure_ascii=False, indent=2)

def main():
    """Главная функция"""
    
    print("🚀 Начинаем публикацию в Telegram...")
    
    # Проверяем настройки
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не задан!")
        print("   Добавьте секрет в GitHub: Settings → Secrets → Actions")
        return
    
    if not TELEGRAM_CHANNEL_ID:
        print("❌ Ошибка: TELEGRAM_CHANNEL_ID не задан!")
        print("   Добавьте секрет в GitHub: Settings → Secrets → Actions")
        return
    
    # Читаем переведённые новости
    input_file = 'src/content/news_translated.json'
    
    if not os.path.exists(input_file):
        print("❌ Файл news_translated.json не найден.")
        print("   Сначала запустите collect_news.py и translate_news.py")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    print(f"📚 Загружено {len(articles)} статей")
    
    # Загружаем список уже опубликованных
    published = load_published()
    print(f"📝 Уже опубликовано: {len(published)} статей")
    
    # Фильтруем новые статьи
    new_articles = [a for a in articles if a['link'] not in published]
    print(f"🆕 Новых статей: {len(new_articles)}")
    
    # Публикуем только первые 5 новых статей (чтобы не спамить)
    articles_to_publish = new_articles[:5]
    
    if not articles_to_publish:
        print("✅ Нет новых статей для публикации")
        return
    
    # Публикуем статьи
    success_count = 0
    
    for i, article in enumerate(articles_to_publish, 1):
        print(f"\n📤 Публикуем статью {i}/{len(articles_to_publish)}...")
        
        message = format_article(article)
        
        if send_to_telegram(message):
            published.add(article['link'])
            success_count += 1
            print(f"  ✅ Опубликовано: {article.get('title_ru', article['title'])[:50]}...")
        else:
            print(f"  ❌ Не удалось опубликовать")
    
    # Сохраняем обновлённый список опубликованных
    save_published(published)
    
    print(f"\n✅ Успешно опубликовано: {success_count} статей")
    print(f"📊 Всего в канале: {len(published)} статей")

# Запуск скрипта
if __name__ == "__main__":
    main()