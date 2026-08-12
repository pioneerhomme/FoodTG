#!/bin/bash
set -e

echo "🔄 Синхронизация..."

# Если есть несохранённые изменения — коммитим их
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "📝 Есть несохранённые изменения — коммитим"
    git add .
    git commit -m "auto: update $(date +%H:%M)"
fi

# Тянем изменения с rebase (игнорируя конфликты в JSON-файлах)
if ! git pull --rebase origin main; then
    echo "⚠️ Конфликт при rebase, решаем..."
    # Берём нашу версию для конфликтов в скриптах
    git checkout --theirs src/content/published.json 2>/dev/null || true
    git checkout --ours scripts/ 2>/dev/null || true
    git add .
    git rebase --continue
fi

# Отправляем на GitHub
if git push 2>/dev/null; then
    echo "✅ Успешно отправлено на GitHub"
else
    echo "⚠️ Push не удался, пробуем с force..."
    git push --force-with-lease
fi
