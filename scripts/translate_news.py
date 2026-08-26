import json
import os

def main():
    print("🔄 Подготовка рецептов (перевод не требуется)...")
    
    input_file = 'src/content/news.json'
    output_file = 'src/content/news_translated.json'
    
    if not os.path.exists(input_file):
        print("❌ news.json не найден")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    # Просто копируем title в title_ru
    for a in articles:
        a['title_ru'] = a.get('title', '')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Подготовлено {len(articles)} рецептов")

if __name__ == "__main__":
    main()