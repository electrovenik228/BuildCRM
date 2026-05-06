from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import AIChatMessage, Apartment, Building, Client, ClientNote, Deal, Floor, ResidentialComplex


class BuildingGenerationTests(APITestCase):
    def test_building_create_generates_floors_and_apartments(self):
        complex_obj = ResidentialComplex.objects.create(name="Green Yard", address="Main street")

        response = self.client.post(
            "/api/buildings/",
            {
                "complex": complex_obj.id,
                "name": "Tower A",
                "floors_count": 4,
                "apartments_per_floor": 3,
                "default_rooms": 2,
                "default_area": "58.50",
                "default_price": "75000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        building = Building.objects.get(pk=response.data["id"])
        self.assertEqual(Floor.objects.filter(building=building).count(), 4)
        self.assertEqual(Apartment.objects.filter(building=building).count(), 12)
        self.assertTrue(Apartment.objects.filter(building=building, number="4-3").exists())


class DealRulesTests(APITestCase):
    def setUp(self):
        complex_obj = ResidentialComplex.objects.create(name="Build City", address="Central")
        self.building = Building.objects.create(complex=complex_obj, name="B1", floors_count=1)
        self.floor = Floor.objects.create(building=self.building, number=1)
        self.apartment = Apartment.objects.create(
            building=self.building,
            floor=self.floor,
            number="1-1",
            rooms=1,
            area=Decimal("40.00"),
            price=Decimal("50000.00"),
        )
        self.client_obj = Client.objects.create(full_name="Aman User", phone="+996700000000", source="site")

    def test_deal_creation_reserves_apartment_and_blocks_second_active_deal(self):
        response = self.client.post(
            "/api/deals/",
            {
                "client": self.client_obj.id,
                "apartment": self.apartment.id,
                "status": Deal.Status.LEAD,
                "final_price": "49000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.apartment.refresh_from_db()
        self.assertEqual(self.apartment.status, Apartment.Status.RESERVED)

        second_response = self.client.post(
            "/api/deals/",
            {
                "client": self.client_obj.id,
                "apartment": self.apartment.id,
                "status": Deal.Status.IN_PROGRESS,
                "final_price": "48000.00",
            },
            format="json",
        )
        self.assertEqual(second_response.status_code, 400)

    def test_closing_deal_sells_apartment_and_sold_apartment_is_not_editable(self):
        deal = Deal.objects.create(client=self.client_obj, apartment=self.apartment, final_price=Decimal("49000.00"))
        self.apartment.status = Apartment.Status.RESERVED
        self.apartment.save(update_fields=["status"])

        response = self.client.patch(f"/api/deals/{deal.id}/", {"status": Deal.Status.CLOSED}, format="json")
        self.assertEqual(response.status_code, 200)
        self.apartment.refresh_from_db()
        self.assertEqual(self.apartment.status, Apartment.Status.SOLD)

        apartment_response = self.client.patch(
            f"/api/apartments/{self.apartment.id}/",
            {"price": "51000.00"},
            format="json",
        )
        self.assertEqual(apartment_response.status_code, 400)

    def test_canceling_active_deal_releases_apartment(self):
        response = self.client.post(
            "/api/deals/",
            {
                "client": self.client_obj.id,
                "apartment": self.apartment.id,
                "status": Deal.Status.IN_PROGRESS,
                "final_price": "49000.00",
                "reserved_until": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.apartment.refresh_from_db()
        self.assertEqual(self.apartment.status, Apartment.Status.RESERVED)

        cancel_response = self.client.patch(
            f"/api/deals/{response.data['id']}/",
            {"status": Deal.Status.CANCELED},
            format="json",
        )

        self.assertEqual(cancel_response.status_code, 200)
        self.apartment.refresh_from_db()
        self.assertEqual(self.apartment.status, Apartment.Status.AVAILABLE)

    def test_lost_deal_releases_apartment(self):
        deal = Deal.objects.create(client=self.client_obj, apartment=self.apartment, final_price=Decimal("49000.00"))
        self.apartment.status = Apartment.Status.RESERVED
        self.apartment.save(update_fields=["status"])

        response = self.client.patch(f"/api/deals/{deal.id}/", {"status": Deal.Status.LOST}, format="json")

        self.assertEqual(response.status_code, 200)
        self.apartment.refresh_from_db()
        self.assertEqual(self.apartment.status, Apartment.Status.AVAILABLE)


class DashboardTests(TestCase):
    def test_dashboard_counts_apartment_statuses(self):
        complex_obj = ResidentialComplex.objects.create(name="Stats", address="Stats addr")
        building = Building.objects.create(complex=complex_obj, name="S1", floors_count=1)
        floor = Floor.objects.create(building=building, number=1)
        Apartment.objects.create(building=building, floor=floor, number="1", rooms=1, area="35.00", price="1.00")
        Apartment.objects.create(
            building=building,
            floor=floor,
            number="2",
            rooms=1,
            area="35.00",
            price="1.00",
            status=Apartment.Status.RESERVED,
        )
        Apartment.objects.create(
            building=building,
            floor=floor,
            number="3",
            rooms=1,
            area="35.00",
            price="1.00",
            status=Apartment.Status.SOLD,
        )

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual({key: payload[key] for key in ["total", "sold", "available", "reserved"]}, {"total": 3, "sold": 1, "available": 1, "reserved": 1})
        self.assertIn("financial", payload)

    def test_dashboard_returns_financial_kpis(self):
        complex_obj = ResidentialComplex.objects.create(name="Finance", address="Finance addr")
        building = Building.objects.create(complex=complex_obj, name="F1", floors_count=1)
        floor = Floor.objects.create(building=building, number=1)
        apartment = Apartment.objects.create(building=building, floor=floor, number="1", rooms=1, area="50.00", price="100000.00")
        client = Client.objects.create(full_name="Buyer", phone="+996700000001")
        Deal.objects.create(
            client=client,
            apartment=apartment,
            status=Deal.Status.CLOSED,
            final_price="95000.00",
        )

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        financial = response.json()["financial"]
        self.assertEqual(financial["deals_total"], 1)
        self.assertEqual(financial["closed_deals"], 1)
        self.assertEqual(financial["conversion_rate"], 100.0)
        self.assertEqual(financial["closed_revenue"], 95000.0)
        self.assertEqual(financial["revenue_by_building"][0]["building"], "F1")


class ClientCardTests(APITestCase):
    def setUp(self):
        complex_obj = ResidentialComplex.objects.create(name="Client Complex", address="Client street")
        building = Building.objects.create(complex=complex_obj, name="Client Tower", floors_count=1)
        floor = Floor.objects.create(building=building, number=1)
        self.apartment = Apartment.objects.create(
            building=building,
            floor=floor,
            number="1-1",
            rooms=2,
            area="55.00",
            price="75000.00",
        )
        self.client_obj = Client.objects.create(full_name="Aman Buyer", phone="+996700111222", source="site")

    def test_client_detail_includes_deals_and_notes(self):
        Deal.objects.create(client=self.client_obj, apartment=self.apartment, final_price="74000.00")
        ClientNote.objects.create(client=self.client_obj, note_type=ClientNote.NoteType.CALL, text="Первичный звонок")

        response = self.client.get(f"/api/clients/{self.client_obj.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "site")
        self.assertEqual(response.data["deals"][0]["apartment_number"], "1-1")
        self.assertEqual(response.data["notes"][0]["note_type"], ClientNote.NoteType.CALL)

    def test_client_notes_endpoint_filters_by_client(self):
        other_client = Client.objects.create(full_name="Other", phone="+996700333444")
        ClientNote.objects.create(client=self.client_obj, text="Нужна ипотека")
        ClientNote.objects.create(client=other_client, text="Другой клиент")

        response = self.client.get(f"/api/client-notes/?client={self.client_obj.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["text"], "Нужна ипотека")


class ApartmentFilterTests(APITestCase):
    def setUp(self):
        complex_obj = ResidentialComplex.objects.create(name="Filter Complex", address="Filter street")
        self.building = Building.objects.create(complex=complex_obj, name="Filter Tower", floors_count=2)
        floor_1 = Floor.objects.create(building=self.building, number=1)
        floor_2 = Floor.objects.create(building=self.building, number=2)
        Apartment.objects.create(
            building=self.building,
            floor=floor_1,
            number="1-1",
            rooms=1,
            area="40.00",
            price="50000.00",
            payment_type=Apartment.PaymentType.CASH,
        )
        Apartment.objects.create(
            building=self.building,
            floor=floor_2,
            number="2-1",
            rooms=2,
            area="60.00",
            price="90000.00",
            status=Apartment.Status.RESERVED,
            payment_type=Apartment.PaymentType.MORTGAGE,
        )

    def test_apartment_api_filters_by_rooms_payment_and_price(self):
        response = self.client.get(
            f"/api/apartments/?building={self.building.id}&rooms=2&payment_type=mortgage&max_price=95000"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["number"], "2-1")


class AIChatTests(APITestCase):
    def setUp(self):
        complex_obj = ResidentialComplex.objects.create(name="AI Complex", address="AI street")
        building = Building.objects.create(complex=complex_obj, name="AI Tower", floors_count=1)
        floor = Floor.objects.create(building=building, number=1)
        Apartment.objects.create(
            building=building,
            floor=floor,
            number="1-1",
            rooms=2,
            area="55.00",
            price="75000.00",
            status=Apartment.Status.AVAILABLE,
        )
        Apartment.objects.create(
            building=building,
            floor=floor,
            number="1-2",
            rooms=1,
            area="38.00",
            price="52000.00",
            status=Apartment.Status.RESERVED,
        )

    def test_ai_chat_answers_dashboard_question_and_saves_history(self):
        response = self.client.post(
            "/api/ai/chat/",
            {"message": "Покажи дашборд"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "rules")
        self.assertEqual(response.data["data"], {"total": 2, "sold": 0, "available": 1, "reserved": 1})
        self.assertIn("Всего квартир: 2", response.data["answer"])
        self.assertEqual(AIChatMessage.objects.count(), 2)

    def test_ai_chat_searches_apartments_by_rooms_and_price(self):
        response = self.client.post(
            "/api/ai/chat/",
            {"message": "Покажи 2-комнатные до 80000"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]["apartments"]), 1)
        self.assertEqual(response.data["data"]["apartments"][0]["number"], "1-1")

    def test_ai_chat_answers_smalltalk_without_crm_stats(self):
        response = self.client.post(
            "/api/ai/chat/",
            {"message": "Как дела?"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "smalltalk")
        self.assertEqual(response.data["data"], {})
        self.assertIn("Работаю", response.data["answer"])

    def test_ai_chat_asks_to_clarify_unclear_message(self):
        response = self.client.post(
            "/api/ai/chat/",
            {"message": "Что?"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "smalltalk")
        self.assertIn("Я отвечаю на вопросы по CRM", response.data["answer"])

    @patch("crm.ai.chat._generate_gemini_content", return_value="Монолит прочнее и гибче по планировкам, панель обычно быстрее и дешевле.")
    def test_ai_chat_routes_construction_questions_to_consulting_gemini(self, mocked_gemini):
        response = self.client.post(
            "/api/ai/chat/",
            {"message": "Как объяснить клиенту разницу между монолитом и панельным домом?"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "gemini_consulting")
        self.assertEqual(response.data["data"], {})
        self.assertIn("Монолит", response.data["answer"])
        mocked_gemini.assert_called_once()

    def test_ai_chat_history_returns_saved_messages(self):
        self.client.post("/api/ai/chat/", {"message": "сколько свободных квартир?"}, format="json")

        response = self.client.get("/api/ai/chat/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["role"], AIChatMessage.Role.USER)
        self.assertEqual(response.data[1]["role"], AIChatMessage.Role.ASSISTANT)


class UIPageTests(TestCase):
    def setUp(self):
        self.complex_obj = ResidentialComplex.objects.create(name="UI Complex", address="UI street")
        self.building = Building.objects.create(complex=self.complex_obj, name="UI Tower", floors_count=1)
        self.floor = Floor.objects.create(building=self.building, number=1)
        Apartment.objects.create(
            building=self.building,
            floor=self.floor,
            number="1-1",
            rooms=2,
            area="56.00",
            price="80000.00",
        )

    def test_dashboard_page_renders(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BuildCRM")
        self.assertContains(response, "UI Tower")
        self.assertContains(response, "Всего квартир")

    def test_building_detail_page_renders_apartment_grid(self):
        response = self.client.get(f"/buildings/{self.building.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Визуализация дома")
        self.assertContains(response, "1-1")
        self.assertContains(response, "status-available")
