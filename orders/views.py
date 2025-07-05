from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
from django.utils.dateparse import parse_date
from django.contrib.auth.decorators import login_required
import json
from decimal import Decimal
from django.utils import timezone
from django.db import models

from .models import Order, OrderItem, OrderStatusHistory, PlantingRequest, PlantingRequestHistory
from .services import OrderService, OrderItemService, SeasonOrderService, OrderStatusHistoryService
from .utils import (
    validate_order_data, validate_order_item_data, get_order_status_color,
    get_order_status_icon, calculate_delivery_urgency, get_urgency_color,
    format_currency, export_orders_to_csv, export_order_items_to_csv,
    get_season_order_fields_mapping, get_order_item_fields_mapping,
    get_next_production_stage, can_advance_to_next_stage,
    calculate_planting_date_urgency, get_planting_date_bg_color
)
from seasons.models import Season, SeasonProduct
from customers.models import Customer
from products.models import Variety, Rootstock, Species


@login_required
def season_selection(request):
    """Sezon seçimi sayfası - Sipariş sistemine giriş"""
    seasons = Season.objects.all().order_by('-start_date')
    
    # Her sezon için temel istatistikleri al
    for season in seasons:
        season.order_stats = OrderService.get_season_order_statistics(season.id)
    
    context = {
        'seasons': seasons,
        'page_title': 'Sipariş Yönetimi - Sezon Seçimi'
    }
    return render(request, 'orders/season_selection.html', context)


@login_required
def planting_season_selection(request):
    """Ekim takip için sezon seçimi sayfası"""
    seasons = Season.objects.all().order_by('-start_date')
    
    # Her sezon için ekim istatistikleri al
    for season in seasons:
        planting_stats = PlantingRequest.objects.filter(season=season).aggregate(
            total_requests=models.Count('id'),
            pending_requests=models.Count('id', filter=models.Q(status='pending')),
            sent_requests=models.Count('id', filter=models.Q(status='sent')), 
            confirmed_requests=models.Count('id', filter=models.Q(status='confirmed')),
            planted_requests=models.Count('id', filter=models.Q(status='planted')),
            overdue_requests=models.Count('id', filter=models.Q(
                requested_planting_date__lt=timezone.now().date(),
                status__in=['pending', 'sent', 'confirmed']
            ))
        )
        season.planting_stats = planting_stats
    
    context = {
        'seasons': seasons,
        'page_title': 'Ekim Takip - Sezon Seçimi'
    }
    return render(request, 'orders/planting_season_selection.html', context)


