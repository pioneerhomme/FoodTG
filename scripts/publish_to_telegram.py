import json
import requests
import os
import re
import html as html_lib
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')
QWEN_API_KEY = os.getenv('QWEN_API_KEY', '')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')

POSTS_PER_RUN = 5

CHANNEL_USERNAME = "@ignisnovosti"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

SKIP_MARKERS = [
    'подпишись', 'подписывайся', 'наш канал', 'реклама', 'партнер', 'партнёр',
    'промокод', 'розыгрыш', 'приватный чат', 't.me/', 'vk.com/', 'youtube.com/',
    'ozon.ru', 'wildberries', 'max.ru', 'по ссылке', 'жми',
    'угадайте блюдо', 'угадайте по', 'ответ в комментариях', 'пишите в комментариях',
    'отвечаю на вопросы', 'ответы на вопросы', 'карточки', 'карточк',
]

JUNK_PATTERNS = [
    'Эксклюзивы', 'Реклама', 'erid:', 'VK Видео',
    'Подписывайтесь', 'Читайте также',
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

def should_skip(article):
    """Пропускаем рекламу, вопросы, посты без рецепта"""
    title = (article.get('title', '') or '').strip()
    description = article.get('description', '') or article.get('summary', '') or ''
    text = remove_links(html_to_paragraphs(description))
    combined = (title + ' ' + text).lower()
    
    for marker in SKIP_MARKERS:
        if marker in combined:
            return True, "маркер пропуска"
    
    if len(text) < 150:
        return True, "слишком коротко"
    
    recipe_keywords = ['ингредиент', 'приготовлен', 'рецепт', 'смешать', 'добавить', 
                       'жарить', 'варить', 'тушить', 'запекать', 'нарезать', 
                       'грамм', 'ст.л', 'ч.л', 'минут']
    has_recipe = any(kw in combined for kw in recipe_keywords)
    if not has_recipe:
        return True, "нет рецепта"
    
    return False, ""

def get_qwen_client():
    from openai import OpenAI
    return OpenAI(
        api_key=QWEN_API_KEY,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )

def extract_recipe_data(title, text):
    """
    Qwen извлекает из поста структурированные данные в JSON.
    Если в посте нет КБЖУ — рассчитывает по ингредиентам.
    """
    if not QWEN_API_KEY:
        return None
    
    prompt = f"""Проанализируй рецепт и верни ТОЛЬКО валидный JSON (без markdown, без кавычек снаружи, без комментариев).

Структура JSON:
{{
  "name": "короткое название блюда (2-5 слов, без эмодзи)",
  "appetizing": "одно яркое предложение, чтобы потекли слюнки (20-40 слов)",
  "ingredients": ["ингредиент 1 с количеством", "ингредиент 2 с количеством"],
  "steps": ["шаг 1", "шаг 2"],
  "time_minutes": число_минут_общего_времени,
  "servings": "на сколько порций",
  "kjbu": {{
    "kcal": число_на_100г,
    "proteins": число_Б_на_100г,
    "fats": число_Ж_на_100г,
    "carbs": число_У_на_100г,
    "estimated": true_если_рассчитал_сам_иначе_false
  }},
  "tags": ["завтрак", "ужин", "пп", "десерт" и т.д. — максимум 3]
}}

Правила:
- Ингредиенты и шаги — один в один из поста, но исправь опечатки и убери лишнее
- В шагах указывай РЕАЛЬНОЕ время для лучшего усвоения по принципам ПП (например, 'мариновать 20 мин' вместо 'на ночь')
- Если в исходном посте есть КБЖУ — возьми их как есть (estimated: false)
- Если КБЖУ нет — рассчитай по ингредиентам на 100 г готового блюда (estimated: true)
- Все продукты должны быть простыми и доступными в обычном магазине
- Без ссылок, эмодзи, кавычек в строках
- Только валидный JSON

Название блюда: {title}

Текст поста:
{text[:2500]}

JSON:"""
    
    try:
        client = get_qwen_client()
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "Ты кулинарный помощник. Возвращаешь только валидный JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        data = json.loads(content)
        return data
    except Exception as e:
        print(f"  ⚠️ Qwen ошибка извлечения: {e}")
        return None

def get_stock_image(name):
    """Сток Pexels для блюда"""
    if not PEXELS_API_KEY or not QWEN_API_KEY:
        return ""
    try:
        client = get_qwen_client()
        response = client.chat.completions.create(
            model="qwen-turbo",
            messages=[{"role": "user", "content":
                f"Write 2-3 English keywords for a food photography search of this dish. Reply only with words.\n\nDish: {name}"}],
            max_tokens=20,
            temperature=0.5
        )
        keywords = response.choices[0].message.content.strip()
        keywords = re.sub(r'[^a-zA-Z\s,]', '', keywords).strip()
        if not keywords:
            return ""
        
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

def format_recipe_post(recipe_data, image, video):
    """Формирует красивый пост по структурированным данным"""
    name = html_lib.escape(recipe_data.get('name', 'Блюдо'))
    appetizing = html_lib.escape(recipe_data.get('appetizing', ''))
    ingredients = recipe_data.get('ingredients', [])
    steps = recipe_data.get('steps', [])
    time_min = recipe_data.get('time_minutes', 30)
    servings = html_lib.escape(recipe_data.get('servings', ''))
    kjbu = recipe_data.get('kjbu', {})
    tags = recipe_data.get('tags', [])
    
    ing_lines = [f"• {html_lib.escape(ing)}" for ing in ingredients[:12]]
    ingredients_block = '\n'.join(ing_lines) if ing_lines else ''
    
    steps_lines = [f"{i+1}. {html_lib.escape(s)}" for i, s in enumerate(steps[:8])]
    steps_block = '\n'.join(steps_lines) if steps_lines else ''
    
    kcal = kjbu.get('kcal', 0)
    p = kjbu.get('proteins', 0)
    f = kjbu.get('fats', 0)
    c = kjbu.get('carbs', 0)
    est = '≈' if kjbu.get('estimated', False) else ''
    kjbu_line = f"🔥 <b>КБЖУ на 100 г:</b> {est}{kcal} ккал • Б: {p} • Ж: {f} • У: {c}"
    
    base_tags = tags[:3] if tags else ['рецепт', 'ужин', 'вкусно']
    hashtags = ' '.join('#' + t.replace(' ', '').lower() for t in base_tags)
    hashtags += ' #рецепт'
    
    time_line = f"⏱ <b>Время:</b> {time_min} мин"
    if servings:
        time_line += f" • {servings}"
    
    subscribe_link = f'<a href="{CHANNEL_LINK}"><b>🔔 Подписаться</b></a>'
    
    message = f"""🍲 <b>{name}</b>

<i>{appetizing}</i>

🥄 <b>Ингредиенты:</b>
{ingredients_block}

👩‍🍳 <b>Приготовление:</b>
{steps_block}

{time_line}
{kjbu_line}

{subscribe_link}
{hashtags}"""
    
    return message

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
        elif 'png' in content_type:
            ext = 'png'
        else:
            ext = 'jpg'
        return resp.content, f"media.{ext}"
    except Exception:
        return None, None

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
    except Exception:
        pass
    content, filename = download_media(image_url)
    if content:
        if b'<html' in content[:200].lower():
            return False
        try:
            files = {'photo': (filename, content, 'image/jpeg')}
            data = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": message, "parse_mode": "HTML"}
            result = requests.post(url, data=data, files=files).json()
            return result.get('ok', False)
        except Exception:
            return False
    return False

def send_video(message, video_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    data = {"chat_id": TELEGRAM_CHANNEL_ID, "video": video_url, "caption": message, "parse_mode": "HTML"}
    try:
        result = requests.post(url, data=data).json()
        if result.get('ok'):
            return True
    except Exception:
        pass
    content, filename = download_media(video_url)
    if content and len(content) <= 50 * 1024 * 1024:
        try:
            files = {'video': (filename, content, 'video/mp4')}
            data = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": message, "parse_mode": "HTML"}
            result = requests.post(url, data=data, files=files).json()
            return result.get('ok', False)
        except Exception:
            return False
    return False

def score_recipe(article, recipe_data):
    """Приоритет: каналы с КБЖУ + полный рецепт + свежие"""
    score = 5
    source = article.get('source', '').lower()
    
    if 'простые рецепты' in source or 'аймкук' in source:
        score += 3
    
    if 'кухня наизнанку' in source:
        score += 2
    
    kjbu = recipe_data.get('kjbu', {}) if recipe_data else {}
    if not kjbu.get('estimated', True) and kjbu.get('kcal'):
        score += 2
    
    score += min(2, article.get('timestamp', 0) / (24 * 3600))
    
    return score

def load_published():
    f = 'src/content/published.json'
    if os.path.exists(f):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                return set(json.load(fh))
        except Exception:
            return set()
    return set()

def save_published(published):
    f = 'src/content/published.json'
    with open(f, 'w', encoding='utf-8') as fh:
        json.dump(list(published), fh, ensure_ascii=False, indent=2)

def load_site_feed():
    f = 'src/content/site_feed.json'
    if os.path.exists(f):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return []
    return []

def save_site_feed(feed):
    f = 'src/content/site_feed.json'
    with open(f, 'w', encoding='utf-8') as fh:
        json.dump(feed, fh, ensure_ascii=False, indent=2)

def main():
    print("🍳 Начинаем публикацию рецептов...")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("❌ Telegram секреты не настроены!")
        return
    
    input_file = 'src/content/news_translated.json'
    if not os.path.exists(input_file):
        print("❌ Файл news_translated.json не найден.")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    print(f"📚 Загружено {len(articles)} рецептов")
    published = load_published()
    new_articles = [a for a in articles if a['link'] not in published]
    print(f"🆕 Новых рецептов: {len(new_articles)}")
    
    clean_articles = []
    for a in new_articles:
        skip, reason = should_skip(a)
        if skip:
            print(f"  🚫 Пропускаем ({reason}): {a.get('title', '')[:60]}")
        else:
            clean_articles.append(a)
    print(f"✅ После фильтра: {len(clean_articles)} рецептов")
    
    candidates = clean_articles[:15]
    prepared = []
    for a in candidates:
        description = a.get('description', '') or a.get('summary', '')
        text = remove_links(html_to_paragraphs(description))
        title = a.get('title_ru', a.get('title', ''))
        
        print(f"\n🔍 Обрабатываем: {title[:60]}...")
        recipe_data = extract_recipe_data(title, text)
        if not recipe_data or not recipe_data.get('name'):
            print("  ⚠️ Не удалось извлечь рецепт")
            continue
        
        score = score_recipe(a, recipe_data)
        
        image = a.get('image', '')
        video = a.get('video', '')
        if not image and not video:
            stock = get_stock_image(recipe_data.get('name', ''))
            if stock:
                image = stock
        
        prepared.append({
            'article': a,
            'recipe_data': recipe_data,
            'image': image,
            'video': video,
            'score': score
        })
        print(f"  ✅ {recipe_data.get('name')} → score {score}")
    
    prepared.sort(key=lambda x: x['score'], reverse=True)
    to_publish = prepared[:POSTS_PER_RUN]
    
    if not to_publish:
        print("✅ Нет новых рецептов для публикации")
        return
    
    site_feed = load_site_feed()
    success_count = 0
    for i, item in enumerate(to_publish, 1):
        article = item['article']
        recipe_data = item['recipe_data']
        image = item['image']
        video = item['video']
        
        print(f"\n📤 Публикуем {i}/{len(to_publish)}: {recipe_data.get('name')}...")
        message = format_recipe_post(recipe_data, image, video)
        
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
            # Сохраняем для сайта
            site_feed.insert(0, {
                "name": html_lib.escape(recipe_data.get('name', '')),
                "appetizing": html_lib.escape(recipe_data.get('appetizing', '')),
                "ingredients": [html_lib.escape(i) for i in recipe_data.get('ingredients', [])],
                "steps": [html_lib.escape(s) for s in recipe_data.get('steps', [])],
                "time_minutes": recipe_data.get('time_minutes', 0),
                "servings": recipe_data.get('servings', ''),
                "kjbu": recipe_data.get('kjbu', {}),
                "tags": [t.replace(' ', '').lower() for t in recipe_data.get('tags', [])],
                "image": image or "",
                "time": datetime.now().isoformat()
            })
            print(f"  ✅ Опубликовано")
        else:
            print(f"  ❌ Не удалось опубликовать")
    
    site_feed = site_feed[:60]
    save_site_feed(site_feed)
    save_published(published)
    print(f"\n✅ Успешно опубликовано: {success_count}")
    print(f"🌐 Лента сайта: {len(site_feed)} рецептов")

if __name__ == "__main__":
    main()