from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AIChatMessage, Apartment, Building, Client, Deal, Floor, ResidentialComplex
from .serializers import (
    AIChatMessageSerializer,
    AIChatRequestSerializer,
    AIChatResponseSerializer,
    ApartmentSerializer,
    BuildingSerializer,
    ClientSerializer,
    DealSerializer,
    FloorSerializer,
    ResidentialComplexSerializer,
)


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
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        if floor_id:
            queryset = queryset.filter(floor_id=floor_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer


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
        counts = dict(Apartment.objects.values_list("status").annotate(count=Count("id")))
        return Response(
            {
                "total": sum(counts.values()),
                "sold": counts.get(Apartment.Status.SOLD, 0),
                "available": counts.get(Apartment.Status.AVAILABLE, 0),
                "reserved": counts.get(Apartment.Status.RESERVED, 0),
            }
        )


def _dashboard_counts(queryset=None):
    queryset = queryset or Apartment.objects.all()
    counts = dict(queryset.values_list("status").annotate(count=Count("id")))
    return {
        "total": sum(counts.values()),
        "sold": counts.get(Apartment.Status.SOLD, 0),
        "available": counts.get(Apartment.Status.AVAILABLE, 0),
        "reserved": counts.get(Apartment.Status.RESERVED, 0),
    }


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
            "dashboard": _dashboard_counts(),
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
            "dashboard": _dashboard_counts(Apartment.objects.filter(building=building)),
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
