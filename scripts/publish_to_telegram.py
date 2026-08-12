import json
import requests
import os
import re
import html as html_lib
import trafilatura
from bs4 import BeautifulSoup
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')
QWEN_API_KEY = os.getenv('QWEN_API_KEY', '')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')

CHANNEL_USERNAME = "@ignisnovosti"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

WATERMARK_SOURCES = ['mash', 'baza', '112', 'lifeshot', 'шторм', 'readovka', 'барыня']

AD_MARKERS = [
    'подпишись', 'подписывайся', 'подписывайтесь', 'подписаться на',
    'наш канал', 'канал про', 'мой канал', 'этот канал', 'наши каналы',
    'реклама', 'партнер', 'партнёр', 'коллаб', 'пиар', 'промокод',
    'скидка', 'акция', 'розыгрыш', 'жми', 'переходи', 'по ссылке',
    'приватный чат', 'приватным чатом', 'наш чат', 'в наш чат',
    't.me/', 'te.me/', 'tele.click', 'vk.com/', 'youtube.com/',
]

JUNK_PATTERNS = [
    'Эксклюзивы', 'Статьи Фото', 'Спецпроекты', 'Исследования', 'Мини-игры',
    'Архив', 'Лента добра', 'Хочешь видеть', 'Вернуться в обычную',
    'Войти', 'Регистрация', 'Реклама', 'ООО «', 'erid:', 'VK Видео', 'VK - ВК',
    'Силовые структуры', 'ВсеСледствие', 'Криминал', 'Полиция',
    'Редактор отдела', 'редактор отдела', 'Читайте также', 'Новости партнеров',
    'Подписывайтесь', 'ВсеПолитика', 'ВсеНаука', 'ВсеОбщество', 'Мир Все',
    'Россия Все', 'Фото:', 'Фото :', 'Из жизни', 'Наука и техника',
    'ТАСС собрал', 'Сайт ТАСС', 'Редакция сайта',
]

def html_to_paragraphs(html_text):
    if not html_text:
        return ""
    text = re.sub(r'(?i)<br\s*/?>', '\n', html_text)
    text = re.sub(r'(?i)</p>', '\n\n', text)
    text = re.sub('<[^<]+?>', '', text)
    text = html_lib.unescape(text)
    lines = [line.strip() for line in text.split('\n')]
    return '\n\n'.join(l for l in lines if l).strip()

def remove_links(text):
    if not text:
        return ""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r't\.me/\S+', '', text)
    text = re.sub(r'@[a-zA-Z_][a-zA-Z0-9_]{3,}', '', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def is_ad(title, description):
    combined = (title + ' ' + description).lower()
    hits = sum(1 for m in AD_MARKERS if m in combined)
    return hits >= 2

def validate_article(article):
    title = (article.get('title', '') or '').strip()
    description = article.get('description', '') or article.get('summary', '') or ''
    text = remove_links(html_to_paragraphs(description))
    is_tg = article.get('source', '').startswith('TG:')
    
    if is_ad(title, description):
        return False, "реклама"
    
    if is_tg:
        if len(text) < 80:
            return False, "мало текста"
        if re.match(r'^https?://', title) and len(text) < 150:
            return False, "заголовок-ссылка"
    else:
        if len(title) < 10:
            return False, "пустой заголовок"
    
    return True, ""

def limit_text(text, limit=1500):
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if '\n\n' in cut:
        cut = cut[:cut.rfind('\n\n')]
    elif '. ' in cut:
        cut = cut[:cut.rfind('. ') + 1]
    return cut.strip() + "..."

def is_junk(line):
    line = line.strip()
    if not line:
        return True
    if len(line) < 25:
        return True
    if re.match(r'^\d{1,2}:\d{2},', line):
        return True
    if re.match(r'^[А-Я][а-я]+\s+[А-Я][а-я]+(\s*\([^)]*\))?$', line):
        return True
    for pattern in JUNK_PATTERNS:
        if pattern in line:
            return True
    return False

def clean_text(text):
    if not text:
        return ""
    paragraphs = text.split('\n\n')
    clean = []
    for p in paragraphs:
        lines = [l for l in p.split('\n') if not is_junk(l)]
        p = '\n'.join(lines).strip()
        if p and len(p) > 20:
            clean.append(p)
    return '\n\n'.join(clean)

def clean_title(title):
    if not title:
        return title
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F9FF"
        "\U00002600-\U000027BF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002702-\U000027B0"
        "]+",
        flags=re.UNICODE
    )
    cleaned = title.strip()
    while cleaned:
        new_cleaned = emoji_pattern.sub('', cleaned, count=1).strip()
        new_cleaned = re.sub(r'^[🔥💥]+\s*', '', new_cleaned).strip()
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned
    return cleaned

