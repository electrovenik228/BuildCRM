from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AIChatMessage, Apartment, Building, Client, ClientNote, Deal, Floor, ResidentialComplex
from .serializers import (
    AIChatMessageSerializer,
    AIChatRequestSerializer,
    AIChatResponseSerializer,
    ApartmentSerializer,
    BuildingSerializer,
    ClientDetailSerializer,
    ClientNoteSerializer,
    ClientSerializer,
    DealSerializer,
    FloorSerializer,
    ResidentialComplexSerializer,
)


ACTIVE_DEAL_STATUSES = [Deal.Status.LEAD, Deal.Status.IN_PROGRESS]


class ResidentialComplexViewSet(viewsets.ModelViewSet):
    queryset = ResidentialComplex.objects.all()
    serializer_class = ResidentialComplexSerializer


class BuildingViewSet(viewsets.ModelViewSet):
    serializer_class = BuildingSerializer

    def get_queryset(self):
        return (
            Building.objects.select_related("complex")
            .prefetch_related("floors")
            .annotate(apartments_count=Count("apartments"))
        )


class FloorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FloorSerializer

    def get_queryset(self):
        queryset = Floor.objects.select_related("building")
        building_id = self.request.query_params.get("building")
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        return queryset


class ApartmentViewSet(viewsets.ModelViewSet):
    serializer_class = ApartmentSerializer

    def get_queryset(self):
        queryset = Apartment.objects.select_related("building", "floor", "building__complex")
        building_id = self.request.query_params.get("building")
        floor_id = self.request.query_params.get("floor")
        status = self.request.query_params.get("status")
        rooms = self.request.query_params.get("rooms")
        payment_type = self.request.query_params.get("payment_type")
        min_price = self.request.query_params.get("min_price")
        max_price = self.request.query_params.get("max_price")
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        if floor_id:
            queryset = queryset.filter(floor_id=floor_id)
        if status:
            queryset = queryset.filter(status=status)
        if rooms:
            queryset = queryset.filter(rooms=rooms)
        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        return queryset


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer

    def get_queryset(self):
        return Client.objects.prefetch_related("notes", "deals__apartment__building")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ClientDetailSerializer
        return ClientSerializer


class ClientNoteViewSet(viewsets.ModelViewSet):
    serializer_class = ClientNoteSerializer

    def get_queryset(self):
        queryset = ClientNote.objects.select_related("client")
        client_id = self.request.query_params.get("client")
        note_type = self.request.query_params.get("note_type")
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        if note_type:
            queryset = queryset.filter(note_type=note_type)
        return queryset


class DealViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = DealSerializer

    def get_queryset(self):
        queryset = Deal.objects.select_related("client", "apartment", "apartment__building")
        apartment_id = self.request.query_params.get("apartment")
        client_id = self.request.query_params.get("client")
        status = self.request.query_params.get("status")
        if apartment_id:
            queryset = queryset.filter(apartment_id=apartment_id)
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class DashboardView(APIView):
    def get(self, request):
        return Response(_dashboard_payload())


def _apartment_counts(queryset=None):
    queryset = queryset or Apartment.objects.all()
    counts = dict(queryset.values_list("status").annotate(count=Count("id")))
    return {
        "total": sum(counts.values()),
        "sold": counts.get(Apartment.Status.SOLD, 0),
        "available": counts.get(Apartment.Status.AVAILABLE, 0),
        "reserved": counts.get(Apartment.Status.RESERVED, 0),
    }


def _financial_kpis():
    deals = Deal.objects.all()
    total_deals = deals.count()
    closed_deals = deals.filter(status=Deal.Status.CLOSED).count()
    active_deals = deals.filter(status__in=ACTIVE_DEAL_STATUSES)
    apartment_value = Apartment.objects.aggregate(total_price=Sum("price"), total_area=Sum("area"))
    total_price = apartment_value["total_price"] or 0
    total_area = apartment_value["total_area"] or 0
    closed_revenue = deals.filter(status=Deal.Status.CLOSED).aggregate(total=Sum("final_price"))["total"] or 0
    active_pipeline = active_deals.aggregate(total=Sum("final_price"))["total"] or 0

    revenue_by_building = [
        {
            "building": row["apartment__building__name"],
            "revenue": row["revenue"] or 0,
        }
        for row in deals.filter(status=Deal.Status.CLOSED)
        .values("apartment__building__name")
        .annotate(revenue=Sum("final_price"))
        .order_by("apartment__building__name")
    ]

    return {
        "deals_total": total_deals,
        "closed_deals": closed_deals,
        "conversion_rate": round((closed_deals / total_deals) * 100, 2) if total_deals else 0,
        "closed_revenue": closed_revenue,
        "active_pipeline": active_pipeline,
        "average_deal": deals.filter(status=Deal.Status.CLOSED).aggregate(avg=Avg("final_price"))["avg"] or 0,
        "average_sqm_price": total_price / total_area if total_area else 0,
        "expired_reserved": active_deals.filter(reserved_until__lt=timezone.now()).count(),
        "revenue_by_building": revenue_by_building,
    }


def _dashboard_payload(queryset=None):
    payload = _apartment_counts(queryset)
    if queryset is None:
        payload["financial"] = _financial_kpis()
    return payload


def dashboard_page(request):
    buildings = (
        Building.objects.select_related("complex")
        .annotate(apartments_count=Count("apartments"))
        .order_by("complex__name", "name")
    )
    return render(
        request,
        "crm/dashboard.html",
        {
            "dashboard": _apartment_counts(),
            "financial": _financial_kpis(),
            "buildings": buildings,
            "first_building": buildings.first(),
        },
    )


def building_detail_page(request, pk):
    building = get_object_or_404(Building.objects.select_related("complex"), pk=pk)
    floors = building.floors.prefetch_related("apartments").order_by("-number")
    floor_rows = [
        {
            "number": floor.number,
            "apartments": floor.apartments.order_by("number"),
        }
        for floor in floors
    ]
    return render(
        request,
        "crm/building_detail.html",
        {
            "building": building,
            "floor_rows": floor_rows,
            "dashboard": _apartment_counts(Apartment.objects.filter(building=building)),
        },
    )


class AIChatView(APIView):
    def post(self, request):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(AIChatResponseSerializer(result).data)


class AIChatHistoryView(APIView):
    def get(self, request):
        messages = AIChatMessage.objects.order_by("-created_at", "-id")[:50]
        serializer = AIChatMessageSerializer(reversed(messages), many=True)
        return Response(serializer.data)
