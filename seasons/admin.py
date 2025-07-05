from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Season, SeasonProduct


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'is_active', 'product_count', 'created_info']
    list_filter = ['is_active', 'start_date']
    search_fields = ['name']
    ordering = ['-start_date']
    readonly_fields = ['created_info']
    
    fieldsets = (
        ('Genel Bilgiler', {
            'fields': ('name', 'start_date', 'is_active')
        }),
        ('Ek Bilgiler', {
            'fields': ('created_info',),
            'classes': ('collapse',)
        }),
    )
    
    def product_count(self, obj):
        """Sezona ait ürün sayısı"""
        count = obj.season_products.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:seasons_seasonproduct_changelist') + f'?season__id__exact={obj.id}'
            return format_html('<a href="{}">{} ürün</a>', url, count)
        return '0 ürün'
    product_count.short_description = 'Ürün Sayısı'
    
    def created_info(self, obj):
        """Oluşturma bilgileri"""
        if obj.pk:
            return f"Oluşturulma: {obj.season_products.first().created_at if obj.season_products.exists() else 'Henüz ürün yok'}"
        return "Yeni kayıt"
    created_info.short_description = 'Bilgi'
    
    actions = ['activate_seasons', 'deactivate_seasons']
    
    def activate_seasons(self, request, queryset):
        """Seçili sezonları aktif yap"""
        # Önce hepsini pasif yap
        Season.objects.all().update(is_active=False)
        # Sonra seçilenleri aktif yap (sadece birini)
        if queryset.count() == 1:
            queryset.update(is_active=True)
            self.message_user(request, f'{queryset.first().name} sezonu aktif edildi.')
        else:
            self.message_user(request, 'Sadece bir sezon aktif edilebilir.', level='error')
    activate_seasons.short_description = 'Seçili sezonu aktif yap'
    
    def deactivate_seasons(self, request, queryset):
        """Seçili sezonları pasif yap"""
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} sezon pasif edildi.')
    deactivate_seasons.short_description = 'Seçili sezonları pasif yap'


class SeasonProductInline(admin.TabularInline):
    model = SeasonProduct
    extra = 0
    fields = ['variety', 'rootstock', 'is_active']
    readonly_fields = []
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('variety', 'rootstock')


