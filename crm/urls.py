from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApartmentViewSet,
    AIChatHistoryView,
    AIChatView,
    BuildingViewSet,
    ClientViewSet,
    DashboardView,
    DealViewSet,
    FloorViewSet,
    ResidentialComplexViewSet,
)

router = DefaultRouter()
router.register("complexes", ResidentialComplexViewSet, basename="complex")
router.register("buildings", BuildingViewSet, basename="building")
router.register("floors", FloorViewSet, basename="floor")
router.register("apartments", ApartmentViewSet, basename="apartment")
router.register("clients", ClientViewSet, basename="client")
router.register("deals", DealViewSet, basename="deal")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("ai/chat/", AIChatView.as_view(), name="ai-chat"),
    path("ai/chat/history/", AIChatHistoryView.as_view(), name="ai-chat-history"),
    *router.urls,
]
