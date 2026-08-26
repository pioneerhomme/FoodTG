import json
import os
import re
import html as H
import requests
from datetime import datetime

TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TG_CHAT = os.getenv('TELEGRAM_CHANNEL_ID', '')
QWEN_KEY = os.getenv('QWEN_API_KEY', '')
PEXELS_KEY = os.getenv('PEXELS_API_KEY', '')

CHANNEL = "@ignisnovosti"
PER_RUN = 5
QWEN_OK = bool(QWEN_KEY)  # автовыключение при 403

# ---------- Чистка ----------

def clean_text(html_text):
    """HTML/ссылки/мусор -> чистый текст"""
    if not html_text:
        return ""
    t = re.sub(r'(?i)<br\s*/?>', '\n', html_text)
    t = re.sub(r'(?i)</p>', '\n\n', t)
    t = re.sub('<[^<]+?>', '', t)
    t = H.unescape(t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'@[a-zA-Z_][a-zA-Z0-9_]{3,}', '', t)
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    lines = [l.strip() for l in t.split('\n')]
    return '\n'.join(l for l in lines if l)

def clean_title(title):
    t = re.sub(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+', '', title or '')
    return re.sub(r'^[🔁🖼🎬💥]+\s*', '', t).strip(' .«»"')

# ---------- Фильтр ----------

def should_skip(text):
    low = text.lower()
    if len(low) < 150:
        return "слишком коротко"
    if any(m in low for m in ['реклама', 'промокод', 'розыгрыш', 'подпишись', 'ozon.ru']):
        return "реклама"
    if not any(k in low for k in ['ингредиент', 'приготовлен', 'рецепт', 'смешать',
                                  'добавить', 'жарить', 'варить', 'тушить', 'запекать',
                                  'грамм', 'ст.л', 'ч.л', 'минут']):
        return "нет рецепта"
    return ""

# ---------- Извлечение рецепта БЕЗ AI ----------

FOOD_EN = {'куриц': 'chicken', 'мяс': 'meat', 'рыб': 'fish', 'салат': 'salad',
           'суп': 'soup', 'пирог': 'pie', 'торт': 'cake', 'блин': 'pancakes',
           'творог': 'cottage cheese', 'сыр': 'cheese', 'картоф': 'potatoes',
           'капуст': 'cabbage', 'кабачк': 'zucchini', 'баклажан': 'eggplant',
           'помидор': 'tomatoes', 'огурц': 'cucumbers', 'яблок': 'apple',
           'гриб': 'mushrooms', 'рис': 'rice', 'гречк': 'buckwheat',
           'запеканк': 'casserole', 'котлет': 'cutlets', 'булоч': 'buns',
           'кекс': 'muffins', 'лимонад': 'lemonade', 'напиток': 'drink'}

def guess_tags(text):
    rules = {'завтрак': ['завтрак', 'омлет', 'каш', 'сырник', 'олад'],
             'ужин': ['ужин', 'мясо', 'куриц', 'рыб', 'котлет', 'гарнир'],
             'десерт': ['десерт', 'торт', 'кекс', 'сладк', 'морожен', 'пирог'],
             'салат': ['салат'], 'суп': ['суп', 'борщ'],
             'выпечка': ['выпеч', 'пирог', 'булоч', 'хлеб'],
             'заготовки': ['заготов', 'на зиму', 'марин', 'солень', 'варень'],
             'пп': ['пп ', 'диет', 'калор', 'стройн']}
    tags = [t for t, kws in rules.items() if any(k in text for k in kws)]
    return tags[:3] or ['рецепт']

def parse_recipe(title, text):
    """Авто-разбор рецепта регулярками — работает без AI"""
    ing_m = re.search(r'ингредиент\w*[^:\n]*:(.*?)(?=приготовлен|способ|как готовим|как приготовить)', text, re.S | re.I)
    step_m = re.search(r'(?:приготовлен\w*|способ|как готовим|как приготовить)[^:\n]*:(.*)', text, re.S | re.I)
    
    ingredients = [l.strip('•-–—*· ') for l in (ing_m.group(1).split('\n') if ing_m else []) if len(l.strip('•-–—*· ')) > 3][:12]
    steps = [l.strip() for l in (step_m.group(1).split('\n') if step_m else []) if len(l.strip()) > 10][:8]
    
    time_m = re.search(r'(\d{1,3})\s*мин', text, re.I)
    kcal_m = re.search(r'(\d{2,4})\s*ккал', text, re.I)
    bj_u = re.search(r'[Бб][/ ]?[Жж][/ ]?[Уу][^\d]{0,5}([\d.,]+)[/ ]([\d.,]+)[/ ]([\d.,]+)', text)
    
    first = re.split(r'[.!?\n]', text, 1)[0].strip()
    
    return {
        'name': clean_title(title)[:80] or 'Рецепт',
        'appetizing': first[:150],
        'ingredients': ingredients,
        'steps': steps,
        'time_minutes': int(time_m.group(1)) if time_m else 0,
        'kjbu': {'kcal': int(kcal_m.group(1)), 'proteins': float(bj_u.group(1)),
                 'fats': float(bj_u.group(2)), 'carbs': float(bj_u.group(3)),
                 'estimated': False} if (kcal_m and bj_u) else {},
        'tags': guess_tags(text.lower()),
        'stock_query': ' '.join([en for ru, en in FOOD_EN.items() if ru in text.lower()][:2]) or 'homemade dish',
    }

# ---------- AI-режим (если есть квота) ----------

def ai_recipe(title, text):
    global QWEN_OK
    if not QWEN_OK:
        return None
    try:
        from openai import OpenAI
        r = OpenAI(api_key=QWEN_KEY,
                   base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1").chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content":
                f'Верни ТОЛЬКО JSON: {{"name":"название 2-5 слов","appetizing":"1 яркое предложение","ingredients":["..."],"steps":["..."],"time_minutes":0,"kjbu":{{"kcal":0,"proteins":0,"fats":0,"carbs":0,"estimated":true}},"tags":["макс 3"]}}. '
                f'Ингредиенты и шаги — из поста, опечатки исправь. КБЖУ из поста или рассчитай (estimated:true). Без эмодзи и ссылок.\n\nПост: {text[:2500]}'}],
            max_tokens=1200, temperature=0.3,
            response_format={"type": "json_object"})
        data = json.loads(re.sub(r'^```json\s*|\s*```$', '', r.choices[0].message.content.strip()))
        if data.get('name'):
            data['stock_query'] = ' '.join([en for ru, en in FOOD_EN.items() if ru in data['name'].lower()][:2]) or 'homemade dish'
            return data
    except Exception as e:
        if '403' in str(e) or 'quota' in str(e).lower():
            QWEN_OK = False
            print("  ⚠️ Квота Qwen исчерпана — включаю автономный режим")
    return None

