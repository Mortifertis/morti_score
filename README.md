# Morti Score

Morti Score — backend-сервис для демонстрационной футбольной
аналитики на FastAPI. Он объединяет REST API, дашборд, асинхронную
работу с БД, миграции Alembic, Redis-кэш и несколько простых моделей
прогнозирования результатов матчей на основе seed-данных из JSON.

## Что уже реализовано

- REST API для команд, матчей, турнирной таблицы, прогнозов и health-check.
- HTML-дашборд с последними матчами, ближайшими играми, таблицей и формой
  прогноза.
- Три модели прогнозирования:
  - базовая Poisson-модель;
  - улучшенная Poisson-модель с учетом формы и xG-прокси;
  - Elo-based модель.
- Асинхронный SQLAlchemy 2.x, Alembic-миграции и seed-данные из `data/`.
- Redis-кэш для прогнозов с настраиваемым in-memory fallback режимом.
- Опциональная demo-интеграция Telegram-бота через aiogram.
- Набор автотестов для API, дашборда, настроек, БД и миграций.


## Что демонстрирует проект

- Асинхронный backend на FastAPI.
- Архитектуру со слоями repository и service.
- Хранение данных в PostgreSQL и миграции Alembic.
- Кэширование прогнозов через Redis.
- Статистические модели прогнозирования на основе Poisson и Elo.
- Дашборд на Jinja2.
- Инфраструктуру Docker Compose.
- Непрерывную проверку качества кода через линтинг и тесты.

## Технологии

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x / asyncpg / aiosqlite
- Alembic
- Pydantic v2 / pydantic-settings
- Redis
- Jinja2
- Pytest / pytest-asyncio
- Ruff, Black, isort, flake8

## Быстрый старт локально

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e .[dev]
alembic upgrade head
python scripts/seed_data.py
uvicorn app.main:app --reload
```

После запуска:

- дашборд: <http://127.0.0.1:8000/dashboard>
- документация API: <http://127.0.0.1:8000/docs>
- health-check: <http://127.0.0.1:8000/health>

## Docker Compose

```bash
docker compose up --build
```

Основной `docker-compose.yml` поднимает приложение вместе с PostgreSQL и Redis
без монтирования локальной директории в контейнер. Для разработки с
auto-reload используйте:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Настройки окружения описаны в `app/core/config.py` и могут быть переопределены
переменными
окружения. Если Redis недоступен, `CACHE_FALLBACK_ENABLED=true` включает
резервный in-memory режим для локального запуска и тестов; для режима,
близкого к production, можно установить `CACHE_FALLBACK_ENABLED=false`.

## Команды для разработки

```bash
make install   # установка проекта с dev-зависимостями
make format    # black + isort
make lint      # ruff + flake8 + black --check + isort --check-only
make test      # python -m pytest
make migrate   # alembic upgrade head
make seed      # загрузка seed-данных
make run       # запуск uvicorn в режиме reload
```

## Основные API endpoints

- `GET /health` — проверка состояния сервиса.
- `GET /api/v1/teams` — список команд.
- `GET /api/v1/matches` — список матчей с фильтрами.
- `GET /api/v1/standings` — турнирная таблица.
- `POST /api/v1/predictions/match` — прогноз матча.
- `GET /api/v1/predictions/compare/{home_team_id}/{away_team_id}` — сравнение
  всех моделей прогнозирования.
- `POST /api/v1/admin/seed-data` — загрузка демонстрационных данных.

## Структура проекта

```text
app/
  api/            FastAPI routers и dependency providers
  bot/            optional Telegram demo integration
  core/           настройки, логирование, security helpers
  db/             SQLAlchemy session, Base и Redis-клиент
  models/         ORM-модели
  repositories/   слой доступа к данным
  schemas/        Pydantic-схемы
  services/       бизнес-логика и модели прогнозирования
  static/         CSS для дашборда
  templates/      Jinja2-шаблоны
alembic/          миграции БД
data/             демонстрационные команды и матчи
scripts/          утилиты для seed и миграций
tests/            автотесты
```

## Текущее состояние и ограничения

Проект реализован как рабочий backend MVP: его можно запустить локально,
проверить API через Swagger/OpenAPI и использовать dashboard для демонстрации
результатов. Текущая версия показывает основную бизнес-логику, работу с данными,
API и расчётными моделями, но пока не является production-ready решением.

## Идеи для дальнейшего развития

- Подключить внешний football data provider и автоматизировать импорт матчей.
- Добавить JWT-аутентификацию и роли для административных операций.
- Сохранять историю прогнозов и сравнивать их с фактическими результатами.
- Расширить dashboard графиками формы команд, Elo-рейтинга и качества моделей.
- Расширить CI/CD, добавить структурированное логирование и мониторинг.