@login_required
def order_list(request, season_id):
    """Belirtilen sezondaki siparişler"""
    season = get_object_or_404(Season, id=season_id)
    orders = OrderService.get_orders_by_season(season_id).prefetch_related(
        'items__variety__species',
        'items__rootstock',
        'items__season_product__variety__species',
        'items__season_product__rootstock'
    )
    
    # Filtreleme
    status_filter = request.GET.get('status')
    customer_filter = request.GET.get('customer')
    urgent_filter = request.GET.get('urgent')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    if customer_filter:
        orders = orders.filter(customer_id=customer_filter)
    if urgent_filter:
        orders = orders.filter(urgent=True)
    
    # Sayfalama
    paginator = Paginator(orders, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # İstatistikler
    stats = OrderService.get_season_order_statistics(season_id)
    
    # Filter options
    customers = Customer.objects.filter(is_active=True, orders__season=season).distinct()
    
    # Toplam kalem sayısını hesapla
    total_items = sum(order.items.count() for order in page_obj)
    
    # Siparişlerin aciliyet durumlarını ve ekim tarihi renklendirmelerini hesapla
    for order in page_obj:
        urgency, urgency_text = calculate_delivery_urgency(order)
        order.urgency = urgency
        order.urgency_text = urgency_text
        order.urgency_color = get_urgency_color(urgency)
        order.status_color = get_order_status_color(order.status)
        order.status_icon = get_order_status_icon(order.status)
        
        # Her sipariş kalemi için ekim tarihi renklendirme bilgilerini hesapla
        for item in order.items.all():
            # Anaç ekim tarihi renklendirme
            if item.rootstock_planting_date:
                rootstock_urgency, rootstock_text = calculate_planting_date_urgency(
                    item.rootstock_planting_date, order.status
                )
                item.rootstock_urgency = rootstock_urgency
                item.rootstock_urgency_text = rootstock_text
                item.rootstock_bg_color = get_planting_date_bg_color(rootstock_urgency)
            else:
                item.rootstock_urgency = 'normal'
                item.rootstock_urgency_text = ''
                item.rootstock_bg_color = ''
            
            # Kalem ekim tarihi renklendirme
            if item.scion_planting_date:
                scion_urgency, scion_text = calculate_planting_date_urgency(
                    item.scion_planting_date, order.status
                )
                item.scion_urgency = scion_urgency
                item.scion_urgency_text = scion_text
                item.scion_bg_color = get_planting_date_bg_color(scion_urgency)
            else:
                item.scion_urgency = 'normal'
                item.scion_urgency_text = ''
                item.scion_bg_color = ''
    
    context = {
        'season': season,
        'orders': page_obj,
        'stats': stats,
        'customers': customers,
        'status_filter': status_filter,
        'customer_filter': customer_filter,
        'urgent_filter': urgent_filter,
        'status_choices': Order.OrderStatus.choices,
        'total_items': total_items,
        'page_title': f'{season.name} - Sipariş Detayları'
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def order_create(request, season_id):
    """Yeni sipariş oluştur"""
    season = get_object_or_404(Season, id=season_id)
    
    if request.method == 'POST':
        # Sipariş verilerini al
        order_data = {
            'customer_id': request.POST.get('customer'),
            'season_id': season_id,
            'requested_delivery_date': request.POST.get('requested_delivery_date'),
            'notes': request.POST.get('notes', ''),
            'internal_notes': request.POST.get('internal_notes', ''),
            'special_packaging': request.POST.get('special_packaging') == 'on',
            'urgent': request.POST.get('urgent') == 'on'
        }
        
        # Validasyon
        errors = validate_order_data(order_data)
        
        if not errors:
            try:
                order = OrderService.create_order(
                    created_by_id=request.user.id,
                    **order_data
                )
                
                messages.success(request, f'Sipariş {order.order_number} başarıyla oluşturuldu.')
                return redirect('orders:order_detail', season_id=season_id, order_id=order.id)
                
            except Exception as e:
                messages.error(request, f'Sipariş oluşturulurken hata: {str(e)}')
        else:
            for field, error in errors.items():
                messages.error(request, f'{field}: {error}')
    
    # Form options
    customers = Customer.objects.filter(is_active=True).order_by('first_name')
    field_mapping = get_season_order_fields_mapping()
    
    context = {
        'season': season,
        'customers': customers,
        'field_mapping': field_mapping,
        'page_title': f'{season.name} - Yeni Sipariş'
    }
    return render(request, 'orders/order_create.html', context)


@login_required
def order_detail(request, season_id, order_id):
    """Sipariş detayı"""
    season = get_object_or_404(Season, id=season_id)
    order = get_object_or_404(Order, id=order_id, season=season)
    
    # Sipariş kalemleri
    order_items = OrderItemService.get_items_by_order(order_id)
    
    # Durum geçmişi
    status_history = OrderStatusHistoryService.get_order_history(order_id)
    
    # Aciliyet durumu
    urgency, urgency_text = calculate_delivery_urgency(order)
    
    # Sonraki aşama
    next_stage = get_next_production_stage(order.status)
    can_advance = can_advance_to_next_stage(order)
    
    context = {
        'season': season,
        'order': order,
        'order_items': order_items,
        'status_history': status_history,
        'urgency': urgency,
        'urgency_text': urgency_text,
        'urgency_color': get_urgency_color(urgency),
        'status_color': get_order_status_color(order.status),
        'status_icon': get_order_status_icon(order.status),
        'next_stage': next_stage,
        'can_advance': can_advance,
        'status_choices': Order.OrderStatus.choices,
        'page_title': f'{season.name} - {order.order_number}'
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def order_items_manage(request, season_id, order_id):
    """Sipariş kalemlerini yönet"""
    season = get_object_or_404(Season, id=season_id)
    order = get_object_or_404(Order, id=order_id, season=season)
    
    if request.method == 'POST':
        # Yeni kalem ekleme
        variety_id = request.POST.get('variety')
        rootstock_id = request.POST.get('rootstock') or None
        
        # Variety ve rootstock'tan season_product'u bul veya oluştur
        try:
            if rootstock_id:
                season_product, created = SeasonProduct.objects.get_or_create(
                    season=season,
                    variety_id=variety_id,
                    rootstock_id=rootstock_id,
                    defaults={
                        'is_active': True,
                        # Varsayılan fiyatlar - daha sonra güncellenebilir
                        'price_single_stem_1': 0,
                        'price_single_stem_2': 0,
                        'price_single_stem_3': 0,
                        'price_single_stem_4': 0,
                        'price_single_stem_5': 0,
                        'price_single_stem_6': 0,
                        'price_single_stem_7': 0,
                        'price_single_stem_8': 0,
                        'price_single_stem_9': 0,
                        'price_single_stem_10': 0,
                        'price_single_stem_11': 0,
                        'price_single_stem_12': 0,
                        'price_single_stem_13': 0,
                        'price_single_stem_14': 0,
                        'price_single_stem_15': 0,
                        'price_single_stem_16': 0,
                        'price_single_stem_17': 0,
                        'price_single_stem_18': 0,
                        'price_double_stem_1': 0,
                        'price_double_stem_2': 0,
                        'price_double_stem_3': 0,
                        'price_double_stem_4': 0,
                        'price_double_stem_5': 0,
                        'price_double_stem_6': 0,
                        'price_double_stem_7': 0,
                        'price_double_stem_8': 0,
                        'price_double_stem_9': 0,
                        'price_double_stem_10': 0,
                        'price_double_stem_11': 0,
                        'price_double_stem_12': 0,
                        'price_double_stem_13': 0,
                        'price_double_stem_14': 0,
                        'price_double_stem_15': 0,
                        'price_double_stem_16': 0,
                        'price_double_stem_17': 0,
                        'price_double_stem_18': 0,
                    }
                )
            else:
                season_product, created = SeasonProduct.objects.get_or_create(
                    season=season,
                    variety_id=variety_id,
                    rootstock__isnull=True,
                    defaults={
                        'is_active': True,
                        'rootstock': None,
                        # Varsayılan fiyatlar
                        'price_single_stem_1': 0,
                        'price_single_stem_2': 0,
                        'price_single_stem_3': 0,
                        'price_single_stem_4': 0,
                        'price_single_stem_5': 0,
                        'price_single_stem_6': 0,
                        'price_single_stem_7': 0,
                        'price_single_stem_8': 0,
                        'price_single_stem_9': 0,
                        'price_single_stem_10': 0,
                        'price_single_stem_11': 0,
                        'price_single_stem_12': 0,
                        'price_single_stem_13': 0,
                        'price_single_stem_14': 0,
                        'price_single_stem_15': 0,
                        'price_single_stem_16': 0,
                        'price_single_stem_17': 0,
                        'price_single_stem_18': 0,
                        'price_double_stem_1': 0,
                        'price_double_stem_2': 0,
                        'price_double_stem_3': 0,
                        'price_double_stem_4': 0,
                        'price_double_stem_5': 0,
                        'price_double_stem_6': 0,
                        'price_double_stem_7': 0,
                        'price_double_stem_8': 0,
                        'price_double_stem_9': 0,
                        'price_double_stem_10': 0,
                        'price_double_stem_11': 0,
                        'price_double_stem_12': 0,
                        'price_double_stem_13': 0,
                        'price_double_stem_14': 0,
                        'price_double_stem_15': 0,
                        'price_double_stem_16': 0,
                        'price_double_stem_17': 0,
                        'price_double_stem_18': 0,
                    }
                )
                
            if created:
                messages.info(request, f'Bu ürün-anaç kombinasyonu sezonda yoktu, otomatik oluşturuldu. Fiyatları daha sonra güncelleyebilirsiniz.')
                
        except Exception as e:
            messages.error(request, f'Season product oluşturulurken hata: {str(e)}')
            return redirect('orders:order_items_manage', season_id=season_id, order_id=order_id)
        
        item_data = {
            'season_product_id': season_product.id,
            'stem_type': request.POST.get('stem_type'),
            'viol_type': request.POST.get('viol_type'),
            'quantity': int(request.POST.get('quantity', 0)),
            'viol_count': int(request.POST.get('viol_count', 0)),
            'notes': request.POST.get('notes', ''),
            'unit_price': None  # Unit price'ı POST verilerinden al (eğer girilmişse)
        }
        
        # Unit price'ı POST verilerinden al (eğer girilmişse)
        unit_price_str = request.POST.get('unit_price', '').strip()
        if unit_price_str:
            try:
                item_data['unit_price'] = Decimal(unit_price_str)
            except (ValueError, TypeError):
                # Geçersiz fiyat girişi, None olarak bırak (otomatik hesaplanacak)
                pass
        
        # Validasyon
        errors = validate_order_item_data(item_data)
        
        if not errors:
            try:
                order_item = OrderItemService.create_order_item(
                    order_id=order_id,
                    **item_data
                )
                
                messages.success(request, 'Sipariş kalemi başarıyla eklendi.')
                return redirect('orders:order_items_manage', season_id=season_id, order_id=order_id)
                
            except Exception as e:
                messages.error(request, f'Kalem eklenirken hata: {str(e)}')
        else:
            for field, error in errors.items():
                messages.error(request, f'{field}: {error}')
    
    # Mevcut kalemler
    order_items = OrderItemService.get_items_by_order(order_id)
    
    # Form için gerekli veriler
    varieties = Variety.objects.filter(
        season_products__season=season
    ).distinct().select_related('species').order_by('species__name', 'name')
    
    # Tüm aktif anaçları göster (sadece sezondakileri değil)
    rootstocks = Rootstock.objects.filter(
        is_active=True
    ).order_by('name')
    
    species_list = Species.objects.filter(
        varieties__season_products__season=season
    ).distinct().order_by('name')
    
    context = {
        'season': season,
        'order': order,
        'order_items': order_items,
        'varieties': varieties,
        'rootstocks': rootstocks,
        'species_list': species_list,
        'stem_type_choices': OrderItem.StemType.choices,
        'viol_type_choices': OrderItem.ViolType.choices,
        'page_title': f'{order.order_number} - Kalemler'
    }
    return render(request, 'orders/order_items_manage.html', context)


@login_required
@require_http_methods(["POST"])
def order_status_update(request, season_id, order_id):
    """Sipariş durumunu güncelle"""
    season = get_object_or_404(Season, id=season_id)
    order = get_object_or_404(Order, id=order_id, season=season)
    
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')
    
    if new_status in [choice[0] for choice in Order.OrderStatus.choices]:
        try:
            OrderService.update_order_status(
                order_id=order_id,
                new_status=new_status,
                changed_by_id=request.user.id,
                notes=notes
            )
            
            messages.success(request, f'Sipariş durumu {order.get_status_display()} olarak güncellendi.')
            
        except Exception as e:
            messages.error(request, f'Durum güncellenirken hata: {str(e)}')
    else:
        messages.error(request, 'Geçersiz durum seçimi.')
    
    return redirect('orders:order_detail', season_id=season_id, order_id=order_id)


@login_required
@require_http_methods(["POST"])
def order_delete(request, season_id, order_id):
    """Sipariş sil"""
    season = get_object_or_404(Season, id=season_id)
    order = get_object_or_404(Order, id=order_id, season=season)
    
    # Sadece taslak siparişler silinebilir
    if order.status != Order.OrderStatus.DRAFT:
        messages.error(request, 'Sadece taslak siparişler silinebilir.')
        return redirect('orders:order_detail', season_id=season_id, order_id=order_id)
    
    try:
        order_number = order.order_number
        order.delete()
        messages.success(request, f'Sipariş {order_number} başarıyla silindi.')
        
    except Exception as e:
        messages.error(request, f'Sipariş silinirken hata: {str(e)}')
    
    return redirect('orders:order_list', season_id=season_id)


@login_required
def season_statistics(request, season_id):
    """Sezon sipariş istatistikleri"""
    season = get_object_or_404(Season, id=season_id)
    
    # Temel istatistikler
    stats = OrderService.get_season_order_statistics(season_id)
    
    # Üretim özeti
    production_summary = SeasonOrderService.get_season_production_summary(season_id)
    
    # Hesaplanmış değerler
    calculated_stats = {}
    
    # Ortalama sipariş tutarı
    if stats['total_orders'] > 0:
        calculated_stats['average_order_amount'] = stats['total_amount'] / stats['total_orders']
    else:
        calculated_stats['average_order_amount'] = 0
    
    # Fide başına ortalama fiyat
    if stats.get('total_quantity', 0) > 0:
        calculated_stats['average_price_per_plant'] = stats['total_amount'] / stats['total_quantity']
    else:
        calculated_stats['average_price_per_plant'] = 0
    
    # Viol başına ortalama fiyat
    if stats.get('total_viol_count', 0) > 0:
        calculated_stats['average_price_per_viol'] = stats['total_amount'] / stats['total_viol_count']
    else:
        calculated_stats['average_price_per_viol'] = 0
    
    # Normal siparişler (toplam - bekleyen - geciken)
    calculated_stats['normal_orders'] = (
        stats['total_orders'] - 
        stats.get('pending_orders', 0) - 
        stats.get('overdue_orders', 0)
    )
    
    # Viol başına ortalama fide sayısı
    if production_summary.get('total_viols', 0) > 0:
        calculated_stats['avg_plants_per_viol'] = (
            production_summary['total_plants'] / production_summary['total_viols']
        )
    else:
        calculated_stats['avg_plants_per_viol'] = 0
    
    context = {
        'season': season,
        'stats': stats,
        'production_summary': production_summary,
        'calculated_stats': calculated_stats,
        'page_title': f'{season.name} - İstatistikler'
    }
    return render(request, 'orders/season_statistics.html', context)


@login_required
def season_export(request, season_id):
    """Sezon siparişlerini export et"""
    season = get_object_or_404(Season, id=season_id)
    orders = OrderService.get_orders_by_season(season_id)
    
    # CSV export
    csv_content = export_orders_to_csv(list(orders))
    
    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{season.name}_siparisler.csv"'
    
    return response


@login_required
def planting_list(request, season_id):
    """Ekim talep kartları listesi"""
    season = get_object_or_404(Season, id=season_id)
    
    # Ekim taleplerini al
    planting_requests = PlantingRequest.objects.filter(season=season).select_related(
        'variety__species', 'rootstock', 'created_by', 'confirmed_by', 'planted_by'
    ).prefetch_related('order_items__order__customer')
    
    # Filtreleme
    status_filter = request.GET.get('status')
    planting_type_filter = request.GET.get('planting_type')
    area_filter = request.GET.get('area')
    date_filter = request.GET.get('date_filter')
    
    if status_filter:
        planting_requests = planting_requests.filter(status=status_filter)
    if planting_type_filter:
        planting_requests = planting_requests.filter(planting_type=planting_type_filter)
    if area_filter:
        planting_requests = planting_requests.filter(planting_area__icontains=area_filter)
    
    # Tarih filtresi
    if date_filter:
        from datetime import datetime, timedelta
        today = timezone.now().date()
        
        if date_filter == 'today':
            planting_requests = planting_requests.filter(requested_planting_date=today)
        elif date_filter == 'this_week':
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            planting_requests = planting_requests.filter(
                requested_planting_date__range=[week_start, week_end]
            )
        elif date_filter == 'overdue':
            planting_requests = planting_requests.filter(
                requested_planting_date__lt=today,
                status__in=['pending', 'sent', 'confirmed']
            )
    
    # Sayfalama
    paginator = Paginator(planting_requests, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # İstatistikler
    stats = {
        'total_requests': planting_requests.count(),
        'pending_requests': planting_requests.filter(status='pending').count(),
        'sent_requests': planting_requests.filter(status='sent').count(),
        'confirmed_requests': planting_requests.filter(status='confirmed').count(),
        'planted_requests': planting_requests.filter(status='planted').count(),
        'overdue_requests': planting_requests.filter(
            requested_planting_date__lt=timezone.now().date(),
            status__in=['pending', 'sent', 'confirmed']
        ).count(),
    }
    
    # Ekim alanları
    planting_areas = PlantingRequest.objects.filter(
        season=season, planting_area__isnull=False
    ).exclude(planting_area='').values_list('planting_area', flat=True).distinct()
    
    context = {
        'season': season,
        'planting_requests': page_obj,
        'stats': stats,
        'planting_areas': planting_areas,
        'status_filter': status_filter,
        'planting_type_filter': planting_type_filter,
        'area_filter': area_filter,
        'date_filter': date_filter,
        'status_choices': PlantingRequest.RequestStatus.choices,
        'planting_type_choices': PlantingRequest.PlantingType.choices,
        'page_title': f'{season.name} - Ekim Takip'
    }
    return render(request, 'orders/planting_list.html', context)


@login_required
@require_http_methods(["POST"])
def planting_status_update(request, season_id, request_id):
    """Ekim talep kartı durumunu güncelle"""
    season = get_object_or_404(Season, id=season_id)
    planting_request = get_object_or_404(PlantingRequest, id=request_id, season=season)
    
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')
    location = request.POST.get('location', '')
    area = request.POST.get('area', '')
    actual_date = request.POST.get('actual_date')
    
    if new_status in [choice[0] for choice in PlantingRequest.RequestStatus.choices]:
        try:
            with transaction.atomic():
                # Önceki durum
                old_status = planting_request.status
                
                # Durum güncelle
                planting_request.status = new_status
                
                # Duruma göre özel işlemler
                if new_status == PlantingRequest.RequestStatus.SENT:
                    planting_request.sent_to_planting_date = timezone.now()
                elif new_status == PlantingRequest.RequestStatus.CONFIRMED:
                    planting_request.confirmed_date = timezone.now()
                    planting_request.confirmed_by = request.user
                elif new_status == PlantingRequest.RequestStatus.PLANTED:
                    if actual_date:
                        from django.utils.dateparse import parse_date
                        parsed_date = parse_date(actual_date)
                        if parsed_date:
                            planting_request.actual_planting_date = parsed_date
                    else:
                        planting_request.actual_planting_date = timezone.now().date()
                    planting_request.planted_by = request.user
                
                # Lokasyon bilgileri
                if location:
                    planting_request.planting_location = location
                if area:
                    planting_request.planting_area = area
                
                planting_request.save()
                
                # İlgili OrderItem'ların durumlarını güncelle
                update_order_items_status(planting_request, new_status)
                
                # Geçmiş kaydı oluştur
                PlantingRequestHistory.objects.create(
                    planting_request=planting_request,
                    from_status=old_status,
                    to_status=new_status,
                    changed_by=request.user,
                    notes=notes,
                    location_info=f"{area} - {location}" if area or location else None
                )
                
                messages.success(request, f'Ekim talebi {planting_request.get_status_display()} durumuna güncellendi.')
            
        except Exception as e:
            messages.error(request, f'Durum güncellenirken hata: {str(e)}')
    else:
        messages.error(request, 'Geçersiz durum seçimi.')
    
    return redirect('orders:planting_list', season_id=season_id)


def update_order_items_status(planting_request, new_planting_status):
    """PlantingRequest durumuna göre OrderItem durumlarını güncelle"""
    
    # PlantingRequest durumu → OrderItem durumu mapping
    status_mapping = {
        PlantingRequest.RequestStatus.PENDING: OrderItem.OrderItemStatus.WAITING,
        PlantingRequest.RequestStatus.SENT: OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_SENT,
        PlantingRequest.RequestStatus.CONFIRMED: OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_CONFIRMED,
        PlantingRequest.RequestStatus.PLANTED: OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_PLANTED,
        PlantingRequest.RequestStatus.COMPLETED: OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_PLANTED,
        PlantingRequest.RequestStatus.CANCELLED: OrderItem.OrderItemStatus.WAITING,
    }
    
    # PlantingRequest türüne göre mapping'i ayarla
    if planting_request.planting_type == PlantingRequest.PlantingType.SCION:
        status_mapping = {
            PlantingRequest.RequestStatus.PENDING: OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_PLANTED,
            PlantingRequest.RequestStatus.SENT: OrderItem.OrderItemStatus.SCION_PLANTING_SENT,
            PlantingRequest.RequestStatus.CONFIRMED: OrderItem.OrderItemStatus.SCION_PLANTING_CONFIRMED,
            PlantingRequest.RequestStatus.PLANTED: OrderItem.OrderItemStatus.SCION_PLANTING_PLANTED,
            PlantingRequest.RequestStatus.COMPLETED: OrderItem.OrderItemStatus.SCION_PLANTING_PLANTED,
            PlantingRequest.RequestStatus.CANCELLED: OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_PLANTED,
        }
    
    # Yeni OrderItem durumu
    new_order_item_status = status_mapping.get(new_planting_status)
    
    if new_order_item_status:
        # Bu PlantingRequest'e bağlı tüm OrderItem'ları güncelle
        updated_count = planting_request.order_items.update(status=new_order_item_status)
        
        # Log bilgisi (opsiyonel)
        if updated_count > 0:
            print(f"PlantingRequest {planting_request.request_number}: {updated_count} OrderItem durumu {new_order_item_status} olarak güncellendi")


@login_required
def planting_detail(request, season_id, request_id):
    """Ekim talep kartı detay sayfası"""
    season = get_object_or_404(Season, id=season_id)
    planting_request = get_object_or_404(
        PlantingRequest.objects.select_related(
            'variety__species', 'rootstock', 'season', 'created_by', 'confirmed_by', 'planted_by'
        ).prefetch_related(
            'order_items__order__customer',
            'status_history__changed_by'
        ), 
        id=request_id, 
        season=season
    )
    
    # İlgili siparişler ve müşteriler
    orders = planting_request.get_orders()
    customers = planting_request.get_customers()
    
    # Durum geçmişi
    status_history = planting_request.status_history.all().order_by('-changed_at')
    
    context = {
        'season': season,
        'planting_request': planting_request,
        'orders': orders,
        'customers': customers,
        'status_history': status_history,
        'page_title': f'{planting_request.request_number} - Detay'
    }
    return render(request, 'orders/planting_detail.html', context)


# AJAX API Views
@login_required
def api_season_products(request, season_id):
    """Sezon ürünleri API"""
    season_products = SeasonOrderService.get_available_season_products(season_id)
    
    data = []
    for sp in season_products:
        data.append({
            'id': sp.id,
            'variety_name': sp.variety.get_full_name(),
            'rootstock_name': sp.rootstock.name if sp.rootstock else 'Anaçsız',
            'display_name': f"{sp.variety.get_full_name()} ({sp.rootstock.name if sp.rootstock else 'Anaçsız'})"
        })
    
    return JsonResponse({'season_products': data})


@login_required
def api_product_price(request, season_product_id):
    """Ürün fiyat bilgisi API"""
    try:
        season_product = get_object_or_404(SeasonProduct, id=season_product_id)
        stem_type = request.GET.get('stem_type', 'single')
        order_id = request.GET.get('order_id')
        
        if order_id:
            unit_price = OrderItemService.calculate_unit_price(
                season_product, stem_type, int(order_id)
            )
        else:
            # Varsayılan olarak 1. ayın fiyatını döndür
            if stem_type == 'single':
                unit_price = season_product.price_single_stem_1
            else:
                unit_price = season_product.price_double_stem_1
        
        return JsonResponse({
            'success': True,
            'unit_price': float(unit_price),
            'formatted_price': format_currency(unit_price)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def api_order_totals(request, order_id):
    """Sipariş toplamları API"""
    try:
        order = get_object_or_404(Order, id=order_id)
        
        return JsonResponse({
            'success': True,
            'total_amount': float(order.total_amount),
            'total_quantity': order.total_quantity,
            'total_viol_count': order.total_viol_count,
            'formatted_amount': format_currency(order.total_amount)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# Placeholder views for remaining URLs
@login_required
def order_edit(request, season_id, order_id):
    return redirect('orders:order_detail', season_id=season_id, order_id=order_id)

@login_required
def order_clone(request, season_id, order_id):
    return redirect('orders:order_detail', season_id=season_id, order_id=order_id)

@login_required
def order_item_add(request, season_id, order_id):
    return redirect('orders:order_items_manage', season_id=season_id, order_id=order_id)

@login_required
def order_item_edit(request, season_id, order_id, item_id):
    return redirect('orders:order_items_manage', season_id=season_id, order_id=order_id)

@login_required
@require_http_methods(["POST"])
def order_item_delete(request, season_id, order_id, item_id):
    """Sipariş kalemi sil"""
    season = get_object_or_404(Season, id=season_id)
    order = get_object_or_404(Order, id=order_id, season=season)
    order_item = get_object_or_404(OrderItem, id=item_id, order=order)
    
    try:
        # Kalem bilgisini kaydet
        if order_item.season_product and order_item.season_product.variety:
            variety_name = order_item.season_product.variety.get_full_name()
        elif order_item.variety:
            variety_name = order_item.variety.get_full_name()
        else:
            variety_name = "Bilinmeyen ürün"
            
        item_info = f"{variety_name} - {order_item.quantity} fide"
        
        # Kalemi sil
        order_item.delete()
        
        messages.success(request, f'Sipariş kalemi ({item_info}) başarıyla silindi.')
        
    except Exception as e:
        messages.error(request, f'Kalem silinirken hata: {str(e)}')
    
    return redirect('orders:order_items_manage', season_id=season_id, order_id=order_id)

@login_required
def customer_orders(request, season_id, customer_id):
    return redirect('orders:order_list', season_id=season_id)

@login_required
def reports_dashboard(request):
    return redirect('orders:season_selection')

@login_required
def season_report(request, season_id):
    return redirect('orders:season_statistics', season_id=season_id)

@login_required
def customer_report(request, customer_id):
    return redirect('orders:season_selection')

@login_required
def api_season_product_by_variety(request, season_id):
    """Variety ve rootstock'tan season_product bul"""
    try:
        variety_id = request.GET.get('variety_id')
        rootstock_id = request.GET.get('rootstock_id') or None
        
        if not variety_id:
            return JsonResponse({
                'success': False,
                'error': 'Variety ID required'
            })
        
        # Season product'u bul
        if rootstock_id:
            season_product = SeasonProduct.objects.get(
                season_id=season_id,
                variety_id=variety_id,
                rootstock_id=rootstock_id
            )
        else:
            season_product = SeasonProduct.objects.get(
                season_id=season_id,
                variety_id=variety_id,
                rootstock__isnull=True
            )
        
        return JsonResponse({
            'success': True,
            'season_product_id': season_product.id,
            'variety_name': season_product.variety.get_full_name(),
            'rootstock_name': season_product.rootstock.name if season_product.rootstock else 'Anaçsız'
        })
        
    except SeasonProduct.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Bu sezon için ürün-anaç kombinasyonu bulunamadı'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def api_varieties_by_species(request, species_id):
    """Species'e göre varietyleri döndür"""
    try:
        season_id = request.GET.get('season_id')
        
        if season_id:
            # Sadece o sezonda bulunan varietyleri getir
            varieties = Variety.objects.filter(
                species_id=species_id,
                season_products__season_id=season_id
            ).distinct().order_by('name')
        else:
            # Tüm varietyleri getir
            varieties = Variety.objects.filter(
                species_id=species_id
            ).order_by('name')
        
        data = []
        for variety in varieties:
            data.append({
                'id': variety.id,
                'name': variety.name,
                'species_id': variety.species_id,
                'full_name': variety.get_full_name()
            })
        
        return JsonResponse({
            'success': True,
            'varieties': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["POST"])
def bulk_send_to_planting(request, season_id):
    """Seçilen siparişleri toplu olarak bekleyen duruma geçir"""
    season = get_object_or_404(Season, id=season_id)
    selected_order_ids = request.POST.getlist('selected_orders')
    
    if not selected_order_ids:
        messages.error(request, 'Hiç sipariş seçilmedi.')
        return redirect('orders:order_list', season_id=season_id)
    
    success_count = 0
    error_count = 0
    
    try:
        with transaction.atomic():
            for order_id in selected_order_ids:
                try:
                    order = Order.objects.get(id=order_id, season=season)
                    
                    # Sadece draft, confirmed durumlarındaki siparişler waiting aşamasına gönderilebilir
                    if order.status in [Order.OrderStatus.DRAFT, Order.OrderStatus.CONFIRMED]:
                        # Sipariş durumunu güncelle
                        OrderService.update_order_status(
                            order_id=order.id,
                            new_status=Order.OrderStatus.WAITING,
                            changed_by_id=request.user.id,
                            notes='Toplu işlemle bekleyen duruma alındı'
                        )
                        success_count += 1
                    else:
                        error_count += 1
                        
                except Order.DoesNotExist:
                    error_count += 1
                    continue
                except Exception as e:
                    error_count += 1
                    continue
        
        # Başarı mesajı
        if success_count > 0:
            messages.success(request, f'{success_count} sipariş başarıyla bekleyen duruma alındı.')
        
        # Hata mesajı
        if error_count > 0:
            messages.warning(request, f'{error_count} sipariş bekleyen duruma alınamadı (uygun durumda değil veya hata oluştu).')
            
    except Exception as e:
        messages.error(request, f'Toplu işlem sırasında hata oluştu: {str(e)}')
    
    return redirect('orders:order_list', season_id=season_id)

@login_required
@require_http_methods(["POST"])
def bulk_send_to_rootstock_planting(request, season_id):
    """Seçilen sipariş kalemlerini anaç/kalem ekime gönder ve PlantingRequest oluştur"""
    season = get_object_or_404(Season, id=season_id)
    selected_item_ids = request.POST.getlist('selected_items')
    planting_type = request.POST.get('planting_type', 'rootstock')  # Default: rootstock
    
    if not selected_item_ids:
        messages.error(request, 'Hiç sipariş kalemi seçilmedi.')
        return redirect('orders:order_list', season_id=season_id)
    
    success_count = 0
    error_count = 0
    created_requests = []
    
    # Ekim türüne göre farklı ayarlar
    is_rootstock_planting = planting_type == 'rootstock'
    planting_type_enum = PlantingRequest.PlantingType.ROOTSTOCK if is_rootstock_planting else PlantingRequest.PlantingType.SCION
    
    try:
        with transaction.atomic():
            # Seçilen kalemleri SADECE anaç türlerine göre grupla
            grouped_items = {}
            
            for item_id in selected_item_ids:
                try:
                    item = OrderItem.objects.select_related(
                        'variety', 'rootstock', 'order', 'season_product'
                    ).get(id=item_id, order__season=season)
                    
                    # Duruma göre geçerlilik kontrolü
                    is_valid_item = False
                    if is_rootstock_planting:
                        # Anaç ekim için: waiting durumunda ve anaçlı ürünler
                        is_valid_item = item.status == OrderItem.OrderItemStatus.WAITING and item.rootstock
                    else:
                        # Kalem ekim için: anaç ekilmiş durumundaki ürünler
                        is_valid_item = item.status == OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_PLANTED
                    
                    if is_valid_item:
                        # Grup anahtarı sadece anaç bazında oluştur
                        rootstock_name = item.rootstock.name if item.rootstock else 'NoRootstock'
                        group_key = rootstock_name
                        
                        if group_key not in grouped_items:
                            grouped_items[group_key] = {
                                'rootstock': item.rootstock,
                                'planting_date': item.rootstock_planting_date if is_rootstock_planting else item.scion_planting_date,
                                'items': [],
                                'varieties': set()  # Çeşitleri takip et
                            }
                        
                        grouped_items[group_key]['items'].append(item)
                        if item.variety:
                            grouped_items[group_key]['varieties'].add(item.variety)
                        
                except OrderItem.DoesNotExist:
                    error_count += 1
                    continue
            
            # Her grup için PlantingRequest oluştur
            for group_key, group_data in grouped_items.items():
                # Ekim adedini POST verilerinden al
                planting_quantity_key = f"planting_quantity_{group_key}"
                planting_quantity = request.POST.get(planting_quantity_key)
                
                if not planting_quantity:
                    error_count += len(group_data['items'])
                    continue
                
                try:
                    planting_quantity = int(planting_quantity)
                except (ValueError, TypeError):
                    error_count += len(group_data['items'])
                    continue
                
                if planting_quantity <= 0:
                    error_count += len(group_data['items'])
                    continue
                
                planting_date = group_data['planting_date']
                
                if planting_date:
                    # PlantingRequest oluştur veya mevcut olana ekle (sadece anaç bazında unique)
                    planting_request, created = PlantingRequest.objects.get_or_create(
                        rootstock=group_data['rootstock'],
                        planting_type=planting_type_enum,
                        requested_planting_date=planting_date,
                        season=season,
                        defaults={
                            'status': PlantingRequest.RequestStatus.SENT,
                            'sent_to_planting_date': timezone.now(),
                            'created_by': request.user,
                            'planting_quantity': planting_quantity,
                            'notes': f'Sistem tarafından otomatik oluşturuldu - {len(group_data["varieties"])} çeşit ({planting_type_enum.label})'
                        }
                    )
                    
                    # Eğer mevcut bir request varsa planting_quantity'yi güncelle
                    if not created:
                        planting_request.planting_quantity += planting_quantity
                        planting_request.save()
                    
                    # OrderItem'ları güncelle ve PlantingRequest'e ekle
                    for item in group_data['items']:
                        # Duruma göre OrderItem status güncelleme
                        if is_rootstock_planting:
                            item.status = OrderItem.OrderItemStatus.ROOTSTOCK_PLANTING_SENT
                        else:
                            item.status = OrderItem.OrderItemStatus.SCION_PLANTING_SENT
                        
                        item.save()
                        planting_request.order_items.add(item)
                        success_count += 1
                    
                    planting_request.calculate_totals()
                    
                    if created:
                        created_requests.append(planting_request)
                else:
                    # Ekim tarihi hesaplanamadığı için hata
                    error_count += len(group_data['items'])
        
        # Başarı mesajı
        if success_count > 0:
            planting_type_text = 'anaç' if is_rootstock_planting else 'kalem'
            messages.success(request, f'{success_count} sipariş kalemi {planting_type_text} ekime gönderildi.')
            if created_requests:
                request_numbers = ', '.join([req.request_number for req in created_requests])
                messages.info(request, f'Oluşturulan ekim talep kartları: {request_numbers}')
        
        # Hata mesajı
        if error_count > 0:
            error_msg = 'anaç ekime gönderilemedi (uygun durumda değil, anaçsız veya ekim tarihi hesaplanamadı)' if is_rootstock_planting else 'kalem ekime gönderilemedi (anaç ekilmemiş veya ekim tarihi hesaplanamadı)'
            messages.warning(request, f'{error_count} sipariş kalemi {error_msg}.')
            
    except Exception as e:
        messages.error(request, f'Toplu işlem sırasında hata oluştu: {str(e)}')
    
    return redirect('orders:order_list', season_id=season_id)
