from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.forms import TextInput, Textarea
from django.utils import timezone
from decimal import Decimal

from .models import Order, OrderItem, OrderStatusHistory, PlantingRequest, PlantingRequestHistory
from .services import OrderService, OrderItemService


class OrderItemInline(admin.TabularInline):
    """Sipariş kalemi inline admin"""
    model = OrderItem
    extra = 1
    fields = [
        'season_product', 'stem_type', 'viol_type', 
        'quantity', 'viol_count', 'unit_price', 'total_price', 'status', 'notes'
    ]
    readonly_fields = ['total_price']
    
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '10'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 40})},
    }
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'season_product__variety__species',
            'season_product__rootstock',
            'variety__species',
            'rootstock'
        )


class OrderStatusHistoryInline(admin.TabularInline):
    """Sipariş durum geçmişi inline admin"""
    model = OrderStatusHistory
    extra = 0
    fields = ['from_status', 'to_status', 'changed_at', 'changed_by', 'notes']
    readonly_fields = ['changed_at', 'changed_by']
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


class PlantingRequestHistoryInline(admin.TabularInline):
    """Ekim talep geçmişi inline admin"""
    model = PlantingRequestHistory
    extra = 0
    fields = ['from_status', 'to_status', 'changed_at', 'changed_by', 'notes', 'location_info']
    readonly_fields = ['changed_at', 'changed_by']
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Sipariş admin konfigürasyonu"""
    
    list_display = [
        'order_number', 'customer_info', 'season', 'status_badge', 
        'total_amount_formatted', 'order_date', 'requested_delivery_date',
        'production_progress', 'urgency_indicator', 'actions_column'
    ]
    
    list_filter = [
        'status', 'season', 'urgent', 'special_packaging',
        'order_date', 'requested_delivery_date', 'created_at'
    ]
    
    search_fields = [
        'order_number', 'customer__first_name', 'customer__last_name',
        'customer__first_name', 'customer__last_name', 'customer__phone_number', 'notes'
    ]
    
    readonly_fields = [
        'order_number', 'total_amount', 'total_quantity_display', 'total_viol_count_display',
        'production_status', 'created_at', 'updated_at', 'days_until_delivery',
        'planned_delivery_date_display'
    ]
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': (
                'order_number', 'customer', 'season', 'status'
            )
        }),
        ('Tarih Bilgileri', {
            'fields': (
                'order_date', 'requested_delivery_date', 
                'actual_shipment_date', 'actual_delivery_date',
                'planned_delivery_date_display', 'days_until_delivery'
            )
        }),
        ('Özel Talepler', {
            'fields': (
                'urgent', 'special_packaging'
            )
        }),
        ('Notlar', {
            'fields': (
                'notes', 'internal_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Özet Bilgiler', {
            'fields': (
                'total_amount', 'total_quantity_display', 'total_viol_count_display', 'production_status'
            ),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': (
                'created_by', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 60})},
    }
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'customer', 'season', 'created_by'
        ).prefetch_related('items')
    
    def customer_info(self, obj):
        """Müşteri bilgisi"""
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            f'{obj.customer.first_name} {obj.customer.last_name}',
            obj.customer.get_short_address() if hasattr(obj.customer, 'get_short_address') else f'{obj.customer.district}/{obj.customer.city}'
        )
    customer_info.short_description = 'Müşteri'
    customer_info.admin_order_field = 'customer__first_name'
    
    def status_badge(self, obj):
        """Durum badge'i"""
        color_map = {
            'draft': 'secondary',
            'confirmed': 'primary',
            'waiting': 'info',
            'awaiting_shipment': 'success',
            'shipped': 'success',
            'delivered': 'success',
            'cancelled': 'danger'
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Durum'
    status_badge.admin_order_field = 'status'
    
    def total_amount_formatted(self, obj):
        """Formatlanmış toplam tutar"""
        return format_html(
            '<strong>{} TL</strong>',
            '{:,.2f}'.format(obj.total_amount)
        )
    total_amount_formatted.short_description = 'Toplam Tutar'
    total_amount_formatted.admin_order_field = 'total_amount'
    
    def production_progress(self, obj):
        """Üretim ilerleme çubuğu"""
        progress = obj.production_status
        color = 'success' if progress == 100 else 'info' if progress > 50 else 'warning'
        return format_html(
            '<div class="progress" style="width: 100px;">'
            '<div class="progress-bar bg-{}" style="width: {}%">{}</div>'
            '</div>',
            color, progress, '{}%'.format(progress)
        )
    production_progress.short_description = 'İlerleme'
    
    def urgency_indicator(self, obj):
        """Aciliyet göstergesi"""
        if obj.urgent:
            return format_html('<span class="badge bg-danger">ACİL</span>')
        
        if obj.days_until_delivery is not None:
            if obj.days_until_delivery < 0:
                return format_html('<span class="badge bg-danger">GECİKMİŞ</span>')
            elif obj.days_until_delivery <= 7:
                return format_html('<span class="badge bg-warning">{} GÜN</span>', obj.days_until_delivery)
        
        return '-'
    urgency_indicator.short_description = 'Aciliyet'
    
    def actions_column(self, obj):
        """İşlem sütunu"""
        detail_url = reverse('admin:orders_order_change', args=[obj.pk])
        return format_html(
            '<a href="{}" class="btn btn-sm btn-outline-primary">Düzenle</a>',
            detail_url
        )
    actions_column.short_description = 'İşlemler'
    
    def planned_delivery_date_display(self, obj):
        """Planlanan teslimat tarihi"""
        date = obj.calculate_planned_delivery_date()
        if date:
            return date.strftime('%d.%m.%Y')
        return '-'
    planned_delivery_date_display.short_description = 'Planlanan Teslimat'
    
    def total_quantity_display(self, obj):
        """Toplam miktar"""
        return f'{obj.total_quantity} fide'
    total_quantity_display.short_description = 'Toplam Miktar'
    
    def total_viol_count_display(self, obj):
        """Toplam viol"""
        return f'{obj.total_viol_count} viol'
    total_viol_count_display.short_description = 'Toplam Viol'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni kayıt
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['mark_as_confirmed', 'mark_as_waiting', 'mark_as_cancelled']
    
    def mark_as_confirmed(self, request, queryset):
        """Seçilen siparişleri onayla"""
        updated = 0
        for order in queryset:
            if order.status == Order.OrderStatus.DRAFT:
                OrderService.update_order_status(
                    order.id, Order.OrderStatus.CONFIRMED, 
                    request.user.id, 'Admin panelinden toplu onaylandı'
                )
                updated += 1
        
        self.message_user(request, f'{updated} sipariş onaylandı.')
    mark_as_confirmed.short_description = 'Seçilen siparişleri onayla'
    
    def mark_as_waiting(self, request, queryset):
        """Seçilen siparişleri bekleyene çevir"""
        updated = 0
        for order in queryset:
            if order.status in [Order.OrderStatus.DRAFT, Order.OrderStatus.CONFIRMED]:
                OrderService.update_order_status(
                    order.id, Order.OrderStatus.WAITING,
                    request.user.id, 'Admin panelinden toplu bekleyene çevrildi'
                )
                updated += 1
        
        self.message_user(request, f'{updated} sipariş bekleyene çevrildi.')
    mark_as_waiting.short_description = 'Seçilen siparişleri bekleyene çevir'
    
    def mark_as_cancelled(self, request, queryset):
        """Seçilen siparişleri iptal et"""
        updated = 0
        for order in queryset:
            if order.status != Order.OrderStatus.DELIVERED:
                OrderService.update_order_status(
                    order.id, Order.OrderStatus.CANCELLED,
                    request.user.id, 'Admin panelinden toplu iptal edildi'
                )
                updated += 1
        
        self.message_user(request, f'{updated} sipariş iptal edildi.')
    mark_as_cancelled.short_description = 'Seçilen siparişleri iptal et'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Sipariş kalemi admin konfigürasyonu"""
    
    list_display = [
        'order_link', 'product_info', 'stem_type', 'viol_type',
        'quantity', 'viol_count', 'unit_price', 'total_price_formatted',
        'status_badge', 'planting_dates_info'
    ]
    
    list_filter = [
        'stem_type', 'viol_type', 'status', 'order__status', 'order__season',
        'variety__species', 'created_at'
    ]
    
    search_fields = [
        'order__order_number', 'variety__name', 'rootstock__name',
        'season_product__variety__name', 'order__customer__first_name'
    ]
    
    readonly_fields = [
        'total_price', 'planned_delivery_date_display',
        'rootstock_planting_date_display', 'scion_planting_date_display',
        'grafting_date_display', 'head_formation_date_display',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Sipariş Bilgileri', {
            'fields': ('order', 'season_product', 'status')
        }),
        ('Ürün Detayları', {
            'fields': (
                'variety', 'rootstock', 'stem_type', 'viol_type'
            )
        }),
        ('Miktar ve Fiyat', {
            'fields': (
                'quantity', 'viol_count', 'unit_price', 'total_price'
            )
        }),
        ('Üretim Tarihleri', {
            'fields': (
                'planned_delivery_date_display',
                'rootstock_planting_date_display',
                'scion_planting_date_display',
                'grafting_date_display',
                'head_formation_date_display'
            ),
            'classes': ('collapse',)
        }),
        ('Notlar', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order__customer', 'order__season', 'variety__species', 
            'rootstock', 'season_product__variety', 'season_product__rootstock'
        )
    
    def order_link(self, obj):
        """Sipariş linki"""
        url = reverse('admin:orders_order_change', args=[obj.order.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.order.order_number
        )
    order_link.short_description = 'Sipariş'
    order_link.admin_order_field = 'order__order_number'
    
    def product_info(self, obj):
        """Ürün bilgisi"""
        variety_name = obj.variety.get_full_name() if obj.variety else 'Bilinmeyen'
        rootstock_name = obj.rootstock.name if obj.rootstock else 'Anaçsız'
        
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            variety_name, rootstock_name
        )
    product_info.short_description = 'Ürün'
    
    def status_badge(self, obj):
        """Durum badge'i"""
        color_map = {
            'waiting': 'secondary',
            'rootstock_planting_sent': 'info',
            'rootstock_planting_confirmed': 'primary',
            'rootstock_planting_planted': 'success',
            'scion_planting_sent': 'info',
            'scion_planting_confirmed': 'primary',
            'scion_planting_planted': 'success',
            'grafting_sent': 'warning',
            'grafting_confirmed': 'primary',
            'grafting_planted': 'success',
            'head_formation_sent': 'warning',
            'head_formation_confirmed': 'primary',
            'head_formation_formed': 'success',
            'cutting_sent': 'warning',
            'cutting_confirmed': 'primary',
            'cutting_cut': 'success',
            'ready_for_shipment': 'success'
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Durum'
    status_badge.admin_order_field = 'status'
    
    def total_price_formatted(self, obj):
        """Formatlanmış toplam fiyat"""
        return format_html(
            '<strong>{} TL</strong>',
            '{:,.2f}'.format(obj.total_price)
        )
    total_price_formatted.short_description = 'Toplam Fiyat'
    total_price_formatted.admin_order_field = 'total_price'
    
    def planting_dates_info(self, obj):
        """Ekim tarihleri bilgisi"""
        rootstock_date = obj.rootstock_planting_date
        scion_date = obj.scion_planting_date
        
        if rootstock_date and scion_date:
            return format_html(
                '<small>Anaç: {}<br>Kalem: {}</small>',
                rootstock_date.strftime('%d.%m.%Y'),
                scion_date.strftime('%d.%m.%Y')
            )
        return '-'
    planting_dates_info.short_description = 'Ekim Tarihleri'
    
    def planned_delivery_date_display(self, obj):
        """Planlanan teslimat tarihi"""
        date = obj.planned_delivery_date
        return date.strftime('%d.%m.%Y') if date else '-'
    planned_delivery_date_display.short_description = 'Planlanan Teslimat'
    
    def rootstock_planting_date_display(self, obj):
        """Anaç ekim tarihi"""
        date = obj.rootstock_planting_date
        return date.strftime('%d.%m.%Y') if date else '-'
    rootstock_planting_date_display.short_description = 'Anaç Ekim Tarihi'
    
    def scion_planting_date_display(self, obj):
        """Kalem ekim tarihi"""
        date = obj.scion_planting_date
        return date.strftime('%d.%m.%Y') if date else '-'
    scion_planting_date_display.short_description = 'Kalem Ekim Tarihi'
    
    def grafting_date_display(self, obj):
        """Aşılama tarihi"""
        date = obj.grafting_date
        return date.strftime('%d.%m.%Y') if date else '-'
    grafting_date_display.short_description = 'Aşılama Tarihi'
    
    def head_formation_date_display(self, obj):
        """Kafa oluşturma tarihi"""
        date = obj.head_formation_date
        return date.strftime('%d.%m.%Y') if date else '-'
    head_formation_date_display.short_description = 'Kafa Oluşturma Tarihi'


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    """Sipariş durum geçmişi admin konfigürasyonu"""
    
    list_display = [
        'order_link', 'status_change', 'changed_at', 'changed_by', 'notes_preview'
    ]
    
    list_filter = [
        'from_status', 'to_status', 'changed_at'
    ]
    
    search_fields = [
        'order__order_number', 'notes', 'changed_by__username'
    ]
    
    readonly_fields = ['order', 'from_status', 'to_status', 'changed_at', 'changed_by']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order', 'changed_by'
        )
    
    def order_link(self, obj):
        """Sipariş linki"""
        url = reverse('admin:orders_order_change', args=[obj.order.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.order.order_number
        )
    order_link.short_description = 'Sipariş'
    order_link.admin_order_field = 'order__order_number'
    
    def status_change(self, obj):
        """Durum değişimi"""
        from_status = obj.order.OrderStatus(obj.from_status).label if obj.from_status else 'Yok'
        to_status = obj.order.OrderStatus(obj.to_status).label
        
        return format_html(
            '{} <span class="text-muted">→</span> {}',
            from_status, to_status
        )
    status_change.short_description = 'Durum Değişimi'
    
    def notes_preview(self, obj):
        """Not önizlemesi"""
        if obj.notes:
            return obj.notes[:50] + '...' if len(obj.notes) > 50 else obj.notes
        return '-'
    notes_preview.short_description = 'Notlar'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PlantingRequest)
class PlantingRequestAdmin(admin.ModelAdmin):
    """Ekim Talep Kartı admin konfigürasyonu"""
    
    list_display = [
        'request_number', 'product_display_admin', 'planting_type_badge', 
        'status_badge', 'requested_planting_date', 'total_quantity_display',
        'order_customer_count', 'days_remaining', 'location_display'
    ]
    
    list_filter = [
        'planting_type', 'status', 'season', 'variety__species',
        'requested_planting_date', 'actual_planting_date', 'planting_area'
    ]
    
    search_fields = [
        'request_number', 'variety__name', 'rootstock__name',
        'notes', 'planting_location', 'planting_area'
    ]
    
    readonly_fields = [
        'request_number', 'total_quantity', 'total_viol_count',
        'order_count', 'customer_count', 'days_until_planting',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': (
                'request_number', 'planting_type', 'variety', 'rootstock', 'season'
            )
        }),
        ('Tarih Bilgileri', {
            'fields': (
                'requested_planting_date', 'sent_to_planting_date',
                'confirmed_date', 'actual_planting_date', 'completion_date'
            )
        }),
        ('Durum ve Lokasyon', {
            'fields': (
                'status', 'planting_location', 'planting_area'
            )
        }),
        ('Miktar Bilgileri', {
            'fields': (
                'planting_quantity', 'total_quantity', 'total_viol_count', 'order_count', 'customer_count'
            ),
            'classes': ('collapse',)
        }),
        ('Notlar', {
            'fields': (
                'notes', 'internal_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': (
                'created_by', 'confirmed_by', 'planted_by', 
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['order_items']
    inlines = [PlantingRequestHistoryInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'variety__species', 'rootstock', 'season', 'created_by'
        ).prefetch_related('order_items__order__customer')
    
    def product_display_admin(self, obj):
        """Ürün görüntü adı"""
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.variety.get_full_name(),
            obj.rootstock.name if obj.rootstock else 'Anaçsız'
        )
    product_display_admin.short_description = 'Ürün'
    
    def planting_type_badge(self, obj):
        """Ekim türü badge'i"""
        color = 'success' if obj.planting_type == 'rootstock' else 'primary'
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_planting_type_display()
        )
    planting_type_badge.short_description = 'Ekim Türü'
    
    def status_badge(self, obj):
        """Durum badge'i"""
        color_map = {
            'pending': 'secondary',
            'sent': 'warning',
            'confirmed': 'info',
            'planted': 'success',
            'completed': 'success',
            'cancelled': 'danger'
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Durum'
    
    def total_quantity_display(self, obj):
        """Toplam miktar gösterimi"""
        return format_html(
            '<strong>{}</strong> fide<br><small>{} viol</small>',
            obj.total_quantity, obj.total_viol_count
        )
    total_quantity_display.short_description = 'Miktar'
    
    def order_customer_count(self, obj):
        """Sipariş ve müşteri sayısı"""
        return format_html(
            '{} sipariş<br><small>{} müşteri</small>',
            obj.order_count, obj.customer_count
        )
    order_customer_count.short_description = 'Sipariş/Müşteri'
    
    def days_remaining(self, obj):
        """Kalan gün sayısı"""
        days = obj.days_until_planting
        if days is None:
            return '-'
        
        if days < 0:
            return format_html('<span class="badge bg-danger">{}g GECİKMİŞ</span>', abs(days))
        elif days == 0:
            return format_html('<span class="badge bg-warning">BUGÜN</span>')
        elif days <= 3:
            return format_html('<span class="badge bg-warning">{} GÜN</span>', days)
        else:
            return format_html('<span class="badge bg-info">{} GÜN</span>', days)
    days_remaining.short_description = 'Kalan Süre'
    
    def location_display(self, obj):
        """Lokasyon gösterimi"""
        if obj.planting_area and obj.planting_location:
            return format_html(
                '<strong>{}</strong><br><small>{}</small>',
                obj.planting_area, obj.planting_location
            )
        elif obj.planting_area:
            return obj.planting_area
        elif obj.planting_location:
            return obj.planting_location
        return '-'
    location_display.short_description = 'Lokasyon'
    
    actions = ['send_to_planting', 'confirm_planting', 'mark_as_planted']
    
    def send_to_planting(self, request, queryset):
        """Seçilen talepleri ekime gönder"""
        updated = 0
        for req in queryset:
            if req.send_to_planting(request.user):
                updated += 1
        
        self.message_user(request, f'{updated} talep ekime gönderildi.')
    send_to_planting.short_description = 'Seçilen talepleri ekime gönder'
    
    def confirm_planting(self, request, queryset):
        """Seçilen talepleri onayla"""
        updated = 0
        for req in queryset:
            if req.confirm_planting(request.user):
                updated += 1
        
        self.message_user(request, f'{updated} talep onaylandı.')
    confirm_planting.short_description = 'Seçilen talepleri onayla'
    
    def mark_as_planted(self, request, queryset):
        """Seçilen talepleri ekildi olarak işaretle"""
        updated = 0
        for req in queryset:
            if req.mark_as_planted(user=request.user):
                updated += 1
        
        self.message_user(request, f'{updated} talep ekildi olarak işaretlendi.')
    mark_as_planted.short_description = 'Seçilen talepleri ekildi işaretle'


@admin.register(PlantingRequestHistory)
class PlantingRequestHistoryAdmin(admin.ModelAdmin):
    """Ekim talep geçmişi admin konfigürasyonu"""
    
    list_display = [
        'planting_request_link', 'status_change', 'changed_at', 'changed_by', 'location_info'
    ]
    
    list_filter = [
        'from_status', 'to_status', 'changed_at'
    ]
    
    search_fields = [
        'planting_request__request_number', 'notes', 'changed_by__username'
    ]
    
    readonly_fields = ['planting_request', 'from_status', 'to_status', 'changed_at', 'changed_by']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'planting_request', 'changed_by'
        )
    
    def planting_request_link(self, obj):
        """Ekim talebi linki"""
        url = reverse('admin:orders_plantingrequest_change', args=[obj.planting_request.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.planting_request.request_number
        )
    planting_request_link.short_description = 'Ekim Talebi'
    planting_request_link.admin_order_field = 'planting_request__request_number'
    
    def status_change(self, obj):
        """Durum değişimi"""
        from_status = obj.planting_request.RequestStatus(obj.from_status).label if obj.from_status else 'Yok'
        to_status = obj.planting_request.RequestStatus(obj.to_status).label
        
        return format_html(
            '{} <span class="text-muted">→</span> {}',
            from_status, to_status
        )
    status_change.short_description = 'Durum Değişimi'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# Admin site özelleştirmesi
admin.site.site_header = 'TurelFide Sipariş Yönetimi'
admin.site.site_title = 'Sipariş Admin'
admin.site.index_title = 'Sipariş Yönetim Paneli'