def extract_media_from_html(html_text):
    html_text = html_text or ""
    video = ""
    m = re.search(r'<video[^>]+src="([^"]+)"', html_text)
    if m:
        video = m.group(1)
    else:
        m = re.search(r'<source[^>]+src="([^"]+)"', html_text)
        if m:
            video = m.group(1)
    image = ""
    m = re.search(r'<img[^>]+src="([^"]+)"', html_text)
    if m:
        image = m.group(1)
    else:
        m = re.search(r'poster="([^"]+)"', html_text)
        if m:
            image = m.group(1)
    return image, video

def extract_main_content(link):
    try:
        resp = requests.get(link, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return "", "", ""
        soup = BeautifulSoup(resp.text, 'lxml')
        og_img = soup.find('meta', property='og:image')
        og_vid = soup.find('meta', property='og:video')
        image = og_img['content'] if og_img and og_img.get('content') else ""
        video = og_vid['content'] if og_vid and og_vid.get('content') else ""
        text = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_recall=False,
        )
        if text:
            text = clean_text(text)
            print(f"  🎯 Trafilatura: текст {len(text)} символов, картинка: {'да' if image else 'нет'}")
            return text, image, video
    except Exception as e:
        print(f"  ⚠️ Trafilatura ошибка: {e}")
    return "", "", ""

def extract_og_fallback(link):
    try:
        resp = requests.get(link, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'lxml')
        desc = soup.find('meta', property='og:description')
        img = soup.find('meta', property='og:image')
        vid = soup.find('meta', property='og:video')
        text = desc['content'] if desc and desc.get('content') else ""
        image = img['content'] if img and img.get('content') else ""
        video = vid['content'] if vid and vid.get('content') else ""
        if text:
            print(f"  ℹ️ OG-фолбэк: текст {len(text)} символов")
        return text, image, video
    except Exception:
        return "", "", ""

def download_media(url):
    if not url:
        return None, None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if resp.status_code != 200:
            return None, None
        content_type = resp.headers.get('content-type', '')
        if 'video' in content_type:
            ext = 'mp4'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            ext = 'jpg'
        elif 'png' in content_type:
            ext = 'png'
        elif 'gif' in content_type:
            ext = 'gif'
        else:
            if '.mp4' in url:
                ext = 'mp4'
            elif '.jpg' in url or '.jpeg' in url:
                ext = 'jpg'
            elif '.png' in url:
                ext = 'png'
            else:
                ext = 'jpg'
        return resp.content, f"media.{ext}"
    except Exception as e:
        print(f"  ⚠️ Не удалось скачать медиа: {e}")
        return None, None

def get_qwen_client():
    from openai import OpenAI
    return OpenAI(
        api_key=QWEN_API_KEY,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )

def generate_short_title(title, text):
    """ИИ сжимает заголовок до сути: 3-7 слов"""
    if not QWEN_API_KEY:
        return ""
    try:
        client = get_qwen_client()
        response = client.chat.completions.create(
            model="qwen-turbo",
            messages=[{"role": "user", "content":
                f"Сожми заголовок новости до 3-7 слов, передав главную суть. Без кавычек, эмодзи и точек.\n\nЗаголовок: {title}\nТекст: {text[:500]}"}],
            max_tokens=30,
            temperature=0.7
        )
        t = response.choices[0].message.content.strip().strip('"«».')
        t = remove_links(t)
        if 8 <= len(t) <= 80:
            print(f"  ✂️ Короткий заголовок: {t}")
            return t
    except Exception as e:
        print(f"  ⚠️ Qwen заголовок ошибка: {e}")
    return ""

