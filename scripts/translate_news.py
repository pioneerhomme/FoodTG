import json
import os
from deep_translator import GoogleTranslator

def translate_text(text, source_lang='auto', target_lang='ru'):
    """Переводит текст с одного языка на другой"""
    
    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)
        return translated
    except Exception as e:
        print(f"  ⚠️ Ошибка перевода: {e}")
        return text

def translate_article(article):
    """Переводит статью если нужно"""
    
    # Если статья уже на русском - не переводим
    if article.get('language') == 'ru':
        return article
    
    # Переводим заголовок
    print(f"  🌐 Переводим: {article['title'][:50]}...")
    translated_title = translate_text(article['title'])
    
    # Добавляем переведённый заголовок
    article['title_ru'] = translated_title
    article['language'] = 'ru'
    
    return article

def main():
    """Главная функция"""
    
    print("🚀 Начинаем перевод новостей...")
    
    # Читаем собранные новости
    input_file = 'src/content/news.json'
    
    if not os.path.exists(input_file):
        print("❌ Файл news.json не найден. Сначала запустите collect_news.py")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    print(f"📚 Загружено {len(articles)} статей")
    
    # Переводим статьи
    translated_articles = []
    need_translation = 0
    
    for article in articles:
        if article.get('language') != 'ru':
            need_translation += 1
            translated_articles.append(translate_article(article))
        else:
            translated_articles.append(article)
    
    print(f"\n🌐 Переведено {need_translation} статей")
    
    # Сохраняем результат
    output_file = 'src/content/news_translated.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(translated_articles, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено в {output_file}")
    print(f"📊 Всего статей: {len(translated_articles)}")

# Запуск скрипта
if __name__ == "__main__":
    main()