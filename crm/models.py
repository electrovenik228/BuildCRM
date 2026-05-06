from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ResidentialComplex(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Building(models.Model):
    complex = models.ForeignKey(
        ResidentialComplex,
        related_name="buildings",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    floors_count = models.PositiveIntegerField()

    class Meta:
        ordering = ["complex_id", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["complex", "name"],
                name="unique_building_name_per_complex",
            ),
        ]

    def __str__(self):
        return f"{self.complex}: {self.name}"


class Floor(models.Model):
    building = models.ForeignKey(
        Building,
        related_name="floors",
        on_delete=models.CASCADE,
    )
    number = models.PositiveIntegerField()

    class Meta:
        ordering = ["building_id", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["building", "number"],
                name="unique_floor_number_per_building",
            ),
        ]

    def __str__(self):
        return f"{self.building} / floor {self.number}"


class Apartment(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"

    class PaymentType(models.TextChoices):
        CASH = "cash", "Cash"
        MORTGAGE = "mortgage", "Mortgage"
        INSTALLMENT = "installment", "Installment"

    building = models.ForeignKey(
        Building,
        related_name="apartments",
        on_delete=models.CASCADE,
    )
    floor = models.ForeignKey(
        Floor,
        related_name="apartments",
        on_delete=models.CASCADE,
    )
    number = models.CharField(max_length=32)
    rooms = models.PositiveSmallIntegerField()
    area = models.DecimalField(max_digits=8, decimal_places=2)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )
    payment_type = models.CharField(
        max_length=16,
        choices=PaymentType.choices,
        default=PaymentType.CASH,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["building_id", "floor__number", "number", "id"]
        indexes = [
            models.Index(fields=["building", "status"]),
            models.Index(fields=["floor", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["building", "number"],
                name="unique_apartment_number_per_building",
            ),
        ]

    @property
    def color(self):
        if self.payment_type == self.PaymentType.MORTGAGE:
            return "blue"
        return {
            self.Status.AVAILABLE: "green",
            self.Status.RESERVED: "yellow",
            self.Status.SOLD: "red",
        }[self.status]

    def clean(self):
        if self.floor_id and self.building_id and self.floor.building_id != self.building_id:
            raise ValidationError({"floor": "Floor must belong to the apartment building."})

    def __str__(self):
        return f"{self.building} / apartment {self.number}"


class Client(models.Model):
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, db_index=True)
    source = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["full_name", "id"]

    def __str__(self):
        return self.full_name


class Deal(models.Model):
    class Status(models.TextChoices):
        LEAD = "lead", "Lead"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"
        CANCELED = "canceled", "Canceled"
        LOST = "lost", "Lost"

    client = models.ForeignKey(
        Client,
        related_name="deals",
        on_delete=models.PROTECT,
    )
    apartment = models.ForeignKey(
        Apartment,
        related_name="deals",
        on_delete=models.PROTECT,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.LEAD,
        db_index=True,
    )
    final_price = models.DecimalField(max_digits=14, decimal_places=2)
    reserved_until = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["apartment", "status"]),
            models.Index(fields=["client", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["apartment"],
                condition=Q(status__in=["lead", "in_progress"]),
                name="unique_active_deal_per_apartment",
            ),
        ]

    def __str__(self):
        return f"Deal #{self.pk} / {self.client} / {self.apartment}"


class ClientNote(models.Model):
    class NoteType(models.TextChoices):
        COMMENT = "comment", "Comment"
        CALL = "call", "Call"

    client = models.ForeignKey(
        Client,
        related_name="notes",
        on_delete=models.CASCADE,
    )
    note_type = models.CharField(
        max_length=16,
        choices=NoteType.choices,
        default=NoteType.COMMENT,
        db_index=True,
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["client", "note_type"]),
        ]

    def __str__(self):
        return f"{self.client} / {self.note_type}: {self.text[:60]}"


class AIChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["role", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:60]}"