# ---------- Сток ----------

def get_stock(query):
    if not PEXELS_KEY:
        return ""
    try:
        r = requests.get("https://api.pexels.com/v1/search",
                         headers={"Authorization": PEXELS_KEY},
                         params={"query": query, "per_page": 1}, timeout=15).json()
        return r.get('photos', [{}])[0].get('src', {}).get('large', '')
    except Exception:
        return ""

# ---------- Публикация ----------

def format_post(d):
    ing = '\n'.join(f"• {H.escape(i)}" for i in d['ingredients']) or '• см. источник'
    stp = '\n'.join(f"{i+1}. {H.escape(s)}" for i, s in enumerate(d['steps'])) or '1. См. источник'
    k = d.get('kjbu', {})
    kjbu = f"🔥 <b>КБЖУ на 100 г:</b> {'≈' if k.get('estimated') else ''}{k.get('kcal', 0)} ккал • Б: {k.get('proteins', 0)} • Ж: {k.get('fats', 0)} • У: {k.get('carbs', 0)}" if k else ""
    time_l = f"⏱ <b>Время:</b> {d['time_minutes']} мин" if d.get('time_minutes') else ""
    tags = ' '.join('#' + t for t in d['tags']) + ' #рецепт'
    return f"""🍲 <b>{H.escape(d['name'])}</b>

<i>{H.escape(d['appetizing'])}</i>

🥄 <b>Ингредиенты:</b>
{ing}

👩‍🍳 <b>Приготовление:</b>
{stp}

{time_l}
{kjbu}

<a href="https://t.me/{CHANNEL.replace('@', '')}"><b>🔔 Подписаться</b></a>
{tags}"""

