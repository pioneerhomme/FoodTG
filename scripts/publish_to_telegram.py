import json
import requests
import os
import re
import html as html_lib
import trafilatura

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def html_to_paragraphs(html_text):
    """Превращает HTML в текст с абзацами"""
    if not html_text:
        return ""
    text = re.sub(r'(?i)<br\s*/?>', '\n', html_text)
    text = re.sub(r'(?i)</p>', '\n\n', text)
    text = re.sub('<[^<]+?>', '', text)
    text = html_lib.unescape(text)
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(l for l in lines if l)
    return text.strip()

def limit_text(text, limit=800):
    """Обрезает текст по границе абзаца или предложения"""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if '\n\n' in cut:
        cut = cut[:cut.rfind('\n\n')]
    elif '. ' in cut:
        cut = cut[:cut.rfind('. ') + 1]
    return cut.strip() + "..."

def extract_og(html, prop):
    """Достаёт og:description / og:image из HTML страницы"""
    patterns = [
        f'<meta[^>]+property="og:{prop}"[^>]+content="([^"]*)"',
        f'<meta[^>]+content="([^"]*)"[^>]+property="og:{prop}"',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return html_lib.unescape(m.group(1))
    return ""

def extract_image_from_html(html_text):
    m = re.search(r'<img[^>]+src="([^"]+)"', html_text or "")
    return m.group(1) if m else ""

def fetch_article(link):
    """Качает страницу статьи и достаёт полный текст и картинку"""
    try:
        resp = requests.get(link, headers=HEADERS, timeout=20)
        html = resp.text
        image = extract_og(html, 'image')
        # Полный текст статьи через trafilatura
        text = trafilatura.extract(html, include_comments=False, favor_recall=True)
        if not text:
            text = extract_og(html, 'description')
        return (text or ""), image
    except Exception as e:
        print(f"  ⚠️ Не удалось получить страницу: {e}")
        return "", ""

def generate_hashtags(article):
    """Генерирует хэштеги по содержанию"""
    
    text = (article.get('title', '') + ' ' +
            article.get('description', '')).lower()
    
    hashtags = []
    
    categories = {
        'технологии': ['смартфон', 'телефон', 'android', 'iphone', 'компьютер', 'интернет', 'гаджет', 'приложени', 'технолог', 'робот', 'нейросет', 'хакер', 'геймер'],
        'экономика': ['рубл', 'доллар', 'евро', 'экономик', 'банк', 'цен', 'рынок', 'бизнес', 'финанс', 'инфляц', 'крипт', 'брикс', 'миллиардер'],
        'происшествия': ['авари', 'преступ', 'выстрел', 'напал', 'погиб', 'пожар', 'ракетн', 'опасност', 'ранени', 'полици', 'суд', 'арест', 'вор', 'убийств', 'фсин', 'розыск'],
        'политика': ['путин', 'президент', 'правительств', 'дума', 'министр', 'закон', 'депутат', 'кремл', 'чиновник'],
        'общество': ['москв', 'росси', 'россиян', 'школ', 'больниц', 'город', 'жител', 'врач', 'квартир', 'кузбасс'],
        'наука': ['учен', 'исследован', 'открыти', 'космос', 'эксперимент', 'наук'],
        'спорт': ['спорт', 'матч', 'футбол', 'побед', 'атлет', 'олимп', 'хоккей', 'сборн', 'теннис', 'чемпион', 'федерер'],
        'шоубиз': ['актер', 'фильм', 'пев', 'певиц', 'звезд', 'концерт', 'сериал', 'кино', 'модел'],
        'вмире': ['европ', 'сша', 'кита', 'украин', 'нью-йорк', 'мир'],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                hashtags.append('#' + category)
                break
    
    hashtags.extend(['#новости', '#топ'])
    
    return ' '.join(hashtags[:4])

def send_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHANNEL_ID, "text": message, "parse_mode": "HTML"}
    try:
        return requests.post(url, data=data).json().get('ok', False)
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

def send_photo(message, image_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "photo": image_url,
        "caption": message,
        "parse_mode": "HTML"
    }
    try:
        return requests.post(url, data=data).json().get('ok', False)
    except Exception as e:
        print(f"  ❌ Ошибка фото: {e}")
        return False

def format_article(article):
    """Собирает пост как у Топора: картинка + жирный заголовок + текст абзацами"""
    
    title = article.get('title_ru', article.get('title', 'Без заголовка'))
    
    # Текст и картинка из RSS (если есть)
    description = article.get('description', '') or article.get('summary', '')
    text = html_to_paragraphs(description)
    image = extract_image_from_html(description)
    
    # Если текста или картинки нет — качаем страницу статьи
    if len(text) < 100 or not image:
        page_text, page_image = fetch_article(article['link'])
        if len(text) < 100 and page_text:
            text = page_text
        if not image and page_image:
            image = page_image
    
    text = limit_text(text, 800)
    hashtags = generate_hashtags(article)
    
    if text:
        message = f"""🔥 <b>{title}</b>

{text}

{hashtags}"""
    else:
        message = f"""🔥 <b>{title}</b>

{hashtags}"""
    
    # Страховка от лимита Telegram в 1024 символа для подписи к фото
    if image and len(message) > 1024:
        text = limit_text(text, 1024 - len(title) - len(hashtags) - 20)
        message = f"""🔥 <b>{title}</b>

{text}

{hashtags}"""
    
    return message, image

def load_published():
    published_file = 'src/content/published.json'
    if os.path.exists(published_file):
        with open(published_file, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_published(published):
    published_file = 'src/content/published.json'
    with open(published_file, 'w', encoding='utf-8') as f:
        json.dump(list(published), f, ensure_ascii=False, indent=2)

def main():
    print("🚀 Начинаем публикацию в Telegram...")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("❌ Ошибка: секреты не настроены!")
        return
    
    input_file = 'src/content/news_translated.json'
    if not os.path.exists(input_file):
        print("❌ Файл news_translated.json не найден.")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    print(f"📚 Загружено {len(articles)} статей")
    
    published = load_published()
    new_articles = [a for a in articles if a['link'] not in published]
    print(f"🆕 Новых статей: {len(new_articles)}")
    
    articles_to_publish = new_articles[:5]
    
    if not articles_to_publish:
        print("✅ Нет новых статей для публикации")
        return
    
    success_count = 0
    
    for i, article in enumerate(articles_to_publish, 1):
        print(f"\n📤 Публикуем {i}/{len(articles_to_publish)}...")
        
        message, image = format_article(article)
        
        ok = False
        if image:
            print("  🖼 Отправляем с картинкой...")
            ok = send_photo(message, image)
        
        if not ok:
            ok = send_message(message)
        
        if ok:
            published.add(article['link'])
            success_count += 1
            print(f"  ✅ Опубликовано")
        else:
            print(f"  ❌ Не удалось опубликовать")
    
    save_published(published)
    print(f"\n✅ Успешно опубликовано: {success_count}")

if __name__ == "__main__":
    main()