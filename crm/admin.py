from django.contrib import admin

from .models import AIChatMessage, Apartment, Building, Client, Deal, Floor, ResidentialComplex


@admin.register(ResidentialComplex)
class ResidentialComplexAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "address")
    search_fields = ("name", "address")


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("id", "complex", "name", "floors_count")
    list_filter = ("complex",)
    search_fields = ("name", "complex__name")


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("id", "building", "number")
    list_filter = ("building",)


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "building", "floor", "number", "rooms", "area", "price", "status", "payment_type")
    list_filter = ("status", "payment_type", "building")
    search_fields = ("number", "building__name", "building__complex__name")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "source")
    search_fields = ("full_name", "phone")


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "apartment", "status", "final_price", "created_at")
    list_filter = ("status",)
    search_fields = ("client__full_name", "client__phone", "apartment__number")


@admin.register(AIChatMessage)
class AIChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "created_at", "content")
    list_filter = ("role",)
    search_fields = ("content",)
