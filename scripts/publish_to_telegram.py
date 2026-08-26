import json, os, re, html as H, requests
from datetime import datetime, timezone, timedelta

TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TG_CHAT = os.getenv('TELEGRAM_CHANNEL_ID', '')
QWEN_KEY = os.getenv('QWEN_API_KEY', '')
GROQ_KEY = os.getenv('GROQ_API_KEY', '')
PEXELS_KEY = os.getenv('PEXELS_API_KEY', '')
EVENT_NAME = os.getenv('EVENT_NAME', 'workflow_dispatch')
CHANNEL = "@ignisnovosti"
MSK = timezone(timedelta(hours=3))
AI_OK = bool(QWEN_KEY or GROQ_KEY)

JUNK = ['приятного аппетита', 'смотр', 'ссылк', 'каталог', 'наш канал', 'подпис',
        '***', 'макс', 'ozon', 'wildberries', 'реклама', 'комментариях', 'спасибо',
        'полный рецепт', 'пошаговыми фото', 'ккал', 'б:', 'б /', 'ж:', 'у:']
EXOTIC = ['кокос', 'авокадо', 'киноа', 'кускус', 'тофу', 'миди', 'устриц', 'трюфел',
          'гребешок', 'лангуст', 'анчоус', 'каперс', 'артшо', 'манго', 'папайя',
          'личжи', 'пармезан', 'дорблю', 'хумус', 'тахини', 'матча', 'фисташк']

def strip_all_html(text):
    if not text: return ""
    t = re.sub(r'<tg-emoji[^>]*>.*?</tg-emoji>', '', text, flags=re.S)
    t = re.sub(r'<span class="emoji">.*?</span>', '', t, flags=re.S)
    t = re.sub(r'<tg-spoiler[^>]*>.*?</tg-spoiler>', '', t, flags=re.S)
    t = re.sub(r'<blockquote[^>]*>.*?</blockquote>', '', t, flags=re.S)
    t = re.sub(r'<video[^>]*>.*?</video>', '', t, flags=re.S)
    t = re.sub(r'<img[^>]*>', '', t)
    t = re.sub(r'<a[^>]*>.*?</a>', '', t, flags=re.S)
    t = re.sub(r'(?i)<br\s*/?>', '\n', t)
    t = re.sub(r'(?i)</?p>', '\n', t)
    t = re.sub(r'<[^<>]+>', '', t)
    t = re.sub(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\u20e3\ufe0f\u200d\u2024]+', '', t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'@[a-zA-Z_][a-zA-Z0-9_]{3,}', '', t)
    t = H.unescape(t)
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return '\n'.join(l.strip() for l in t.split('\n') if l.strip())

def clean_title(title):
    if not title: return ""
    t = re.sub(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\u20e3\ufe0f]+', '', title)
    return re.sub(r'^[🔁🖼🎬💥]+\s*', '', t).strip(' .«»"')

def short_name(title):
    t = clean_title(title)
    if len(t) > 60: t = t[:60].rsplit(' ', 1)[0] + '…'
    return t or 'Рецепт'

def clean_lines(block, min_len):
    out = []
    for line in (block or '').split('\n'):
        line = re.sub(r'^\d+[\u20e3\u2024.)\s]+', '', line).strip('•-–—*· ')
        low = line.lower()
        if len(line) >= min_len and not any(j in low for j in JUNK) \
           and not re.match(r'^[бжу]\s*[:/]', low):
            out.append(line)
    return out

def similar(a, b):
    a = re.sub(r'[^a-zа-яё0-9]', '', a.lower())[:25]
    b = re.sub(r'[^a-zа-яё0-9]', '', b.lower())[:25]
    return bool(a and b and (a in b or b in a or a[:12] == b[:12]))

def looks_like_ingredient(s):
    return bool(re.search(r'[-—]\s*\d|^\d|г\.|мл|шт|по вкусу', s.lower()))

def should_skip(text):
    low = text.lower()
    if len(low) < 150: return "коротко"
    if any(m in low for m in ['реклама', 'промокод', 'розыгрыш', 'подпишись', 'ozon.ru', 'wildberries']): return "реклама"
    if any(e in low for e in EXOTIC): return "экзотика"
    if not any(k in low for k in ['ингредиент', 'ингридиент', 'продукт', 'приготовлен', 'рецепт',
                                  'смешать', 'добавить', 'жарить', 'варить', 'тушить',
                                  'запекать', 'грамм', 'ст.л', 'ч.л', 'минут']): return "нет рецепта"
    return ""

FOOD_EN = {'куриц': 'chicken', 'мяс': 'meat', 'рыб': 'fish', 'салат': 'salad', 'суп': 'soup',
           'пирог': 'pie', 'торт': 'cake', 'блин': 'pancakes', 'творог': 'cottage cheese',
           'сыр': 'cheese', 'картоф': 'potatoes', 'капуст': 'cabbage', 'кабачк': 'zucchini',
           'баклажан': 'eggplant', 'помидор': 'tomatoes', 'огурц': 'cucumbers', 'яблок': 'apple',
           'гриб': 'mushrooms', 'рис': 'rice', 'гречк': 'buckwheat', 'запеканк': 'casserole',
           'котлет': 'cutlets', 'булоч': 'buns', 'кекс': 'muffins', 'лимонад': 'lemonade',
           'напиток': 'drink', 'каш': 'porridge', 'омлет': 'omelet', 'сырник': 'syrniki'}

