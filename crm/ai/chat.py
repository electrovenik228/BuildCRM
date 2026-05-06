import re

from django.conf import settings
from django.db.models import Avg, Count, Q, Sum

from crm.models import Apartment, Deal


def answer_chat(message):
    text = message.strip()
    normalized = text.lower()

    smalltalk_answer = _answer_smalltalk(normalized)
    if smalltalk_answer:
        return smalltalk_answer

    rule_answer = _answer_with_rules(normalized)
    if rule_answer:
        return rule_answer

    if _is_construction_consulting_question(normalized):
        consulting_answer = _answer_construction_consulting(text)
        if consulting_answer:
            return {
                "answer": consulting_answer,
                "data": {},
                "source": "gemini_consulting",
            }

    crm_context = _build_crm_context()
    gemini_answer = _answer_with_gemini(text, crm_context)
    if gemini_answer:
        return {
            "answer": gemini_answer,
            "data": crm_context,
            "source": "gemini",
        }

    return {
        "answer": "Я пока умею отвечать по квартирам, статусам, продажам и базовым KPI. Попробуйте: 'сколько свободных квартир?' или 'покажи 2-комнатные до 80000'.",
        "data": crm_context,
        "source": "fallback",
    }


def _answer_with_rules(normalized):
    if _contains_any(normalized, ["дашборд", "dashboard", "статистика", "kpi", "итоги"]):
        data = _dashboard_data()
        return {
            "answer": _format_dashboard(data),
            "data": data,
            "source": "rules",
        }

    if _contains_any(normalized, ["сколько", "count", "количество"]):
        status = _extract_status(normalized)
        rooms = _extract_rooms(normalized)
        queryset = Apartment.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        if rooms:
            queryset = queryset.filter(rooms=rooms)
        count = queryset.count()
        label = _status_label(status) if status else "всего"
        room_part = f" {rooms}-комнатных" if rooms else ""
        return {
            "answer": f"Сейчас {label}{room_part} квартир: {count}.",
            "data": {"count": count, "status": status, "rooms": rooms},
            "source": "rules",
        }

    if _contains_any(normalized, ["покажи", "найди", "список", "квартир"]):
        status = _extract_status(normalized)
        rooms = _extract_rooms(normalized)
        max_price = _extract_max_price(normalized)
        apartments = _search_apartments(status=status, rooms=rooms, max_price=max_price)
        return {
            "answer": _format_apartments(apartments),
            "data": {
                "apartments": apartments,
                "filters": {"status": status, "rooms": rooms, "max_price": max_price},
            },
            "source": "rules",
        }

    if _contains_any(normalized, ["выручка", "сумма продаж", "revenue"]):
        total = Deal.objects.filter(status=Deal.Status.CLOSED).aggregate(total=Sum("final_price"))["total"] or 0
        return {
            "answer": f"Закрытая выручка по сделкам: ${total}.",
            "data": {"closed_revenue": str(total)},
            "source": "rules",
        }

    if _contains_any(normalized, ["средний чек", "average", "avg"]):
        avg = Deal.objects.filter(status=Deal.Status.CLOSED).aggregate(avg=Avg("final_price"))["avg"] or 0
        return {
            "answer": f"Средний чек по закрытым сделкам: ${avg}.",
            "data": {"average_closed_deal": str(avg)},
            "source": "rules",
        }

    return None


def _answer_smalltalk(normalized):
    normalized = normalized.strip(" ?!.,")
    if not normalized:
        return None

    if normalized in {"привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер", "hello", "hi"}:
        return {
            "answer": "Здравствуйте. Могу помочь по квартирам, продажам, остаткам и базовым KPI.",
            "data": {},
            "source": "smalltalk",
        }

    if normalized in {"как дела", "как ты", "как дела?", "как ты?"}:
        return {
            "answer": "Работаю в штатном режиме. Могу подсказать статистику по CRM или найти квартиры по параметрам.",
            "data": {},
            "source": "smalltalk",
        }

    if normalized in {"что", "что?", "не понял", "не поняла", "поясни"}:
        return {
            "answer": "Я отвечаю на вопросы по CRM. Например: 'сколько свободных квартир?', 'покажи 2-комнатные до 80000' или 'какая выручка?'.",
            "data": {},
            "source": "smalltalk",
        }

    return None


def _is_construction_consulting_question(normalized):
    consulting_markers = [
        "строитель",
        "недвиж",
        "девелоп",
        "застрой",
        "монолит",
        "панель",
        "кирпич",
        "каркас",
        "фундамент",
        "перекрыт",
        "фасад",
        "отделк",
        "ремонт",
        "планиров",
        "ипотек",
        "рассроч",
        "клиент",
        "покупател",
        "продаж",
        "объясн",
        "возражен",
        "аргумент",
        "презентац",
        "квартир",
        "дом",
        "жк",
    ]
    return _contains_any(normalized, consulting_markers)


