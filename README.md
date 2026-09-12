# Vertical World — Climbing Anthology (GitHub Pages)

Публичный сайт антологии людей вертикального мира (1900–2026) на русском и английском.

**Исходные тексты (редакционные):** `climbing_stars_anthology.md`, `climbing_stars_anthology_en.md`  
**Публичные тексты сайта:** `docs/content/ru.md`, `docs/content/en.md` (без заметок к редакции и внутренних ссылок на бэкапы)

## Локальный просмотр

GitHub Pages отдаёт файлы как статику. Локально нужен простой HTTP-сервер (иначе `fetch` markdown/json может блокироваться):

```bash
cd docs
python3 -m http.server 8080
```

Открыть: http://localhost:8080/?lang=ru

## Обновить публичный контент после правок исходников

```bash
python3 scripts/build_public_content.py
```

## Портреты и атрибуция

Скрипт тянет **только свободно лицензированные** pageimage с Wikipedia/Wikimedia Commons (`pilicense=free`) и сохраняет локальные копии + каталог с автором, ссылкой на первоисточник и лицензией:

```bash
python3 scripts/build_people_index.py
python3 scripts/fetch_commons_portraits.py
# после докачки — уточнить artist/license из Commons:
python3 scripts/rebuild_catalog_from_portraits.py
```

- Каталог: `docs/media/catalog.json`
- Файлы: `docs/media/portraits/`
- На сайте у каждого портрета выводится credit + original + license
- Если свободного изображения нет — заглушка «нет свободного портрета» (не подставляем fair-use / пресс-фото)
- Покрытие растёт повторными запусками `fetch_commons_portraits.py` (скрипт умеет продолжать с места остановки; Wikimedia иногда отвечает 429 — нужны паузы)

Первый проход обычно закрывает далеко не всех: у многих современных спортсменов на Википедии только non-free фото. Это ожидаемо и правильнее, чем нарушать права.

## Публикация на GitHub Pages

Аккаунт проекта: **[nullchar0](https://github.com/nullchar0)**.

Ожидаемый URL сайта:

`https://nullchar0.github.io/vertical-world-anthology/`

```bash
# войти именно под nullchar0
gh auth logout -h github.com -u SillyHatsOnly 2>/dev/null || true
gh auth login -h github.com

git add .
git commit -m "Add Vertical World anthology GitHub Pages site"
gh repo create vertical-world-anthology --public --source=. --remote=origin --push

# Pages: Settings → Pages → Deploy from branch main / folder /docs
# или через CLI:
gh api -X POST repos/nullchar0/vertical-world-anthology/pages \
  -f build_type=legacy -f source[branch]=main -f source[path]=/docs
```

## Структура

```
docs/                 ← корень GitHub Pages
  index.html
  assets/
  content/            ← очищенные RU/EN
  media/
    catalog.json
    people_index.json
    portraits/
scripts/
  build_public_content.py
  fetch_commons_portraits.py
```
