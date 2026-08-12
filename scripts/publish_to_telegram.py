import json
import requests
import os
import re

# Получаем настройки из переменных окружения (из секретов GitHub)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')

def clean_html(html_text, max_length=250):
    """Убирает HTML теги из текста и обрезает до нужной длины"""
    if not html_text:
        return ""
    # Убираем HTML теги
    clean = re.sub('<[^<]+?>', '', html_text)
    # Убираем HTML entities
    clean = re.sub(r'&[a-zA-Z]+;', ' ', clean)
    clean = re.sub(r'&\w+;', ' ', clean)
    # Убираем лишние пробелы и переносы строк
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Обрезаем до нужной длины по границе слова
    if len(clean) > max_length:
        clean = clean[:max_length]
        clean = clean.rsplit(' ', 1)[0] + "..."
    return clean

def generate_hashtags(article):
    """Генерирует хэштеги по содержанию новости"""
    
    text = (article.get('title', '') + ' ' + 
            article.get('description', '') + ' ' + 
            article.get('summary', '')).lower()
    
    hashtags = []
    
    # Категории и ключевые слова
    categories = {
        'технологии': ['смартфон', 'телефон', 'android', 'iphone', 'компьютер', 'ии', 'интернет', 'гаджет', 'приложени', 'технолог', 'робот', 'нейросет', 'хакер'],
        'экономика': ['рубл', 'доллар', 'евро', 'экономик', 'банк', 'цен', 'рынок', 'бизнес', 'финанс', 'инфляц', 'ипотек', 'крипт'],
        'происшествия': ['авари', 'преступ', 'выстрел', 'напал', 'погиб', 'пожар', 'ракетн', 'опасност', 'ранени', 'полици', 'суд', 'арест'],
        'политика': ['путин', 'президент', 'правительств', 'дума', 'министр', 'закон', 'депутат', 'кремл', 'сенат'],
        'общество': ['москв', 'росси', 'россиян', 'школ', 'больниц', 'город', 'жител', 'врач', 'учител'],
        'наука': ['учен', 'исследован', 'открыти', 'космос', 'эксперимент', 'наук'],
        'спорт': ['спорт', 'матч', 'футбол', 'побед', 'атлет', 'олимп', 'хоккей'],
        'шоубиз': ['актер', 'фильм', 'пев', 'певиц', 'звезд', 'концерт', 'сериал', 'кино'],
        'авто': ['автомобил', 'дтп', 'водител', 'машин', 'дорог'],
        'вмире': ['европ', 'сша', 'кита', 'украин', 'мир', 'стран'],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                hashtags.append('#' + category)
                break
    
    # Общие хэштеги для охвата
    hashtags.extend(['#новости', '#топ'])
    
    # Максимум 5 хэштегов
    return ' '.join(hashtags[:5])

def send_to_telegram(message):
    """Отправляет сообщение в Telegram канал"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True  # Без превью, ссылок всё равно нет
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
    """Форматирует статью: заголовок + пересказ + хэштеги, без ссылок"""
    
    title = article.get('title_ru', article.get('title', 'Без заголовка'))
    
    # Краткий пересказ
    description = article.get('description', '') or article.get('summary', '')
    clean_desc = clean_html(description)
    
    # Хэштеги
    hashtags = generate_hashtags(article)
    
    if clean_desc:
        message = f"""🔥 {title}

{clean_desc}

{hashtags}"""
    else:
        message = f"""🔥 {title}

{hashtags}"""
    
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
    
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не задан!")
        return
    
    if not TELEGRAM_CHANNEL_ID:
        print("❌ Ошибка: TELEGRAM_CHANNEL_ID не задан!")
        return
    
    input_file = 'src/content/news_translated.json'
    
    if not os.path.exists(input_file):
        print("❌ Файл news_translated.json не найден.")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    print(f"📚 Загружено {len(articles)} статей")
    
    published = load_published()
    print(f"📝 Уже опубликовано: {len(published)} статей")
    
    new_articles = [a for a in articles if a['link'] not in published]
    print(f"🆕 Новых статей: {len(new_articles)}")
    
    articles_to_publish = new_articles[:5]
    
    if not articles_to_publish:
        print("✅ Нет новых статей для публикации")
        return
    
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
    
    save_published(published)
    
    print(f"\n✅ Успешно опубликовано: {success_count} статей")
    print(f"📊 Всего в канале: {len(published)} статей")

if __name__ == "__main__":
    main()