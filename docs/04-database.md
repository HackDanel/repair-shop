# 4. База данных

СУБД — PostgreSQL 17. Схема создаётся миграциями Django (`python manage.py migrate`).

## 4.1. ER-диаграмма

```mermaid
erDiagram
  accounts_user ||--o{ repairs_repairrequest : "клиент (client_id)"
  accounts_user |o--o{ repairs_repairrequest : "мастер (master_id)"
  catalog_devicetype ||--o{ catalog_service : ""
  catalog_devicetype ||--o{ repairs_repairrequest : ""
  catalog_service |o--o{ repairs_repairrequest : ""
  catalog_devicetype }o--o{ inventory_part : "inventory_part_device_types"
  repairs_repairrequest ||--o{ repairs_statuschange : ""
  repairs_repairrequest ||--o{ repairs_comment : ""
  repairs_repairrequest ||--o{ repairs_photo : ""
  repairs_repairrequest ||--o{ repairs_partusage : ""
  inventory_part ||--o{ repairs_partusage : ""
  inventory_part ||--o{ inventory_stockmovement : ""
  repairs_repairrequest |o--o{ inventory_stockmovement : ""
  accounts_user |o--o{ repairs_statuschange : "автор"
  accounts_user |o--o{ repairs_comment : "автор"
  accounts_user |o--o{ inventory_stockmovement : "автор"

  accounts_user {
    bigint id PK
    varchar username UK
    varchar email UK
    varchar password "хеш PBKDF2"
    varchar first_name
    varchar last_name
    varchar phone
    varchar role "client | master | admin"
    bool is_active
  }
  catalog_devicetype {
    bigint id PK
    varchar name UK
  }
  catalog_service {
    bigint id PK
    bigint device_type_id FK
    varchar name
    text description
    numeric price_from "CHECK >= 0"
    smallint duration_days
    bool is_active
  }
  repairs_repairrequest {
    bigint id PK
    uuid tracking_code UK
    bigint client_id FK
    bigint device_type_id FK
    varchar device_model
    varchar serial_number
    bigint service_id FK "NULL"
    text problem
    varchar status "индекс"
    bigint master_id FK "NULL"
    numeric labor_cost "CHECK >= 0"
    timestamptz created_at "индекс"
    timestamptz updated_at
    timestamptz issued_at "NULL"
  }
  repairs_statuschange {
    bigint id PK
    bigint request_id FK
    varchar old_status
    varchar new_status
    bigint author_id FK
    timestamptz created_at
  }
  repairs_comment {
    bigint id PK
    bigint request_id FK
    bigint author_id FK
    text text
    bool is_internal
    timestamptz created_at
  }
  repairs_photo {
    bigint id PK
    bigint request_id FK
    varchar image
    timestamptz uploaded_at
  }
  repairs_partusage {
    bigint id PK
    bigint request_id FK
    bigint part_id FK
    int quantity "CHECK >= 1"
    numeric unit_price
    timestamptz created_at
  }
  inventory_part {
    bigint id PK
    varchar sku UK
    varchar name
    numeric price "CHECK >= 0"
    int quantity "CHECK >= 0"
    int min_quantity
  }
  inventory_stockmovement {
    bigint id PK
    bigint part_id FK
    varchar kind "income | usage | return | adjust"
    int delta "CHECK <> 0"
    bigint request_id FK "NULL"
    bigint author_id FK
    varchar note
    timestamptz created_at
  }
```

## 4.2. Таблицы

| Таблица | Назначение |
|---|---|
| `accounts_user` | Пользователи всех ролей. Расширяет стандартного пользователя Django полями `role`, `phone`; `email` уникален |
| `catalog_devicetype` | Справочник типов устройств |
| `catalog_service` | Услуги прайса с ценой «от» и сроком |
| `repairs_repairrequest` | Заявки на ремонт — центральная таблица |
| `repairs_statuschange` | Журнал смены статусов (аудит: кто и когда) |
| `repairs_comment` | Комментарии к заявке; `is_internal` скрывает комментарий от клиента |
| `repairs_photo` | Фото устройства, файл хранится на диске, в БД — путь |
| `repairs_partusage` | Запчасти, использованные в ремонте; цена фиксируется на момент списания |
| `inventory_part` | Запчасти на складе и текущий остаток |
| `inventory_part_device_types` | Связь «многие ко многим»: к каким типам устройств подходит запчасть |
| `inventory_stockmovement` | Журнал движений склада; сумма `delta` по запчасти объясняет её остаток |

## 4.3. Ограничения целостности

| Ограничение | Таблица | Смысл |
|---|---|---|
| `UNIQUE(username)`, `UNIQUE(email)` | `accounts_user` | Один аккаунт на логин и почту |
| `UNIQUE(name)` | `catalog_devicetype` | Нет дублей типов |
| `uniq_service_per_device` — `UNIQUE(device_type_id, name)` | `catalog_service` | Одна услуга с таким названием на тип устройства |
| `service_price_non_negative` — `CHECK(price_from >= 0)` | `catalog_service` | Цена не отрицательная |
| `request_labor_non_negative` — `CHECK(labor_cost >= 0)` | `repairs_repairrequest` | Стоимость работ не отрицательная |
| `UNIQUE(tracking_code)` | `repairs_repairrequest` | Код для публичной проверки статуса |
| `usage_quantity_positive` — `CHECK(quantity >= 1)` | `repairs_partusage` | Списывается хотя бы одна штука |
| `part_price_non_negative`, `CHECK(quantity >= 0)` | `inventory_part` | Остаток не уходит в минус (тип `PositiveIntegerField`) |
| `UNIQUE(sku)` | `inventory_part` | Уникальный артикул |
| `movement_delta_not_zero` — `CHECK(delta <> 0)` | `inventory_stockmovement` | Пустых движений нет |

Внешние ключи:

- `ON DELETE PROTECT`: клиент заявки, тип устройства, тип услуги, запчасть в ремонте. Нельзя удалить запись,
  на которую ссылается история.
- `ON DELETE SET NULL`: мастер, услуга, автор комментария, движения и смены статуса. История остаётся, если
  сотрудника удалили.
- `ON DELETE CASCADE`: фото, комментарии, история статусов и запчасти заявки удаляются вместе с заявкой.

Индексы: по `status` и `created_at` заявки (фильтры списков и статистика), плюс индексы, которые Django
создаёт для всех внешних ключей.
