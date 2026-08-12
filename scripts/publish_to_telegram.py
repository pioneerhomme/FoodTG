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

def clean_html(html_text, max_length=400):
    """Removes HTML tags and truncates to the specified length"""
    if not html_text:
        return ""
    clean = re.sub('<[^<]+?>', '', html_text)
    clean = html_lib.unescape(clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if len(clean) > max_length:
        clean = clean[:max_length]
        clean = clean.rsplit(' ', 1)[0] + "..."
    return clean

def extract_og(html, prop):
    """Extracts og:description / og:image from the page's HTML"""
    patterns = [
        f'<meta[^>]+property="og:{prop}"[^>]+content="([^"]*)"',
        f'<meta[^>]+content="([^"]*)"[^>]+property="og:{prop}"',
        f'<meta[^>]+name="twitter:{prop}"[^>]+content="([^"]*)"',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return html_lib.unescape(m.group(1))
    return ""

def fetch_article_meta(link):
    """Fetches the article page and returns (text, image)"""
    try:
        resp = requests.get(link, headers=HEADERS, timeout=15)
        text = extract_og(resp.text, 'description')
        image = extract_og(resp.text, 'image')
        return text, image
    except Exception as e:
        print(f"  ⚠️ Failed to fetch page: {e}")
        return "", ""

def extract_image_from_html(html_text):
    """Extracts the first image from HTML"""
    m = re.search(r'<img[^>]+src="([^"]+)"', html_text or "")
    return m.group(1) if m else ""

def generate_hashtags(article):
    """Generates hashtags based on the content of the news"""
    
    text = (article.get('title', '') + ' ' +
            article.get('description', '')).lower()
    
    hashtags = []
    
    categories = {
        'технологии': ['смартфон', 'телефон', 'android', 'iphone', 'компьютер', 'интернет', 'гаджет', 'приложени', 'технолог', 'робот', 'нейросет', 'хакер'],
        'экономика': ['рубл', 'доллар', 'евро', 'экономик', 'банк', 'цен', 'рынок', 'бизнес', 'финанс', 'инфляц', 'ипотек', 'крипт', 'брикс'],
        'происшествия': ['авари', 'преступ', 'выстрел', 'напал', 'погиб', 'пожар', 'ракетн', 'опасност', 'ранени', 'полици', 'суд', 'арест', 'вор', 'насильник', 'чс'],
        'политика': ['путин', 'президент', 'правительств', 'дума', 'министр', 'закон', 'депутат', 'кремл', 'сенат', 'иран', 'страна'],
        'общество': ['москв', 'росси', 'россиян', 'школ', 'больниц', 'город', 'жител', 'врач', 'учител', 'квартир', 'отел'],
        'наука': ['учен', 'исследован', 'открыти', 'космос', 'эксперимент', 'наук'],
        'спорт': ['спорт', 'матч', 'футбол', 'побед', 'атлет', 'олимп', 'хоккей'],
        'шоубиз': ['актер', 'фильм', 'пев', 'певиц', 'звезд', 'концерт', 'сериал', 'кино', 'модель'],
        'авто': ['автомобил', 'дтп', 'водител', 'машин', 'дорог'],
        'вмире': ['европ', 'сша', 'кита', 'украин', 'нью-йорк', 'мир'],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                hashtags.append('#' + category)
                break
    
    hashtags.extend(['#новости', '#топ'])
    
    return ' '.join(hashtags[:5])

def send_message(message):
    """Sends a text message"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        return response.json().get('ok', False)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def send_photo(message, image_url):
    """Sends a photo with caption"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "photo": image_url,
        "caption": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        return response.json().get('ok', False)
    except Exception as e:
        print(f"  ❌ Error sending photo: {e}")
        return False

def format_article(article):
    """Assembles the post: title + text + hashtags, and an image if available"""
    
    title = article.get('title_ru', article.get('title', 'Без заголовка'))
    
    # Text and image from RSS (if available)
    description = article.get('description', '') or article.get('summary', '')
    clean_desc = clean_html(description)
    image = extract_image_from_html(description)
    
    # If there's no text or image, fetch them from the article page
    if not clean_desc or not image:
        page_text, page_image = fetch_article_meta(article['link'])
        if not clean_desc:
            clean_desc = clean_html(page_text)
        if not image:
            image = page_image
    
    hashtags = generate_hashtags(article)
    
    if clean_desc:
        message = f"""🔥 {title}

{clean_desc}

{hashtags}"""
    else:
        message = f"""🔥 {title}

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
    print("🚀 Starting publication to Telegram...")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("❌ Error: secrets are not configured!")
        return
    
    input_file = 'src/content/news_translated.json'
    if not os.path.exists(input_file):
        print("❌ File news_translated.json not found.")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    print(f"📚 Loaded {len(articles)} articles")
    
    published = load_published()
    new_articles = [a for a in articles if a['link'] not in published]
    print(f"🆕 New articles: {len(new_articles)}")
    
    articles_to_publish = new_articles[:5]
    
    if not articles_to_publish:
        print("✅ No new articles to publish")
        return
    
    success_count = 0
    
    for i, article in enumerate(articles_to_publish, 1):
        print(f"\n📤 Publishing article {i}/{len(articles_to_publish)}...")
        
        message, image = format_article(article)
        
        ok = False
        if image:
            ok = send_photo(message, image)
            print(f"  🖼 Sending with image...")
        
        if not ok:
            ok = send_message(message)
        
        if ok:
            published.add(article['link'])
            success_count += 1
            print(f"  ✅ Published: {article.get('title_ru', article['title'])[:50]}...")
        else:
            print(f"  ❌ Failed to publish")
    
    save_published(published)
    
    print(f"\n✅ Successfully published: {success_count} articles")

if __name__ == "__main__":
    main()