def _dashboard_data():
    counts = dict(Apartment.objects.values_list("status").annotate(count=Count("id")))
    return {
        "total": sum(counts.values()),
        "sold": counts.get(Apartment.Status.SOLD, 0),
        "available": counts.get(Apartment.Status.AVAILABLE, 0),
        "reserved": counts.get(Apartment.Status.RESERVED, 0),
    }


def _build_crm_context():
    dashboard = _dashboard_data()
    deals = Deal.objects.aggregate(
        total=Count("id"),
        closed=Count("id", filter=Q(status=Deal.Status.CLOSED)),
    )
    return {
        "dashboard": dashboard,
        "deals": deals,
    }


def _answer_with_gemini(message, crm_context):
    prompt = (
        "You are an assistant inside a real estate CRM. "
        "Answer in Russian and be concise. "
        "Use the provided CRM context only when the user asks about CRM data, apartments, buildings, sales, deals, revenue, or KPIs. "
        "For greetings, casual phrases, unclear one-word messages, or non-CRM questions, do not invent CRM analytics; ask the user to clarify or explain what CRM questions you can answer. "
        "If CRM context is insufficient for a CRM question, say what data is missing.\n\n"
        f"CRM context: {crm_context}\n\n"
        f"User question: {message}"
    )
    return _generate_gemini_content(prompt)


def _answer_construction_consulting(message):
    prompt = (
        "You are a Russian-speaking consultant for a construction and real estate sales CRM. "
        "Answer practical questions about construction, residential real estate, apartment sales, buyer objections, mortgages, installments, layouts, finishing, and building types. "
        "Be concise, useful for a sales manager, and avoid claiming access to CRM data. "
        "Prefer 4-6 short bullets or a short client-facing script. "
        "If the question requires current laws, exact bank rates, legal/tax advice, or project-specific technical documentation, say that it should be checked with the relevant specialist or current source.\n\n"
        f"User question: {message}"
    )
    return _generate_gemini_content(prompt)


def _generate_gemini_content(prompt):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return None

    try:
        from google import genai
    except ImportError:
        return None

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
        )
    except Exception:
        return None

    return getattr(response, "text", None)


def _search_apartments(status=None, rooms=None, max_price=None):
    queryset = Apartment.objects.select_related("building", "floor", "building__complex")
    if status:
        queryset = queryset.filter(status=status)
    if rooms:
        queryset = queryset.filter(rooms=rooms)
    if max_price:
        queryset = queryset.filter(price__lte=max_price)

    return [
        {
            "id": apartment.id,
            "complex": apartment.building.complex.name,
            "building": apartment.building.name,
            "floor": apartment.floor.number,
            "number": apartment.number,
            "rooms": apartment.rooms,
            "area": str(apartment.area),
            "price": str(apartment.price),
            "status": apartment.status,
            "payment_type": apartment.payment_type,
        }
        for apartment in queryset.order_by("price", "building_id", "floor__number", "number")[:10]
    ]


def _format_dashboard(data):
    return (
        f"Всего квартир: {data['total']}. "
        f"Свободно: {data['available']}, забронировано: {data['reserved']}, продано: {data['sold']}."
    )


def _format_apartments(apartments):
    if not apartments:
        return "По этим фильтрам квартиры не найдены."

    lines = ["Нашел квартиры:"]
    for apartment in apartments:
        lines.append(
            f"#{apartment['id']} {apartment['building']}, кв. {apartment['number']}, "
            f"этаж {apartment['floor']}, {apartment['rooms']} комн., "
            f"{apartment['area']} м2, цена ${apartment['price']}, статус {apartment['status']}."
        )
    return "\n".join(lines)


def _extract_status(normalized):
    if _contains_any(normalized, ["свобод", "available"]):
        return Apartment.Status.AVAILABLE
    if _contains_any(normalized, ["брон", "резерв", "reserved"]):
        return Apartment.Status.RESERVED
    if _contains_any(normalized, ["продан", "sold"]):
        return Apartment.Status.SOLD
    return None


def _extract_rooms(normalized):
    match = re.search(r"(\d+)\s*[- ]?\s*(комн|room)", normalized)
    if not match:
        return None
    return int(match.group(1))


def _extract_max_price(normalized):
    match = re.search(r"(?:до|under|<=)\s*(\d+(?:[\s_]?\d+)*)", normalized)
    if not match:
        return None
    return int(match.group(1).replace(" ", "").replace("_", ""))


def _status_label(status):
    return {
        Apartment.Status.AVAILABLE: "свободных",
        Apartment.Status.RESERVED: "забронированных",
        Apartment.Status.SOLD: "проданных",
    }.get(status, "всего")


def _contains_any(text, needles):
    return any(needle in text for needle in needles)
