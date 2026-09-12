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
Основной аккаунт машины (**SillyHatsOnly**) можно оставить активным по умолчанию — для *этого* репозитория используем nullchar0.

Ожидаемый URL сайта:

`https://nullchar0.github.io/vertical-world-anthology/`

### Два аккаунта в `gh` (рекомендуется)

```bash
# 1) починить/оставить основной аккаунт активным
gh auth login -h github.com
# выбери SillyHatsOnly → сделай его active (default)

# 2) ДОБАВИТЬ второй аккаунт, не выкидывая первый
gh auth login -h github.com
# выбери nullchar0 (Add an account)

gh auth status
# Active: SillyHatsOnly
# nullchar0 тоже Logged in
```

В этом репозитории уже прописано локально:

- `github.account=nullchar0` (новые версии `gh` подхватят pin)
- `credential.https://github.com.username=nullchar0`
- `user.name=nullchar0`

Пуш без смены глобального active-аккаунта:

```bash
# из корня проекта
./scripts/push-nullchar0.sh
# или вручную:
GH_TOKEN="$(gh auth token --user nullchar0)" gh repo create vertical-world-anthology --public --source=. --remote=origin --push
# если remote уже есть:
GH_TOKEN="$(gh auth token --user nullchar0)" git push -u origin main
```

Pages (`/docs`):

```bash
GH_TOKEN="$(gh auth token --user nullchar0)" gh api -X POST repos/nullchar0/vertical-world-anthology/pages \
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