def meal_tags(text):
    low = text.lower(); tags = []
    if any(k in low for k in ['завтрак', 'омлет', 'каш', 'сырник', 'олад', 'блин', 'творог', 'чай', 'лимонад']): tags.append('завтрак')
    if any(k in low for k in ['обед', 'суп', 'борщ', 'плов', 'макарон', 'гречк']): tags.append('обед')
    if any(k in low for k in ['ужин', 'мяс', 'куриц', 'рыб', 'котлет', 'гарнир', 'салат', 'запеканк']): tags.append('ужин')
    if any(k in low for k in ['десерт', 'торт', 'кекс', 'сладк', 'морожен', 'пирог', 'печень', 'булоч']): tags.append('десерт')
    return tags

def parse_recipe(title, text):
    ing_m = re.search(r'(?:ингредиент\w*|ингридиент\w*|продукты|что понадобится|нам понадобится)[^\n]{0,30}:\s*(.*?)(?=(?:приготовлен\w*|способ|как готовим|как приготовить|\Z))', text, re.S | re.I)
    step_m = re.search(r'(?:приготовлен\w*|способ|как готовим|как приготовить)[^\n]{0,30}:\s*(.*)', text, re.S | re.I)
    ingredients = clean_lines(ing_m.group(1) if ing_m else '', 4)[:10]
    steps = clean_lines(step_m.group(1) if step_m else '', 15)[:8]
    time_m = re.search(r'(\d{1,3})\s*мин', text, re.I)
    kcal_m = re.search(r'(\d{2,4})\s*к[Кк]ал', text)
    bj_u = re.search(r'[Бб][/ ]?[Жж][/ ]?[Уу][^\d]{0,10}([\d.,]+)[/\s]+([\d.,]+)[/\s]+([\d.,]+)', text)
    lines = [l for l in text.split('\n') if len(l) > 20 and 'ингредиент' not in l.lower()]
    app = ''
    for l in lines:
        if len(l) > 25 and not similar(l, title) and not looks_like_ingredient(l):
            app = l[:200]; break
    if not app and ingredients:
        app = 'Простые продукты из любого магазина: ' + ', '.join(i.split(' - ')[0].split(' — ')[0].lower() for i in ingredients[:4]) + '.'
    return {'name': short_name(title), 'appetizing': app, 'ingredients': ingredients, 'steps': steps,
            'time_minutes': int(time_m.group(1)) if time_m else 0,
            'kjbu': {'kcal': int(kcal_m.group(1)), 'proteins': float(bj_u.group(1).replace(',', '.')),
                     'fats': float(bj_u.group(2).replace(',', '.')), 'carbs': float(bj_u.group(3).replace(',', '.')),
                     'estimated': False} if (kcal_m and bj_u) else {},
            'tags': meal_tags(text),
            'stock_query': ' '.join([en for ru, en in FOOD_EN.items() if ru in title.lower()][:2]) or 'homemade dish'}

def ai_recipe(title, text):
    global AI_OK
    if not AI_OK: return None
    clients = []
    if GROQ_KEY: clients.append(('groq', GROQ_KEY, 'https://api.groq.com/openai/v1', 'llama-3.3-70b-versatile'))
    if QWEN_KEY: clients.append(('qwen', QWEN_KEY, 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'qwen-plus'))
    for name, key, base, model in clients:
        try:
            from openai import OpenAI
            r = OpenAI(api_key=key, base_url=base).chat.completions.create(
                model=model, max_tokens=1200, temperature=0.3,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content":
                    f'Верни ТОЛЬКО JSON: {{"name":"2-5 слов","appetizing":"1 предложение, НЕ повторяющее название","ingredients":["..."],"steps":["..."],"time_minutes":0,"kjbu":{{"kcal":0,"proteins":0,"fats":0,"carbs":0,"estimated":true}},"tags":["только из: завтрак,обед,ужин,десерт; макс 2"]}}. Возьми из поста. КБЖУ из поста или рассчитай (estimated:true). Без эмодзи.\n\nПост: {text[:2500]}"}])
            data = json.loads(re.sub(r'^```json\s*|\s*```$', '', r.choices[0].message.content.strip()))
            if data.get('name') and (data.get('ingredients') or data.get('steps')):
                data['tags'] = [t for t in data.get('tags', []) if t in ['завтрак', 'обед', 'ужин', 'десерт']]
                data['stock_query'] = ' '.join([en for ru, en in FOOD_EN.items() if ru in data['name'].lower()][:2]) or 'homemade dish'
                return data
        except Exception as e:
            if '403' in str(e) or 'quota' in str(e).lower():
                print(f"  ⚠️ {name}: квота"); continue
    return None

def get_stock(query):
    if not PEXELS_KEY: return ""
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS_KEY},
                         params={"query": query, "per_page": 1}, timeout=15).json()
        return r.get('photos', [{}])[0].get('src', {}).get('large', '')
    except Exception: return ""

