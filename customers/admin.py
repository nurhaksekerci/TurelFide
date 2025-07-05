from django.contrib import admin
from .models import Customer

# Register your models here.

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'formatted_phone', 'city', 'color_display_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'color', 'city', 'district', 'created_at']
    search_fields = ['first_name', 'last_name', 'phone_number', 'city', 'district']
    list_editable = ['is_active']
    list_per_page = 50
    
    def formatted_phone(self, obj):
        return obj.formatted_phone
    formatted_phone.short_description = 'Telefon'
    
    def color_display_name(self, obj):
        return obj.color_display_name
    color_display_name.short_description = 'Sınıf'
