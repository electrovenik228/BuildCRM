from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from crm.models import Apartment, Building, Floor, ResidentialComplex


class Command(BaseCommand):
    help = "Create demo residential complex, building, floors and apartments for the UI."

    @transaction.atomic
    def handle(self, *args, **options):
        complex_obj, _ = ResidentialComplex.objects.get_or_create(
            name="Green Yard",
            defaults={"address": "Bishkek, demo district"},
        )
        building, created = Building.objects.get_or_create(
            complex=complex_obj,
            name="Tower A",
            defaults={"floors_count": 8},
        )
        if not created and building.apartments.exists():
            self.stdout.write(self.style.WARNING("Demo data already exists."))
            return

        building.floors_count = 8
        building.save(update_fields=["floors_count"])

        statuses = [Apartment.Status.AVAILABLE, Apartment.Status.RESERVED, Apartment.Status.SOLD]
        payments = [Apartment.PaymentType.CASH, Apartment.PaymentType.MORTGAGE, Apartment.PaymentType.INSTALLMENT]

        for floor_number in range(1, building.floors_count + 1):
            floor, _ = Floor.objects.get_or_create(building=building, number=floor_number)
            for index in range(1, 5):
                rooms = (index % 3) + 1
                Apartment.objects.get_or_create(
                    building=building,
                    floor=floor,
                    number=f"{floor_number}-{index}",
                    defaults={
                        "rooms": rooms,
                        "area": Decimal("36.00") + Decimal(floor_number * 2 + index * 5),
                        "price": Decimal("42000.00") + Decimal(floor_number * 2500 + index * 3500),
                        "status": statuses[(floor_number + index) % len(statuses)],
                        "payment_type": payments[(floor_number * index) % len(payments)],
                    },
                )

        self.stdout.write(self.style.SUCCESS("Demo data created: Green Yard / Tower A."))
