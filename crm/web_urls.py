from django.urls import path

from .views import building_detail_page, dashboard_page

urlpatterns = [
    path("", dashboard_page, name="ui-dashboard"),
    path("buildings/<int:pk>/", building_detail_page, name="ui-building-detail"),
]
