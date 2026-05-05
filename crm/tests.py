from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APITestCase

from .models import AIChatMessage, Apartment, Building, Client, Deal, Floor, ResidentialComplex


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
        self.assertEqual(response.json(), {"total": 3, "sold": 1, "available": 1, "reserved": 1})


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
