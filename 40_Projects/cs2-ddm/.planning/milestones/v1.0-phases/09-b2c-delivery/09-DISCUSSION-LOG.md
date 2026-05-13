# Phase 9: B2C Delivery — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 09-b2c-delivery
**Areas discussed:** Deploy platform, Demo input + хранение, Формат отчёта, Email gate + processing model

---

## Deploy Platform

| Option | Description | Selected |
|-|-|-|
| Railway | Persistent volumes, managed Python, $5/mo | |
| Render | Free tier with cold starts, paid persistent disk | |
| Streamlit Community Cloud | Free, no persistent storage (loses .tri + analytics.db on restart) | |
| VPS (Hetzner/DO) | Full control, ~$5/mo, manual nginx/systemd setup | |
| Streamlit Community Cloud (no budget path) | Free, bundle analytics.db in repo | |
| Hugging Face Spaces | Free, 16GB RAM, Datasets repo for persistence | |
| Отложить deploy, HTML отчёт | Phase 9 = local HTML report, manual delivery; deploy = Phase 10 | ✓ |

**User's choice:** Нет бюджета на хостинг. Phase 9 = HTML report locally, ручная доставка. Deploy откладывается на Phase 10.
**Notes:** User explicitly said no budget for hosting right now.

---

## Demo Input + Хранение

| Option | Description | Selected |
|-|-|-|
| FACEIT URL | Пользователь даёт ссылку на матч, автоскачивание через FACEIT API. Проблема: 30-day approval. | |
| Пользователь отправляет .dem файл | Скачивает демку с FACEIT вручную, отправляет оператору (email/Telegram). Работает сейчас. | ✓ |
| SteamID + автозагрузка через FACEIT open API | Обойти 30-day approval через open API — нужно проверить. | |

**User's choice:** Пользователь отправляет демку вручную. FACEIT API approval начать в параллель.
**Notes:** Ручная доставка достаточна для early access объёма.

---

## Формат Отчёта

### Структура файла

| Option | Description | Selected |
|-|-|-|
| Self-contained HTML файл | Один .html, всё inline (CSS + данные + чарты base64). Открыть в браузере. | ✓ |
| PDF | Проще отправить, но чарты сложнее (нужен weasyprint/pdfkit). | |
| Streamlit st.download_button → HTML | Генерируется внутри аппа, пользователь скачивает сам. | |

**User's choice:** Self-contained HTML файл.

### Дизайн

| Option | Description | Selected |
|-|-|-|
| Terminal brand Djok | Тот же стиль что на landing: #0e0e12, gold accent, JetBrains Mono. | ✓ |
| Clean minimal (white bg) | Чистый репорт, проще печатать. | |

**User's choice:** Terminal brand Djok.

### Содержимое

**User's choice (free text):** "я хочу отдавать interpretation + чарты + сырые данные"
**Notes:** Три секции: (1) Interpretation tier table + worst metric card, (2) чарты (base64 inline), (3) raw engagements таблица.

---

## Email Gate + Processing Model

| Option | Description | Selected |
|-|-|-|
| Tally форма | Уже есть на landing. Собирает SteamID + email. Оператор получает submission → генерирует HTML вручную → отправляет. | ✓ |
| Email внутри аппа | Добавить input в Streamlit: SteamID + email перед анализом. Записывается в файл/Google Sheets. | |

**User's choice:** Tally форма (уже работает, не менять).
**Notes:** Processing model = sync (оператор запускает когда удобно). Async email delivery — Phase 10.

---

## Точка Входа Генерации

| Option | Description | Selected |
|-|-|-|
| CLI: `python generate_report.py <steamid>` | Отдельный скрипт, не нужен Streamlit. | |
| Streamlit st.download_button в Interpretation tab | Кнопка в существующем табе, работает и локально и при deploy. | ✓ |

**User's choice:** Streamlit st.download_button в Interpretation tab.

---

## Claude's Discretion

- HTML template approach (Jinja2 vs f-strings vs string concat)
- Chart sizing and layout within HTML
- Raw data table column ordering and highlight styling
- Exact section header wording

## Deferred Ideas

- Public deploy (Railway/Render/VPS) — Phase 10, нет бюджета сейчас
- FACEIT URL auto-download — заблокировано на API approval (30 дней)
- Unique shareable URL — требует server-side state, Phase 10 после deploy
- Automated email delivery (Resend/Mailchimp) — Phase 10
- PDF export — weasyprint/pdfkit добавляет сложность, HTML достаточно для MVP
