# ArtSpace — финальная сборка

Готов к защите/деплою. Собран 2026-11-07.

## Запуск
    python3 make_artspace.py

Всё в папке `site/`. Открывай `site/index.html` в браузере
(лучше через локальный сервер: `python3 -m http.server -d site`).

## Страницы
index, catalog, product, order, tickets, favorites, reviews,
my-reviews, organizers, about, contacts, privacy, 404.

## Сценарии
- Поиск + фильтры + сортировка + метки в каталоге (URL синхронизируется).
- Подборщик из 3 вопросов на главной.
- Избранное, «Мои записи» (билеты с QR, печать, отмена).
- Отзывы: форма, список, «только мои», удаление.
- Запись: тариф, гости, валидация, итог.
- Тёмная/светлая тема, prefers-reduced-motion, печать билета.
- 404, sitemap, robots, manifest, _redirects (Netlify), .htaccess (Apache).

Все данные — localStorage. Сервера нет: письма/оплата не уходят.
