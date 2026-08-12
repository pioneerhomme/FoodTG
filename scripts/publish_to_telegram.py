import json
import requests
import os
import re
import html as html_lib
import trafilatura
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')
QWEN_API_KEY = os.getenv('QWEN_API_KEY', '')

# 👇 ЗАМЕНИТЕ на username вашего канала (например, @my_news_channel)
CHANNEL_USERNAME = "@allnewsin"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

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
    """Убирает эмодзи-префиксы (🖼, 🎬, 📷, 🔥, 📹, 🎥) и лишние пробелы из заголовка"""
    if not title:
        return title
    # Удаляем любые эмодзи в начале строки (Unicode emoji regex)
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F9FF"  # Misc Symbols, Emoticons, etc.
        "\U00002600-\U000027BF"  # Misc symbols
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols Extended-A
        "\U00002702-\U000027B0"
        "]+",
        flags=re.UNICODE
    )
    # Чистим последовательно в начале строки
    cleaned = title.strip()
    while cleaned:
        # Убираем эмодзи в начале
        new_cleaned = emoji_pattern.sub('', cleaned, count=1).strip()
        # Убираем символы вроде 🔥 🖼 🎬 📷
        new_cleaned = re.sub(r'^[🔥🖼🎬📷📹🎥⚡💥]+\s*', '', new_cleaned).strip()
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

def rewrite_with_qwen(title, text):
    if not QWEN_API_KEY:
        print("  ⚠️ QWEN_API_KEY не задан")
        return ""
    
    source_text = limit_text(text, 1500)
    
    prompt = f"""Ты — дерзкий новостной блогер в стиле Telegram-каналов «Топор», «Лентач», «Кровавая Барыня».
Передай суть новости своими словами, с эмоциями, сарказмом, лёгким сленгом.

Правила:
- НЕ повторяй заголовок в тексте
- 2-4 предложения, не больше
- Пиши живо, как будто рассказываешь другу
- Разговорный русский язык
- Никаких канцеляризмов, «стало известно», «появилась информация»
- Сохрани все факты, цифры, имена
- Без хэштегов и эмодзи в тексте
- Не добавляй кавычки вокруг ответа

Заголовок: {title}

Текст:
{source_text}

Переписанный текст:"""
    
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=QWEN_API_KEY,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        )
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "Ты дерзкий русский новостной блогер."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.9
        )
        rewritten = response.choices[0].message.content.strip()
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
        print(f"  🤖 Qwen переписал: {len(rewritten)} символов")
        return rewritten
    except Exception as e:
        print(f"  ⚠️ Qwen ошибка: {e}")
        return ""

def generate_hashtags(article):
    text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
    categories = {
        'технологии': ['смартфон', 'iphone', 'android', 'гаджет', 'робот', 'нейросет', 'хакер'],
        'экономика': ['рубл', 'доллар', 'экономик', 'банк', 'рынок', 'бизнес', 'крипт', 'брикс'],
        'происшествия': ['авари', 'убийств', 'пожар', 'суд', 'арест', 'нож', 'дрон', 'взрыв', 'метамфетамин', 'задержали'],
        'политика': ['путин', 'президент', 'трамп', 'иран', 'саммит', 'дума', 'закон'],
        'общество': ['москв', 'росси', 'школ', 'больниц', 'подмосков', 'курильск', 'демографи'],
        'наука': ['учен', 'космос', 'лун', 'станци', 'амёба'],
        'спорт': ['спорт', 'матч', 'футбол', 'хоккей', 'чемпион'],
        'шоубиз': ['актер', 'фильм', 'пев', 'сериал', 'кино', 'крипипаст', 'джефф', 'паук'],
        'вмире': ['сша', 'кита', 'украин', 'европ', 'герман', 'великобритан', 'иран', 'япон'],
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
        result = requests.post(url, data=data).json()
        return result.get('ok', False)
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
        try:
            files = {'photo': (filename, content, 'image/jpeg')}
            data = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": message, "parse_mode": "HTML"}
            result = requests.post(url, data=data, files=files).json()
            if result.get('ok'):
                print(f"  📤 Фото отправчено через загрузку ({len(content)//1024}KB)")
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
    title = article.get('title_ru', article.get('title', 'Без заголовка'))
    title = clean_title(title)
    
    # 1. Медиа и текст из RSS
    description = article.get('description', '') or article.get('summary', '')
    rss_text = html_to_paragraphs(description)
    rss_image, rss_video = extract_media_from_html(description)
    
    # 2. Полный текст со страницы
    tr_text, tr_image, tr_video = extract_main_content(article['link'])
    
    # 3. Фолбэк на og-теги
    if len(tr_text) < 200:
        og_text, og_image, og_video = extract_og_fallback(article['link'])
        if og_text:
            tr_text = og_text
        if og_image:
            tr_image = og_image
        if og_video:
            tr_video = og_video
    
    # 4. Выбираем лучший текст
    text = tr_text if len(tr_text) > len(rss_text) else rss_text
    
    # 5. Медиа
    image = rss_image or tr_image
    video = rss_video or tr_video
    
    # 6. Переписываем через Qwen
    rewritten = rewrite_with_qwen(title, text)
    final_text = rewritten if rewritten else limit_text(text, 900)
    
    hashtags = generate_hashtags(article)
    safe_title = html_lib.escape(title)
    safe_text = html_lib.escape(final_text)
    
    # Кнопка «Подписаться» со встроенной ссылкой на канал
    subscribe_link = f'<a href="{CHANNEL_LINK}"><b>🔔 Подписаться</b></a>'
    
    message = f"""🔥 <b>{safe_title}</b>

{safe_text}

{subscribe_link}
{hashtags}"""
    
    if (image or video) and len(message) > 1024:
        safe_text = html_lib.escape(limit_text(final_text, max(200, 1000 - len(title) - len(hashtags) - 50)))
        message = f"""🔥 <b>{safe_title}</b>

{safe_text}

{subscribe_link}
{hashtags}"""
    
    return message, image, video

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
    
    articles_to_publish = new_articles[:5]
    if not articles_to_publish:
        print("✅ Нет новых статей для публикации")
        return
    
    success_count = 0
    for i, article in enumerate(articles_to_publish, 1):
        print(f"\n📤 Публикуем {i}/{len(articles_to_publish)}: {article.get('title', '')[:60]}...")
        message, image, video = format_article(article)
        
        ok = False
        if video:
            print("  🎬 Отправляем с видео...")
            ok = send_video(message, video)
        if not ok and image:
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