def get_stock_keywords(title):
    if not QWEN_API_KEY:
        return ""
    try:
        client = get_qwen_client()
        response = client.chat.completions.create(
            model="qwen-turbo",
            messages=[{"role": "user", "content":
                f"Write 2-3 English words describing this news as a photo search query for a stock photo. Reply with words only, nothing else.\n\nNews: {title}"}],
            max_tokens=30,
            temperature=0.5
        )
        keywords = response.choices[0].message.content.strip()
        keywords = re.sub(r'[^a-zA-Z\s]', '', keywords).strip()
        return keywords
    except Exception as e:
        print(f"  ⚠️ Qwen keywords ошибка: {e}")
        return ""

def get_stock_image(title):
    if not PEXELS_API_KEY:
        return ""
    keywords = get_stock_keywords(title)
    if not keywords:
        return ""
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": keywords, "per_page": 1, "orientation": "landscape"},
            timeout=15
        )
        photos = resp.json().get('photos', [])
        if photos:
            print(f"  🎨 Сток Pexels: {keywords}")
            return photos[0]['src']['large']
    except Exception as e:
        print(f"  ⚠️ Pexels ошибка: {e}")
    return ""

def is_watermarked_source(article):
    source = article.get('source', '').lower()
    return any(wm in source for wm in WATERMARK_SOURCES)

def score_article(title):
    if not QWEN_API_KEY:
        return 5
    try:
        client = get_qwen_client()
        response = client.chat.completions.create(
            model="qwen-turbo",
            messages=[{"role": "user", "content":
                f"Оцени от 1 до 10, насколько эта новость интересна и резонансна для широкой аудитории (актуальность, эмоциональность, необычность). Ответь одним числом.\n\nНовость: {title}"}],
            max_tokens=5,
            temperature=0.3
        )
        m = re.search(r'\d+', response.choices[0].message.content)
        score = int(m.group()) if m else 5
        return max(1, min(10, score))
    except Exception:
        return 5

def rewrite_with_qwen(title, text):
    if not QWEN_API_KEY:
        print("  ⚠️ QWEN_API_KEY не задан")
        return ""
    source_text = limit_text(text, 1200)
    if len(source_text) < 80:
        return ""
    prompt = f"""Ты — ироничный новостной блогер в стиле Telegram-каналов «Топор» и «Лентач».
Передай суть новости своими словами с ЛЁГКИМ сарказмом и доброй иронией — но БЕЗ грубости и цинизма.

Правила:
- РОВНО 2-3 предложения, коротко и ёмко
- Если новость о смерти, трагедии, преступлении с жертвами, катастрофе или болезни — пиши СДЕРЖАННО и без сарказма
- Пиши ТОЛЬКО о фактах из текста, не выдумывай и не обобщай
- НЕ повторяй заголовок в тексте
- Живой разговорный язык, лёгкая ирония над ситуациями и чиновниками, но не над людьми
- Никаких канцеляризмов, «стало известно», «появилась информация»
- Сохрани главные факты, цифры, имена
- НЕ добавляй никакие ссылки, адреса сайтов, @username
- Без хэштегов и эмодзи в тексте
- Не добавляй кавычки вокруг ответа

Заголовок: {title}

Текст:
{source_text}

Переписанный текст:"""
    try:
        client = get_qwen_client()
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "Ты ироничный, но добрый русский новостной блогер. Над трагедиями не шутишь. Ссылки не добавляешь. Пишешь КОРОТКО: 2-3 предложения."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.85
        )
        rewritten = response.choices[0].message.content.strip()
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
        rewritten = remove_links(rewritten)
        print(f"  🤖 Qwen переписал: {len(rewritten)} символов")
        return rewritten
    except Exception as e:
        print(f"  ⚠️ Qwen ошибка: {e}")
        return ""

