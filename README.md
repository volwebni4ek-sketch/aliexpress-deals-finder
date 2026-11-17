# AliExpress Deals Finder

Інструмент для пошуку вигідних товарів на AliExpress з урахуванням **реальної вартості (ціна + доставка)**, знижок, промокодів/купонів та моніторингу падіння цін.

## Можливості

- **Робота без API-ключів (за замовчуванням):** `DirectWebSearchProvider` парсить структурований JSON зі сторінки пошуку AliExpress (без потреби в `App Key`), з вбудованим захистом від rate-limit та явним виявленням CAPTCHA/антибот-сторінок.
- **Підключаємі провайдери:**
  - `web` — прямий пошук по AliExpress (без ключів).
  - `rapidapi` — адаптер під RapidAPI AliExpress Scraper (опційно, якщо є безкоштовний ключ).
  - `official` — адаптер під офіційний AliExpress Open Platform Affiliate API (`App Key` / `App Secret`).
  - `mock` — офлайн-провайдер для тестів та локальної демонстрації.
- **Розумна фільтрація та скоринг (`deal_score`):**
  - Розрахунок `total_cost = sale_price + shipping_cost`.
  - Фільтри: `min_price`, `max_price`, `max_total_cost`, `free_shipping_only`, `min_discount_pct`, `min_rating`, `min_orders`.
  - Сортування за вигодою (`best_deal`), загальною ціною, знижкою, кількістю замовлень або рейтингом.
- **Моніторинг цін і промокодів (SQLite):**
  - Збереження історії цін та купонів/промокодів.
  - Виявлення падіння ціни, появи нових промокодів та спрацьовування цільової ціни.
- **CLI та FastAPI REST API.**

## Швидкий старт

```bash
# 1. Встановлення залежностей через uv
uv sync --extra dev

# 2. Демо-пошук на тестових даних (працює офлайн)
uv run aliexpress-deals search "mechanical keyboard" --provider mock --max-total-cost 60 --sort best_deal

# 3. Живий пошук через веб-парсер (без API-ключів)
uv run aliexpress-deals search "usb c hub" --provider web --free-shipping --min-rating 4.5

# 4. Запуск REST API сервера
uv run uvicorn aliexpress_deals.api:app --reload
```

## Тести

```bash
uv run pytest
```