def send(kind, message, media_url):
    """kind: message | photo | video. Фото/видео сначала URL, потом файлом."""
    base = f"https://api.telegram.org/bot{TG_TOKEN}/"
    if kind == 'message' or not media_url:
        try:
            return requests.post(base + 'sendMessage',
                                 data={"chat_id": TG_CHAT, "text": message, "parse_mode": "HTML"}).json().get('ok', False)
        except Exception:
            return False
    field = 'photo' if kind == 'photo' else 'video'
    try:
        if requests.post(base + f'send{kind.capitalize()}',
                         data={"chat_id": TG_CHAT, field: media_url, "caption": message,
                               "parse_mode": "HTML"}).json().get('ok'):
            return True
    except Exception:
        pass
    try:
        content = requests.get(media_url, timeout=30).content
        if b'<html' in content[:200].lower() or len(content) > 50 * 1024 * 1024:
            return False
        return requests.post(base + f'send{kind.capitalize()}',
                             data={"chat_id": TG_CHAT, "caption": message, "parse_mode": "HTML"},
                             files={field: ('media.jpg', content)}).json().get('ok', False)
    except Exception:
        return False

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return default

def main():
    print("🍳 Публикуем рецепты...")
    articles = load_json('src/content/news_translated.json', [])
    published = set(load_json('src/content/published.json', []))
    new = [a for a in articles if a['link'] not in published]
    print(f"🆕 Новых: {len(new)}")
    
    # Фильтр + разбор
    prepared = []
    for a in new[:20]:
        text = clean_text(a.get('description', '') or a.get('summary', ''))
        title = a.get('title_ru', a.get('title', ''))
        reason = should_skip(text)
        if reason:
            print(f"  🚫 {reason}: {title[:50]}")
            continue
        
        d = ai_recipe(title, text) or parse_recipe(title, text)
        if not d.get('ingredients') and not d.get('steps'):
            print(f"  🚫 нет рецепта: {title[:50]}")
            continue
        
        image, video = a.get('image', ''), a.get('video', '')
        if not image and not video:
            image = get_stock(d['stock_query'])
        
        score = 5 + (2 if d.get('kjbu') else 0) + (1 if image or video else 0)
        prepared.append((score, {'a': a, 'd': d, 'image': image, 'video': video}))
        print(f"  ✅ {d['name']} → {score}")
    
    prepared.sort(key=lambda x: x[0], reverse=True)
    site_feed = load_json('src/content/site_feed.json', [])
    ok_count = 0
    
    for score, item in prepared[:PER_RUN]:
        d, image, video = item['d'], item['image'], item['video']
        print(f"\n📤 {d['name']}...")
        msg = format_post(d)
        
        ok = video and send('video', msg, video)
        if not ok and image:
            ok = send('photo', msg, image)
        if not ok:
            ok = send('message', msg, '')
        
        if ok:
            published.add(item['a']['link'])
            site_feed.insert(0, {**d, 'image': image, 'time': datetime.now().isoformat()})
            ok_count += 1
            print("  ✅ Опубликовано")
        else:
            print("  ❌ Ошибка отправки")
    
    with open('src/content/published.json', 'w', encoding='utf-8') as f:
        json.dump(list(published), f, ensure_ascii=False)
    with open('src/content/site_feed.json', 'w', encoding='utf-8') as f:
        json.dump(site_feed[:60], f, ensure_ascii=False, indent=2)
    print(f"\n✅ Опубликовано: {ok_count} | Лента сайта: {len(site_feed[:60])}")

if __name__ == "__main__":
    main()