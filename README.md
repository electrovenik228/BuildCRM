# BuildCRM AI

BuildCRM AI - это CRM-система для строительной компании и отдела продаж недвижимости.

Проект помогает вести учет жилых комплексов, домов, этажей, квартир, клиентов и сделок. Также есть визуальная схема дома, дашборд по продажам и AI-чат для быстрых вопросов по базе.

## Для обычных пользователей

### Что можно делать в системе

- Смотреть все квартиры по домам и этажам.
- Видеть статус каждой квартиры цветом.
- Быстро понимать, какие квартиры свободны, забронированы или проданы.
- Открывать карточку квартиры и смотреть детали: этаж, площадь, комнатность, цена, тип оплаты.
- Смотреть общий дашборд по остаткам квартир.
- Работать с клиентами и сделками через админ-панель.
- Задавать вопросы AI-чату по CRM.

### Цвета квартир

```text
Зеленый  - квартира свободна
Желтый   - квартира забронирована
Красный  - квартира продана
Синий    - квартира с ипотекой
```

Если квартира синяя, это значит, что у нее тип оплаты `mortgage`.

### Главная страница

На главной странице отображаются:

- общее количество квартир;
- сколько квартир свободно;
- сколько забронировано;
- сколько продано;
- список домов;
- AI-чат.

Адрес локально:

```text
http://127.0.0.1:8000/
```

### Страница дома

На странице дома квартиры показаны по этажам.

Каждая квартира - отдельная карточка. По нажатию на карточку открывается окно с деталями квартиры.

Пример адреса:

```text
http://127.0.0.1:8000/buildings/1/
```

### AI-чат

AI-чат можно использовать для быстрых вопросов по CRM.

Примеры вопросов:

```text
Сколько свободных квартир?
Покажи дашборд
Покажи 2-комнатные до 80000
Сколько проданных квартир?
Какая выручка?
Какой средний чек?
```

Если подключен Gemini API, чат сможет отвечать более свободно. Если Gemini не подключен, базовые вопросы все равно работают локально.

### Админ-панель

Через админ-панель можно управлять данными:

- жилыми комплексами;
- домами;
- этажами;
- квартирами;
- клиентами;
- сделками;
- историей AI-чата.

Адрес:

```text
http://127.0.0.1:8000/admin/
```

## Техническое описание

BuildCRM AI is a Django + DRF MVP for a real estate construction CRM.

It includes:

- Residential structure: complex -> building -> floor -> apartment
- Apartment statuses and visual building grid
- Deals and clients
- Dashboard API and UI
- Basic AI chat with local rule-based answers and optional Gemini fallback
- Django Admin with Jazzmin

## Tech Stack

- Python 3.12
- Django 6
- Django REST Framework
- SQLite for minimal local/demo setup
- WhiteNoise for static files
- Gunicorn for production web server
- Google Gemini via `google-genai` optional

## Project Structure

```text
core/                  Django project settings and root URLs
crm/                   Main CRM app
crm/ai/chat.py         AI chat service
crm/templates/crm/     Django templates UI
crm/static/crm/        UI CSS and JS
crm/management/commands/seed_demo.py
crm/management/commands/ensure_superuser.py
build.sh              Render build script
start.sh              Render start script
requirements.txt      Python dependencies
```

## Local Setup

Create and activate virtual environment if needed:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply migrations:

```bash
python manage.py migrate
```

Create demo data:

```bash
python manage.py seed_demo
```

Create a local admin user manually:

```bash
python manage.py createsuperuser
```

Run server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Admin:

```text
http://127.0.0.1:8000/admin/
```

API root:

```text
http://127.0.0.1:8000/api/
```

## Demo Data

The command below creates a demo complex, building, floors and apartments:

```bash
python manage.py seed_demo
```

It creates:

- Complex: `Green Yard`
- Building: `Tower A`
- 8 floors
- 4 apartments per floor
- mixed statuses: `available`, `reserved`, `sold`
- mixed payment types: `cash`, `mortgage`, `installment`

The command is idempotent and does not overwrite existing demo apartments.

## AI Chat

Endpoint:

```http
POST /api/ai/chat/
```

Example:

```json
{
  "message": "Покажи 2-комнатные до 80000"
}
```

The chat works in two modes:

- Local rule-based mode if `GEMINI_API_KEY` is empty
- Gemini fallback if `GEMINI_API_KEY` is set

Supported local questions include:

- apartment counts
- dashboard summary
- apartment search by rooms/status/price
- revenue
- average closed deal value

## Environment Variables

Use `.env.example` as a reference.

Important variables:

```text
DEBUG=True
SECRET_KEY=change-me
ALLOWED_HOSTS=127.0.0.1,localhost,.onrender.com
CSRF_TRUSTED_ORIGINS=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=change-this-password
```

This project currently reads environment variables directly from the process environment. If you want automatic `.env` loading locally, add `python-dotenv` or use shell exports.

## Render Deployment

Create a Render Web Service from the Git repository.

Recommended fields:

```text
Runtime: Python 3
Build Command: ./build.sh
Start Command: ./start.sh
```

If the repository root is the project folder, leave `Root Directory` empty.

If the project is inside a subfolder, set:

```text
Root Directory: BuildCRM
```

Render environment variables:

```text
DEBUG=False
SECRET_KEY=<long-random-secret>
ALLOWED_HOSTS=.onrender.com
CSRF_TRUSTED_ORIGINS=https://your-service-name.onrender.com
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=<strong-password>
GEMINI_API_KEY=<your-gemini-token>
GEMINI_MODEL=gemini-2.5-flash
```

`start.sh` runs:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py ensure_superuser
python -m gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

## SQLite Warning on Render

This minimal setup uses SQLite to launch quickly without PostgreSQL.

On Render, the default filesystem is ephemeral. This means uploaded/generated data can disappear after redeploys or restarts.

For a real deployment, switch to PostgreSQL and remove demo seeding from `start.sh`.

## Useful API Endpoints

```text
GET    /api/apartments/
GET    /api/apartments/{id}/
POST   /api/apartments/
PATCH  /api/apartments/{id}/

POST   /api/buildings/

POST   /api/deals/
PATCH  /api/deals/{id}/

GET    /api/dashboard/
POST   /api/ai/chat/
GET    /api/ai/chat/history/
```

## Tests

Run tests:

```bash
python manage.py test crm
```

Run Django system checks:

```bash
python manage.py check
```
