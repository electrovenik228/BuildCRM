from django.db import IntegrityError, transaction
from rest_framework import serializers

from .ai.chat import answer_chat
from .models import AIChatMessage, Apartment, Building, Client, ClientNote, Deal, Floor, ResidentialComplex


ACTIVE_DEAL_STATUSES = [Deal.Status.LEAD, Deal.Status.IN_PROGRESS]


class ResidentialComplexSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResidentialComplex
        fields = ["id", "name", "address"]


class FloorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Floor
        fields = ["id", "building", "number"]


class ApartmentSerializer(serializers.ModelSerializer):
    color = serializers.CharField(read_only=True)

    class Meta:
        model = Apartment
        fields = [
            "id",
            "building",
            "floor",
            "number",
            "rooms",
            "area",
            "price",
            "status",
            "payment_type",
            "color",
            "created_at",
        ]
        read_only_fields = ["created_at", "color"]

    def validate(self, attrs):
        building = attrs.get("building", getattr(self.instance, "building", None))
        floor = attrs.get("floor", getattr(self.instance, "floor", None))
        if building and floor and floor.building_id != building.id:
            raise serializers.ValidationError({"floor": "Floor must belong to the apartment building."})
        return attrs

    def update(self, instance, validated_data):
        if instance.status == Apartment.Status.SOLD:
            raise serializers.ValidationError("Sold apartments cannot be edited.")
        return super().update(instance, validated_data)


class BuildingSerializer(serializers.ModelSerializer):
    apartments_per_floor = serializers.IntegerField(write_only=True, min_value=1, default=0)
    default_rooms = serializers.IntegerField(write_only=True, min_value=1, default=1)
    default_area = serializers.DecimalField(write_only=True, max_digits=8, decimal_places=2, default="40.00")
    default_price = serializers.DecimalField(write_only=True, max_digits=14, decimal_places=2, default="0.00")
    default_payment_type = serializers.ChoiceField(
        write_only=True,
        choices=Apartment.PaymentType.choices,
        default=Apartment.PaymentType.CASH,
    )
    floors = FloorSerializer(many=True, read_only=True)
    apartments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Building
        fields = [
            "id",
            "complex",
            "name",
            "floors_count",
            "apartments_per_floor",
            "default_rooms",
            "default_area",
            "default_price",
            "default_payment_type",
            "floors",
            "apartments_count",
        ]

    def validate_floors_count(self, value):
        if value < 1:
            raise serializers.ValidationError("Building must have at least one floor.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        apartments_per_floor = validated_data.pop("apartments_per_floor", 0)
        default_rooms = validated_data.pop("default_rooms", 1)
        default_area = validated_data.pop("default_area", "40.00")
        default_price = validated_data.pop("default_price", "0.00")
        default_payment_type = validated_data.pop("default_payment_type", Apartment.PaymentType.CASH)

        building = Building.objects.create(**validated_data)
        floors = [Floor(building=building, number=number) for number in range(1, building.floors_count + 1)]
        Floor.objects.bulk_create(floors)

        if apartments_per_floor:
            floors = list(Floor.objects.filter(building=building).order_by("number"))
            apartments = []
            for floor in floors:
                for index in range(1, apartments_per_floor + 1):
                    apartments.append(
                        Apartment(
                            building=building,
                            floor=floor,
                            number=f"{floor.number}-{index}",
                            rooms=default_rooms,
                            area=default_area,
                            price=default_price,
                            payment_type=default_payment_type,
                        )
                    )
            Apartment.objects.bulk_create(apartments)

        building.apartments_count = apartments_per_floor * building.floors_count
        return building


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "full_name", "phone", "source"]


class ClientNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientNote
        fields = ["id", "client", "note_type", "text", "created_at"]
        read_only_fields = ["created_at"]


class DealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = ["id", "client", "apartment", "status", "final_price", "reserved_until", "created_at"]
        read_only_fields = ["created_at"]

    @transaction.atomic
    def create(self, validated_data):
        apartment = Apartment.objects.select_for_update().get(pk=validated_data["apartment"].pk)
        if apartment.status == Apartment.Status.SOLD:
            raise serializers.ValidationError({"apartment": "Sold apartment cannot be used in a new deal."})
        if Deal.objects.filter(
            apartment=apartment,
            status__in=ACTIVE_DEAL_STATUSES,
        ).exists():
            raise serializers.ValidationError({"apartment": "Apartment already has an active deal."})

        validated_data["apartment"] = apartment
        try:
            deal = Deal.objects.create(**validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError({"apartment": "Apartment already has an active deal."}) from exc

        _sync_apartment_status(deal)
        return deal

    @transaction.atomic
    def update(self, instance, validated_data):
        if "apartment" in validated_data and validated_data["apartment"] != instance.apartment:
            raise serializers.ValidationError({"apartment": "Deal apartment cannot be changed."})

        deal = super().update(instance, validated_data)
        _sync_apartment_status(deal)
        return deal


def _sync_apartment_status(deal):
    apartment = Apartment.objects.select_for_update().get(pk=deal.apartment_id)
    if deal.status == Deal.Status.CLOSED:
        apartment.status = Apartment.Status.SOLD
    elif deal.status in ACTIVE_DEAL_STATUSES:
        apartment.status = Apartment.Status.RESERVED
    elif not Deal.objects.filter(
        apartment=apartment,
        status__in=[*ACTIVE_DEAL_STATUSES, Deal.Status.CLOSED],
    ).exclude(pk=deal.pk).exists():
        apartment.status = Apartment.Status.AVAILABLE
    apartment.save(update_fields=["status"])


class ClientDealSummarySerializer(serializers.ModelSerializer):
    apartment_number = serializers.CharField(source="apartment.number", read_only=True)
    building_name = serializers.CharField(source="apartment.building.name", read_only=True)

    class Meta:
        model = Deal
        fields = [
            "id",
            "apartment",
            "apartment_number",
            "building_name",
            "status",
            "final_price",
            "reserved_until",
            "created_at",
        ]


class ClientDetailSerializer(ClientSerializer):
    deals = ClientDealSummarySerializer(many=True, read_only=True)
    notes = ClientNoteSerializer(many=True, read_only=True)

    class Meta(ClientSerializer.Meta):
        fields = [*ClientSerializer.Meta.fields, "deals", "notes"]


class AIChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, trim_whitespace=True)

    def create(self, validated_data):
        AIChatMessage.objects.create(
            role=AIChatMessage.Role.USER,
            content=validated_data["message"],
        )
        result = answer_chat(validated_data["message"])
        assistant_message = AIChatMessage.objects.create(
            role=AIChatMessage.Role.ASSISTANT,
            content=result["answer"],
            metadata={
                "source": result.get("source"),
                "data": result.get("data", {}),
            },
        )
        return {
            "id": assistant_message.id,
            "answer": result["answer"],
            "data": result.get("data", {}),
            "source": result.get("source"),
        }


class AIChatResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    answer = serializers.CharField()
    data = serializers.JSONField()
    source = serializers.CharField(allow_null=True, required=False)


class AIChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIChatMessage
        fields = ["id", "role", "content", "metadata", "created_at"]