def format_post(d):
    ing = '\n'.join(f"• {H.escape(i)}" for i in d['ingredients']) or '• см. источник'
    stp = '\n'.join(f"{i+1}. {H.escape(s)}" for i, s in enumerate(d['steps'])) or '1. См. источник'
    k = d.get('kjbu', {})
    kjbu = f"🔥 <b>КБЖУ:</b> {'≈' if k.get('estimated') else ''}{k.get('kcal', 0)} ккал • Б{k.get('proteins', 0)} Ж{k.get('fats', 0)} У{k.get('carbs', 0)}" if k else ""
    time_l = f"⏱ <b>Время:</b> {d['time_minutes']} мин" if d.get('time_minutes') else ""
    tags = ' '.join('#' + t for t in d['tags'])
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
    base = f"https://api.telegram.org/bot{TG_TOKEN}/"
    if kind == 'message' or not media_url:
        try: return requests.post(base + 'sendMessage', data={"chat_id": TG_CHAT, "text": message, "parse_mode": "HTML"}).json().get('ok', False)
        except Exception: return False
    field = 'photo' if kind == 'photo' else 'video'
    try:
        if requests.post(base + f'send{kind.capitalize()}', data={"chat_id": TG_CHAT, field: media_url, "caption": message, "parse_mode": "HTML"}).json().get('ok'): return True
    except Exception: pass
    try:
        content = requests.get(media_url, timeout=30).content
        if b'<html' in content[:200].lower() or len(content) > 50*1024*1024: return False
        return requests.post(base + f'send{kind.capitalize()}', data={"chat_id": TG_CHAT, "caption": message, "parse_mode": "HTML"}, files={field: ('media.jpg', content)}).json().get('ok', False)
    except Exception: return False

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: pass
    return default

def main():
    print("🍳 Публикуем рецепты...")
    hour = datetime.now(MSK).hour
    slot = {7: 'завтрак', 13: 'обед', 19: 'ужин'}.get(hour)
    if slot is None and EVENT_NAME != 'schedule':
        if hour < 5: slot = 'ужин'
        elif hour < 11: slot = 'завтрак'
        elif hour < 16: slot = 'обед'
        else: slot = 'ужин'
    if slot is None:
        print(f"⏸ {hour}:00 МСК — вне расписания (7/13/19)"); return
    print(f"🕐 Слот: #{slot}")
    articles = load_json('src/content/news_translated.json', [])
    published = set(load_json('src/content/published.json', []))
    new = [a for a in articles if a['link'] not in published]
    print(f"🆕 Новых: {len(new)}")
    prepared = []
    for a in new[:30]:
        text = strip_all_html(a.get('description', '') or a.get('summary', ''))
        title = a.get('title_ru', a.get('title', ''))
        if should_skip(text): continue
        d = ai_recipe(title, text) or parse_recipe(title, text)
        if not d.get('ingredients') or len(d['ingredients']) < 3 or not d.get('steps'): continue
        if not d.get('tags'): d['tags'] = [slot]
        image, video = a.get('image', ''), a.get('video', '')
        if not image and not video: image = get_stock(d['stock_query'])
        score = 5 + (2 if d.get('kjbu') else 0) + (1 if image or video else 0) + (3 if slot in d['tags'] else 0)
        prepared.append((score, {'a': a, 'd': d, 'image': image, 'video': video}))
        print(f"  ✅ {d['name'][:40]} → {score}")
    prepared.sort(key=lambda x: x[0], reverse=True)
    to_publish = prepared[:2]
    if not to_publish:
        print("✅ Нет рецептов для слота"); return
    site_feed = load_json('src/content/site_feed.json', [])
    ok_count = 0
    for score, item in to_publish:
        d, image, video = item['d'], item['image'], item['video']
        print(f"\n📤 {d['name']}...")
        msg = format_post(d)
        ok = video and send('video', msg, video)
        if not ok and image: ok = send('photo', msg, image)
        if not ok: ok = send('message', msg, '')
        if ok:
            published.add(item['a']['link'])
            site_feed.insert(0, {**d, 'image': image, 'time': datetime.now().isoformat()})
            ok_count += 1; print("  ✅ Опубликовано")
        else: print("  ❌ Ошибка отправки")
    with open('src/content/published.json', 'w', encoding='utf-8') as f: json.dump(list(published), f, ensure_ascii=False)
    with open('src/content/site_feed.json', 'w', encoding='utf-8') as f: json.dump(site_feed[:60], f, ensure_ascii=False, indent=2)
    print(f"\n✅ Опубликовано: {ok_count} | Лента сайта: {len(site_feed[:60])}")

if __name__ == "__main__":
    main()
