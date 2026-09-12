# Портреты для сайта

Сайт читает только:

- `docs/media/portraits/<slug>.jpg|png|webp` — файл картинки  
- `docs/media/catalog.json` — автор, лицензия, ссылка на источник  
- `docs/media/people_index.json` — список людей со `slug` (собирается из ссылок в тексте)

`slug` человека смотрите в `people_index.json` (например `messner-rainhold`, `rob-hall`).

## Автоматически (открытые лицензии)

```bash
python3 scripts/fetch_open_portraits.py --allow-remote
python3 scripts/enrich_catalog_attribution.py
```

Берутся только свободные лицензии (CC0 / PD / CC BY / CC BY-SA и аналоги).  
Fair use / «все права защищены» с Википедии **не** скачиваются.

## Вручную — после разрешения автора

1. Получите письменное разрешение (email достаточно) на публикацию на сайте антологии с указанием автора.
2. Положите файл куда угодно на диск и зарегистрируйте:

```bash
python3 scripts/add_manual_portrait.py \
  --slug rob-hall \
  --file ~/Downloads/rob-hall-permission.jpg \
  --artist "Имя Фамилия фотографа" \
  --source-url "https://… или mailto:/ссылка на письмо" \
  --license "Permission from author for non-commercial web use on vertical-world-anthology" \
  --note "Permission email 2026-09-12"
```

Скрипт скопирует файл в `docs/media/portraits/` и обновит `catalog.json`.

3. Закоммитьте и запушьте:

```bash
git add docs/media/portraits/<slug>.* docs/media/catalog.json
git commit -m "Add portrait for <name> with author permission"
./scripts/push-nullchar0.sh
```

После деплоя GitHub Pages портрет появится у карточки с этим `slug`.

### Если человека ещё нет в индексе

В тексте антологии (`docs/content/ru.md` / `en.md`) должна быть ссылка на человека, затем:

```bash
python3 scripts/build_people_index.py
```

После этого появится `slug`, и можно вызывать `add_manual_portrait.py`.

## Что писать в credit на сайте

Минимум:

- имя автора / правообладателя  
- ссылка на оригинал или на запись о разрешении  
- краткая формулировка лицензии/разрешения  

Сайт показывает эти поля из `catalog.json` под фото.
