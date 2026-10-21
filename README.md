# Ремонтная мастерская «ФиксМастер»

Веб-приложение для мастерской по ремонту техники: клиент оформляет заявку с фото и следит за статусом
ремонта, мастер ведёт назначенные заявки и списывает запчасти, администратор распределяет работу, ведёт
прайс, склад и сотрудников и смотрит статистику.

Стек: Python 3.13+, Django 6.0, PostgreSQL 17, HTML/CSS/JS, Chart.js, Docker Compose.

## Документация

1. [Анализ предметной области и аналогов](docs/01-analysis.md)
2. [Функциональные и нефункциональные требования](docs/02-requirements.md)
3. [Архитектура, роли, статусы, маршруты](docs/03-architecture.md)
4. [База данных: ER-диаграмма, таблицы, ограничения](docs/04-database.md)
5. [Тестирование](docs/05-testing.md)
6. [Руководство пользователя](docs/06-user-guide.md)

## Запуск в Docker (PostgreSQL)

```sh
cp .env.example .env              # задать SECRET_KEY
docker compose up -d --build      # http://127.0.0.1:8100
docker compose exec web python manage.py seed_demo      # демо-данные
```

## Деплой на сервер

Продакшен работает на домашнем сервере `b450` (SSH-алиас `b450-remote`), каталог `~/repair`:
https://repair.37.194.184.235.sslip.io

```sh
deploy/deploy.sh b450-remote      # синхронизировать код и перезапустить стек
```

Первый запуск создаёт на сервере `~/repair/.env` со случайными `SECRET_KEY` и `DB_PASSWORD`.
Приложение слушает только `127.0.0.1:8110`, наружу его отдаёт Apache — настройка в
`deploy/apache-repair.conf` (ставится один раз от root, вместе с сертификатом certbot).
Пароль демо-учёток на сервере: `DEMO_PASSWORD` в `~/repair/.env`.

## Локальный запуск для разработки (SQLite)

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo                    # или createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8100
```

Без переменной `DB_NAME` используется SQLite (`db.sqlite3`), с ней — PostgreSQL (см. `.env.example`).

Демо-входы после `seed_demo`: `client`, `master1`, `admin`; пароль `demo12345`
(свой пароль: `seed_demo --password ...`).

## Тесты

```sh
.venv/bin/python manage.py test
```

## Структура

```
config/      настройки и корневые URL
apps/
  accounts/  пользователи и роли
  catalog/   типы устройств и услуги
  repairs/   заявки, статусы, комментарии, фото, запчасти в ремонте
  inventory/ склад и журнал движений
  dashboard/ панель администратора и статистика
templates/   HTML-шаблоны
static/      CSS и JS
docs/        документация
```
