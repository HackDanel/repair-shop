# 8. Развёртывание и сопровождение

## 8.1. Схема

![Схема развёртывания](img/diagram_deployment.png)

| Компонент | Где | Детали |
|---|---|---|
| Сервер | `b450`, Debian 13, Docker 26 | SSH-алиас `b450-remote` (внешний IP, порт 5483) |
| Каталог стека | `~/repair` | `docker-compose.yml`, `.env`, `src/`, `backup.sh`, `backups/` |
| Приложение | контейнер `repair-web-1` | Gunicorn, 3 процесса, слушает `127.0.0.1:8110` |
| БД | контейнер `repair-db-1` | PostgreSQL 17, порт наружу не открыт, том `repair_pgdata` |
| Фото | том `repair_media` | смонтирован в `/app/media` |
| Веб-сервер | Apache 2.4 | `zz-repair.conf` и `zz-repair-le-ssl.conf`, обратный прокси, лимит тела запроса 30 МБ |
| Домен | https://repair.37.194.184.235.sslip.io | сертификат Let's Encrypt, HTTP перенаправляется на HTTPS |

На сервере работают и другие сервисы (kanban, coffee, filebrowser, Redmine, Nextcloud). Стек
изолирован в отдельном проекте Compose `repair` и не публикует порты на внешний интерфейс.

## 8.2. Требования

- Сервер: Linux, Docker Engine 24+ с плагином `docker compose`, Apache 2.4 с модулями `proxy`, `proxy_http`,
  `headers`, `ssl`, certbot.
- Машина разработчика: `ssh`, `rsync`, доступ к серверу по ключу.
- Ресурсы: ≈ 180 МБ RAM в работе (Gunicorn ≈ 145 МБ, PostgreSQL ≈ 35 МБ), ≈ 500 МБ диска под образы, плюс место под фото и бэкапы.

## 8.3. Первая установка

1. Скопировать код и запустить стек (создаёт `~/repair/.env` со случайными `SECRET_KEY` и `DB_PASSWORD`):

   ```sh
   deploy/deploy.sh b450-remote                 # [каталог] [домен] — необязательные аргументы
   ```

2. Подключить Apache и выпустить сертификат (на сервере, от root):

   ```sh
   sudo cp ~/repair/apache-repair.conf /etc/apache2/sites-available/zz-repair.conf
   sudo a2ensite zz-repair && sudo apache2ctl configtest && sudo systemctl reload apache2
   sudo certbot --apache -d repair.37.194.184.235.sslip.io
   ```

3. Создать администратора **или** загрузить демо-данные:

   ```sh
   ssh b450-remote 'cd repair && docker compose exec web python manage.py createsuperuser'
   ssh b450-remote 'cd repair && docker compose exec -T web python manage.py seed_demo --password <пароль>'
   ```

Миграции применяются автоматически при каждом старте контейнера `web`.

## 8.4. Обновление

```sh
git pull                        # или свои изменения
.venv/bin/python manage.py test # тесты зелёные — можно выкладывать
deploy/deploy.sh b450-remote    # rsync кода, пересборка образа, перезапуск web
```

Простой — несколько секунд, пока перезапускается контейнер `web`. База и фото лежат в томах и не
затрагиваются.

## 8.5. Резервное копирование и восстановление

```sh
ssh b450-remote 'cd repair && ./backup.sh'      # дамп БД + архив фото в ~/repair/backups, хранятся 14 последних
```

Для ежедневного бэкапа на сервере выполнить `crontab -e` и добавить строку:

```
30 3 * * * cd $HOME/repair && ./backup.sh >> backups/backup.log 2>&1
```

Восстановление (останавливает приложение, база заменяется целиком):

```sh
cd ~/repair
docker compose stop web
docker compose exec -T db pg_restore -U repair -d repair --clean --if-exists < backups/db_<дата>.dump
docker compose run --rm -T web tar -C /app -xzf - < backups/media_<дата>.tar.gz
docker compose start web
```

## 8.6. Диагностика

| Что проверить | Команда |
|---|---|
| Состояние контейнеров | `ssh b450-remote 'cd repair && docker compose ps'` |
| Логи приложения | `ssh b450-remote 'cd repair && docker compose logs --tail 100 web'` |
| Ответ приложения в обход Apache | `ssh b450-remote 'curl -sI -H "Host: repair.37.194.184.235.sslip.io" http://127.0.0.1:8110/'` |
| Логи Apache | `/var/log/apache2/repair-error.log`, `repair-access.log` |
| Срок сертификата | `sudo certbot certificates` |

Типовые проблемы:

| Симптом | Причина и решение |
|---|---|
| 400 Bad Request | домен не входит в `ALLOWED_HOSTS` — проверить `DOMAIN` в `~/repair/.env` |
| 403 CSRF при входе | открыто по HTTP или с другого домена; вход работает только по HTTPS на домене из `DOMAIN` |
| 413 при загрузке фото | превышен `LimitRequestBody` в Apache (30 МБ) |
| 502 Bad Gateway | контейнер `web` не запущен — смотреть `docker compose logs web` |

## 8.7. Локальный запуск

См. [README](../README.md): SQLite и `runserver` для разработки или `docker compose up` из корня репозитория
для проверки с PostgreSQL (порты 8100 и 5434).