def generate_hashtags(article):
    text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
    categories = {
        'технологии': ['смартфон', 'iphone', 'android', 'гаджет', 'робот', 'нейросет', 'хакер', 'телескоп', 'хаббл', 'xbox', 'playstation', 'genshin'],
        'экономика': ['рубл', 'доллар', 'экономик', 'банк', 'рынок', 'бизнес', 'крипт', 'брикс', 'взятк', 'прибыл', 'выручк', 'акци', 'облигац', 'курс'],
        'происшествия': ['авари', 'убийств', 'пожар', 'суд', 'арест', 'нож', 'дрон', 'взрыв', 'метамфетамин', 'задержали', 'затопило', 'поток', 'колони', 'иск', 'землетрясени'],
        'политика': ['путин', 'президент', 'трамп', 'иран', 'саммит', 'дума', 'закон', 'депутат', 'милонов', 'мчс', 'мид'],
        'общество': ['москв', 'росси', 'школ', 'больниц', 'подмосков', 'курильск', 'демографи', 'ростов', 'казан', 'саратов', 'коммуналк'],
        'наука': ['учен', 'космос', 'лун', 'станци', 'амёба', 'юпитер', 'сияние', 'хаббл', 'черная дыра', 'геном'],
        'спорт': ['спорт', 'матч', 'футбол', 'хоккей', 'чемпион', 'махаев', 'бой'],
        'шоубиз': ['актер', 'фильм', 'пев', 'сериал', 'кино', 'крипипаст', 'джефф', 'паук', 'альбом', 'группа'],
        'вмире': ['сша', 'кита', 'украин', 'европ', 'герман', 'великобритан', 'иран', 'япон', 'литва', 'польша', 'марокко', 'саудов'],
    }
    hashtags = []
    for category, keywords in categories.items():
        for kw in keywords:
            if kw in text:
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
    data = {"chat_id": TELEGRAM_CHANNEL_ID, "photo": image_url, "caption": message, "parse_mode": "HTML"}
    try:
        result = requests.post(url, data=data).json()
        if result.get('ok'):
            return True
        else:
            print(f"  ⚠️ Photo URL rejected: {result.get('description', '')[:80]}")
    except Exception as e:
        print(f"  ⚠️ Photo URL error: {e}")
    content, filename = download_media(image_url)
    if content:
        if b'<html' in content[:200].lower():
            print("  ⚠️ Скачалась HTML-страница вместо фото")
            return False
        try:
            files = {'photo': (filename, content, 'image/jpeg')}
            data = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": message, "parse_mode": "HTML"}
            result = requests.post(url, data=data, files=files).json()
            if result.get('ok'):
                print(f"  📤 Фото отправлено через загрузку ({len(content)//1024}KB)")
                return True
            else:
                print(f"  ❌ Photo upload failed: {result.get('description', '')[:80]}")
        except Exception as e:
            print(f"  ❌ Photo upload error: {e}")
    return False