@admin.register(SeasonProduct)
class SeasonProductAdmin(admin.ModelAdmin):
    list_display = [
        'season', 'variety_info', 'rootstock_info', 'is_active', 
        'total_production_days', 'has_prices', 'updated_at'
    ]
    list_filter = [
        'season', 'is_active', 'variety__species', 
        'rootstock', 'created_at', 'updated_at'
    ]
    search_fields = [
        'variety__name', 'variety__species__name', 
        'rootstock__name', 'season__name'
    ]
    ordering = ['season__start_date', 'variety__species__name', 'variety__name']
    readonly_fields = ['created_at', 'updated_at', 'total_production_days_info']
    
    fieldsets = (
        ('Genel Bilgiler', {
            'fields': ('season', 'variety', 'rootstock', 'is_active')
        }),
        ('Üretim Süreleri (Gün)', {
            'fields': (
                'rootstock_planting_duration', 'scion_planting_duration',
                'single_stem_grafting_duration', 'double_stem_grafting_duration',
                'head_formation_duration', 'waiting_on_room_duration',
                'total_production_days_info'
            )
        }),
        ('Tek Gövde Fiyatları (1-9. Ay)', {
            'fields': (
                ('price_single_stem_1', 'price_single_stem_2', 'price_single_stem_3'),
                ('price_single_stem_4', 'price_single_stem_5', 'price_single_stem_6'),
                ('price_single_stem_7', 'price_single_stem_8', 'price_single_stem_9'),
            ),
            'classes': ('collapse',)
        }),
        ('Tek Gövde Fiyatları (10-18. Ay)', {
            'fields': (
                ('price_single_stem_10', 'price_single_stem_11', 'price_single_stem_12'),
                ('price_single_stem_13', 'price_single_stem_14', 'price_single_stem_15'),
                ('price_single_stem_16', 'price_single_stem_17', 'price_single_stem_18'),
            ),
            'classes': ('collapse',)
        }),
        ('Çift Gövde Fiyatları (1-9. Ay)', {
            'fields': (
                ('price_double_stem_1', 'price_double_stem_2', 'price_double_stem_3'),
                ('price_double_stem_4', 'price_double_stem_5', 'price_double_stem_6'),
                ('price_double_stem_7', 'price_double_stem_8', 'price_double_stem_9'),
            ),
            'classes': ('collapse',)
        }),
        ('Çift Gövde Fiyatları (10-18. Ay)', {
            'fields': (
                ('price_double_stem_10', 'price_double_stem_11', 'price_double_stem_12'),
                ('price_double_stem_13', 'price_double_stem_14', 'price_double_stem_15'),
                ('price_double_stem_16', 'price_double_stem_17', 'price_double_stem_18'),
            ),
            'classes': ('collapse',)
        }),
        ('Ek Bilgiler', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def variety_info(self, obj):
        """Çeşit bilgisi"""
        return obj.variety.get_full_name()
    variety_info.short_description = 'Çeşit'
    variety_info.admin_order_field = 'variety__name'
    
    def rootstock_info(self, obj):
        """Anaç bilgisi"""
        if obj.rootstock:
            return obj.rootstock.name
        return format_html('<span style="color: #999;">Anaçsız</span>')
    rootstock_info.short_description = 'Anaç'
    rootstock_info.admin_order_field = 'rootstock__name'
    
    def total_production_days(self, obj):
        """Toplam üretim süresi"""
        single_days = obj.total_production_duration
        double_days = (
            obj.rootstock_planting_duration + obj.scion_planting_duration +
            obj.double_stem_grafting_duration + obj.head_formation_duration +
            obj.waiting_on_room_duration
        )
        return f"Tek: {single_days}g, Çift: {double_days}g"
    total_production_days.short_description = 'Üretim Süresi'
    
    def total_production_days_info(self, obj):
        """Toplam üretim süresi detayı"""
        if obj.pk:
            single_days = obj.total_production_duration
            double_days = (
                obj.rootstock_planting_duration + obj.scion_planting_duration +
                obj.double_stem_grafting_duration + obj.head_formation_duration +
                obj.waiting_on_room_duration
            )
            return format_html(
                'Tek Gövde: <strong>{}</strong> gün<br>'
                'Çift Gövde: <strong>{}</strong> gün',
                single_days, double_days
            )
        return "Henüz hesaplanmadı"
    total_production_days_info.short_description = 'Toplam Üretim Süresi'
    
    def has_prices(self, obj):
        """Fiyat durumu"""
        single_prices = [getattr(obj, f'price_single_stem_{i}') for i in range(1, 19)]
        double_prices = [getattr(obj, f'price_double_stem_{i}') for i in range(1, 19)]
        
        single_count = sum(1 for p in single_prices if p > 0)
        double_count = sum(1 for p in double_prices if p > 0)
        
        if single_count == 0 and double_count == 0:
            return format_html('<span style="color: red;">❌ Fiyat Yok</span>')
        elif single_count > 0 and double_count > 0:
            return format_html('<span style="color: green;">✅ Tam</span>')
        else:
            return format_html('<span style="color: orange;">⚠️ Kısmi</span>')
    has_prices.short_description = 'Fiyat Durumu'
    
    actions = ['activate_products', 'deactivate_products', 'copy_prices_from_previous_season']
    
    def activate_products(self, request, queryset):
        """Seçili ürünleri aktif yap"""
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} ürün aktif edildi.')
    activate_products.short_description = 'Seçili ürünleri aktif yap'
    
    def deactivate_products(self, request, queryset):
        """Seçili ürünleri pasif yap"""
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} ürün pasif edildi.')
    deactivate_products.short_description = 'Seçili ürünleri pasif yap'
    
    def copy_prices_from_previous_season(self, request, queryset):
        """Önceki sezondan fiyatları kopyala"""
        # Bu özellik daha gelişmiş bir implementasyon gerektirebilir
        self.message_user(request, 'Bu özellik henüz implementasyonda.')
    copy_prices_from_previous_season.short_description = 'Önceki sezondan fiyatları kopyala'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'season', 'variety', 'variety__species', 'rootstock'
        )
