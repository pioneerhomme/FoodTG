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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

# Мусорные строки
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
    # Дата вида "15:52, 12 августа 2026"
    if re.match(r'^\d{1,2}:\d{2},', line):
        return True
    # Имя-фамилия редактора
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

def extract_main_content(link):
    """Основной метод: trafilatura + жёсткая очистка"""
    try:
        resp = requests.get(link, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return "", ""
        
        # Картинка из og:image
        soup = BeautifulSoup(resp.text, 'lxml')
        og_img = soup.find('meta', property='og:image')
        image = og_img['content'] if og_img and og_img.get('content') else ""
        
        # Текст через trafilatura (специализирован для отделения контента от мусора)
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
            return text, image
    except Exception as e:
        print(f"  ⚠️ Trafilatura ошибка: {e}")
    return "", ""

def extract_og_fallback(link):
    """Фолбэк: только og:description + og:image (всегда чистый лид)"""
    try:
        resp = requests.get(link, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'lxml')
        desc = soup.find('meta', property='og:description')
        img = soup.find('meta', property='og:image')
        text = desc['content'] if desc and desc.get('content') else ""
        image = img['content'] if img and img.get('content') else ""
        if text:
            print(f"  ℹ️ OG-фолбэк: текст {len(text)} символов")
        return text, image
    except Exception:
        return "", ""

def extract_image_from_html(html_text):
    m = re.search(r'<img[^>]+src="([^"]+)"', html_text or "")
    return m.group(1) if m else ""

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
        'происшествия': ['авари', 'убийств', 'пожар', 'суд', 'арест', 'нож', 'дрон', 'взрыв'],
        'политика': ['путин', 'президент', 'трамп', 'иран', 'саммит', 'дума', 'закон'],
        'общество': ['москв', 'росси', 'школ', 'больниц', 'подмосков', 'курильск'],
        'наука': ['учен', 'космос', 'лун', 'станци'],
        'спорт': ['спорт', 'матч', 'футбол', 'хоккей', 'чемпион'],
        'шоубиз': ['актер', 'фильм', 'пев', 'сериал', 'кино'],
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
        return requests.post(url, data=data).json().get('ok', False)
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

def send_photo(message, image_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {"chat_id": TELEGRAM_CHANNEL_ID, "photo": image_url, "caption": message, "parse_mode": "HTML"}
    try:
        return requests.post(url, data=data).json().get('ok', False)
    except Exception as e:
        print(f"  ❌ Ошибка фото: {e}")
        return False

def format_article(article):
    title = article.get('title_ru', article.get('title', 'Без заголовка'))
    
    # 1. Текст из RSS (всегда чистый лид)
    description = article.get('description', '') or article.get('summary', '')
    rss_text = html_to_paragraphs(description)
    rss_image = extract_image_from_html(description)
    
    # 2. Полный текст через trafilatura
    tr_text, tr_image = extract_main_content(article['link'])
    
    # 3. Если trafilatura не дал достаточно — фолбэк на og:description
    if len(tr_text) < 200:
        og_text, og_image = extract_og_fallback(article['link'])
        if og_text:
            tr_text = og_text
        if og_image:
            tr_image = og_image
    
    # 4. Выбираем лучший текст
    text = tr_text if len(tr_text) > len(rss_text) else rss_text
    image = tr_image or rss_image
    if not image:
        _, og_image = extract_og_fallback(article['link'])
        image = og_image
    
    # 5. Переписываем через Qwen
    rewritten = rewrite_with_qwen(title, text)
    final_text = rewritten if rewritten else limit_text(text, 900)
    
    hashtags = generate_hashtags(article)
    safe_title = html_lib.escape(title)
    safe_text = html_lib.escape(final_text)
    
    message = f"""🔥 <b>{safe_title}</b>

{safe_text}

{hashtags}"""
    
    if image and len(message) > 1024:
        safe_text = html_lib.escape(limit_text(final_text, max(200, 1000 - len(title) - len(hashtags))))
        message = f"""🔥 <b>{safe_title}</b>

{safe_text}

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