def send_video(message, video_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    data = {"chat_id": TELEGRAM_CHANNEL_ID, "video": video_url, "caption": message, "parse_mode": "HTML"}
    try:
        result = requests.post(url, data=data).json()
        if result.get('ok'):
            return True
        else:
            print(f"  ⚠️ Video URL rejected: {result.get('description', '')[:80]}")
    except Exception as e:
        print(f"  ⚠️ Video URL error: {e}")
    content, filename = download_media(video_url)
    if content:
        if len(content) > 50 * 1024 * 1024:
            print(f"  ⚠️ Видео слишком большое ({len(content)//1024//1024}MB)")
            return False
        try:
            files = {'video': (filename, content, 'video/mp4')}
            data = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": message, "parse_mode": "HTML"}
            result = requests.post(url, data=data, files=files).json()
            if result.get('ok'):
                print(f"  📤 Видео отправлено через загрузку ({len(content)//1024}KB)")
                return True
            else:
                print(f"  ❌ Video upload failed: {result.get('description', '')[:80]}")
        except Exception as e:
            print(f"  ❌ Video upload error: {e}")
    return False

def format_article(article):
    is_tg = article.get('source', '').startswith('TG:')
    dirty = is_watermarked_source(article)
    
    description = article.get('description', '') or article.get('summary', '')
    rss_text = remove_links(html_to_paragraphs(description))
    rss_image, rss_video = extract_media_from_html(description)
    
    if is_tg:
        text = rss_text
        image = rss_image
        video = rss_video
    else:
        tr_text, tr_image, tr_video = extract_main_content(article['link'])
        if len(tr_text) < 200:
            og_text, og_image, og_video = extract_og_fallback(article['link'])
            if og_text:
                tr_text = og_text
            if og_image:
                tr_image = og_image
            if og_video:
                tr_video = og_video
        text = tr_text if len(tr_text) > len(rss_text) else rss_text
        image = rss_image or tr_image
        video = rss_video or tr_video
    
    if dirty:
        video = ""
        image = ""
        print("  🚫 Источник с водяными знаками: медиа не берём")
    
    title = clean_title(article.get('title_ru', article.get('title', '')))
    title = remove_links(title)
    if not title or len(title) < 10:
        first = re.split(r'[.!?\n]', text, 1)[0].strip()
        title = first[:100] if first else 'Новости дня'
    
    # КОРОТКИЙ ЗАГОЛОВОК от ИИ
    short = generate_short_title(title, text)
    if short:
        title = short
    
    if not image and not video:
        stock = get_stock_image(title)
        if stock:
            image = stock
    
    rewritten = rewrite_with_qwen(title, text)
    final_text = rewritten if rewritten else limit_text(text, 450)
    
    hashtags = generate_hashtags(article)
    safe_title = html_lib.escape(title)
    safe_text = html_lib.escape(final_text)
    
    subscribe_link = f'<a href="{CHANNEL_LINK}"><b>🔔 Подписаться</b></a>'
    
    message = f"""🔥 <b>{safe_title}</b>

{safe_text}

{subscribe_link}
{hashtags}"""
    
    return message, image, video, final_text, hashtags

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

def load_site_feed():
    feed_file = 'src/content/site_feed.json'
    if os.path.exists(feed_file):
        try:
            with open(feed_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_site_feed(feed):
    feed_file = 'src/content/site_feed.json'
    with open(feed_file, 'w', encoding='utf-8') as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

def main():
    print("🚀 Начинаем публикацию в Telegram...")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("❌ Telegram секреты не настроены!")
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
    
    clean_articles = []
    for a in new_articles:
        ok, reason = validate_article(a)
        if ok:
            clean_articles.append(a)
        else:
            print(f"  🚫 Пропускаем ({reason}): {a.get('title', '')[:60]}")
    print(f"✅ После фильтра: {len(clean_articles)} статей")
    
    candidates = clean_articles[:20]
    scored = []
    for a in candidates:
        source = a.get('source', '').lower()
        is_topor = 'топор' in source
        description = a.get('description', '') or ''
        has_image, has_video = extract_media_from_html(description)
        has_clean_media = (has_image or has_video) and not is_watermarked_source(a)
        
        score = score_article(a.get('title', ''))
        bonus = (3 if is_topor else 0) + (2 if has_clean_media else 0)
        total = score + bonus
        scored.append((total, a))
        print(f"  ⭐ {a.get('title', '')[:40]}... → {score} + бонус {bonus} = {total}")
    
    scored.sort(key=lambda x: x[0], reverse=True)
    articles_to_publish = [a for _, a in scored[:5]]
    
    if not articles_to_publish:
        print("✅ Нет новых статей для публикации")
        return
    
    site_feed = load_site_feed()
    success_count = 0
    
    for i, article in enumerate(articles_to_publish, 1):
        print(f"\n📤 Публикуем {i}/{len(articles_to_publish)}: {article.get('title', '')[:60]}...")
        message, image, video, final_text, hashtags = format_article(article)
        
        ok = False
        if video:
            print("  🎬 Отправляем с видео...")
            ok = send_video(message, video)
        if not ok and image:
            print("  🖼 Отправляем с картинкой...")
            ok = send_photo(message, image)
        if not ok and not video:
            stock = get_stock_image(article.get('title', ''))
            if stock:
                print("  🎨 Пробуем сток вместо битого фото...")
                ok = send_photo(message, stock)
                image = stock
        if not ok:
            ok = send_message(message)
        
        if ok:
            published.add(article['link'])
            success_count += 1
            site_feed.insert(0, {
                "title": html_lib.escape(clean_title(article.get('title', ''))),
                "text": html_lib.escape(final_text),
                "image": image or "",
                "hashtags": hashtags,
                "time": datetime.now().isoformat()
            })
            print(f"  ✅ Опубликовано")
        else:
            print(f"  ❌ Не удалось опубликовать")
    
    site_feed = site_feed[:60]
    save_site_feed(site_feed)
    save_published(published)
    print(f"\n✅ Успешно опубликовано: {success_count}")
    print(f"🌐 Лента сайта: {len(site_feed)} постов")

if __name__ == "__main__":
    main()