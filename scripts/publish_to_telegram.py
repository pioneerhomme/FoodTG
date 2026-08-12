import json
import requests
import os
import re
import html as html_lib

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
    return '\n\n'.join(l for l in lines if l).strip()

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

def clean_markdown(md):
    """Чистит markdown до обычного текста с абзацами"""
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', md)          # убрать картинки
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)    # ссылки → текст
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.M)      # убрать #
    text = re.sub(r'[*_`>|]', '', text)                     # убрать форматирование
    text = html_lib.unescape(text)
    # одиночные переносы → пробел, тройные → двойные
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # убрать служебные строки Jina
    lines = [l for l in text.split('\n')
             if l.strip() and not l.strip().startswith(('Title:', 'URL Source:', 'Markdown Content:', 'Published Time:'))]
    return '\n\n'.join(lines).strip()

def fetch_via_jina(link):
    """Получает статью через Jina Reader (обходит блокировки)"""
    try:
        resp = requests.get(f"https://r.jina.ai/{link}",
                            headers={"Accept": "text/plain"}, timeout=30)
        print(f"  🔎 Jina: статус {resp.status_code}")
        if resp.status_code == 200:
            md = resp.text
            images = re.findall(r'!\[[^\]]*\]\((https?://[^)\s]+)', md)
            image = images[0] if images else ""
            text = clean_markdown(md)
            print(f"  🔎 Jina: текст {len(text)} символов, картинка: {'да' if image else 'нет'}")
            return text, image
    except Exception as e:
        print(f"  ⚠️ Jina ошибка: {e}")
    return "", ""

def fetch_direct(link):
    """Запасной вариант: прямое получение og-тегов"""
    try:
        resp = requests.get(link, headers=HEADERS, timeout=15)
        print(f"  🔎 Прямой запрос: статус {resp.status_code}")
        html = resp.text
        image_m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', html, re.IGNORECASE)
        desc_m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', html, re.IGNORECASE)
        image = html_lib.unescape(image_m.group(1)) if image_m else ""
        text = html_lib.unescape(desc_m.group(1)) if desc_m else ""
        return text, image
    except Exception as e:
        print(f"  ⚠️ Прямой запрос ошибка: {e}")
        return "", ""

def extract_image_from_html(html_text):
    m = re.search(r'<img[^>]+src="([^"]+)"', html_text or "")
    return m.group(1) if m else ""

def generate_hashtags(article):
    """Генерирует хэштеги по содержанию"""
    text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
    hashtags = []
    categories = {
        'технологии': ['смартфон', 'телефон', 'android', 'iphone', 'компьютер', 'интернет', 'гаджет', 'приложени', 'технолог', 'робот', 'нейросет', 'хакер', 'геймер'],
        'экономика': ['рубл', 'доллар', 'евро', 'экономик', 'банк', 'цен', 'рынок', 'бизнес', 'финанс', 'инфляц', 'крипт', 'брикс', 'миллиардер', 'яхт'],
        'происшествия': ['авари', 'преступ', 'выстрел', 'напал', 'погиб', 'пожар', 'ракетн', 'опасност', 'ранени', 'полици', 'суд', 'арест', 'вор', 'убийств', 'фсин', 'розыск', 'шаурм', 'отравл'],
        'политика': ['путин', 'президент', 'правительств', 'дума', 'министр', 'закон', 'депутат', 'кремл', 'чиновник', 'переговор', 'украин'],
        'общество': ['москв', 'росси', 'россиян', 'школ', 'больниц', 'город', 'жител', 'врач', 'квартир', 'подросток'],
        'наука': ['учен', 'исследован', 'открыти', 'космос', 'эксперимент', 'наук'],
        'спорт': ['спорт', 'матч', 'футбол', 'побед', 'атлет', 'олимп', 'хоккей', 'сборн', 'теннис', 'чемпион'],
        'шоубиз': ['актер', 'фильм', 'пев', 'певиц', 'звезд', 'концерт', 'сериал', 'кино', 'модел'],
        'вмире': ['европ', 'сша', 'кита', 'украин', 'нью-йорк', 'мир', 'запад'],
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
    """Собирает пост: картинка + жирный заголовок + текст абзацами"""
    title = article.get('title_ru', article.get('title', 'Без заголовка'))
    
    # 1. Текст и картинка из RSS (если есть)
    description = article.get('description', '') or article.get('summary', '')
    text = html_to_paragraphs(description)
    image = extract_image_from_html(description)
    
    # 2. Если мало текста или нет картинки — Jina Reader
    if len(text) < 100 or not image:
        jina_text, jina_image = fetch_via_jina(article['link'])
        if len(text) < 100 and jina_text:
            text = jina_text
        if not image and jina_image:
            image = jina_image
    
    # 3. Запасной вариант — прямой запрос
    if len(text) < 100 or not image:
        direct_text, direct_image = fetch_direct(article['link'])
        if len(text) < 100 and direct_text:
            text = direct_text
        if not image and direct_image:
            image = direct_image
    
    text = limit_text(text, 800)
    hashtags = generate_hashtags(article)
    
    message = f"""🔥 <b>{title}</b>

{text}

{hashtags}""" if text else f"""🔥 <b>{title}</b>

{hashtags}"""
    
    # Страховка от лимита Telegram 1024 символа для подписи к фото
    if image and len(message) > 1024:
        text = limit_text(text, max(200, 1000 - len(title) - len(hashtags)))
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