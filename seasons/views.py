from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
from django.utils.dateparse import parse_date
import json
from decimal import Decimal

from .models import Season, SeasonProduct
from .services import SeasonService, SeasonProductService
from .utils import (
    format_season_name, get_price_fields_mapping, get_duration_fields_mapping,
    validate_price_data, validate_duration_data, get_season_statistics,
    export_season_products_data, check_season_completeness
)
from products.models import Variety, Rootstock


def season_list(request):
    """Sezon listesi"""
    seasons = SeasonService.get_all_seasons()
    
    # Her sezon için istatistikleri al ve sezon objesine ekle
    for season in seasons:
        stats = get_season_statistics(season)
        completeness = check_season_completeness(season)
        
        # Sezon objesine dinamik olarak istatistikleri ekle
        season.stats = stats
        season.completeness = completeness
    
    context = {
        'seasons': seasons,
        'page_title': 'Sezonlar'
    }
    return render(request, 'seasons/season_list.html', context)


def season_create(request):
    """Yeni sezon oluştur"""
    if request.method == 'POST':
        name = request.POST.get('name')
        start_date_str = request.POST.get('start_date')
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            start_date = parse_date(start_date_str)
            if not start_date:
                raise ValueError("Geçersiz tarih formatı")
            
            season = SeasonService.create_season(
                name=name,
                start_date=start_date,
                is_active=is_active
            )
            
            messages.success(request, f'{season.name} sezonu başarıyla oluşturuldu.')
            return redirect('seasons:season_detail', season_id=season.id)
            
        except Exception as e:
            messages.error(request, f'Sezon oluşturulurken hata: {str(e)}')
    
    context = {
        'page_title': 'Yeni Sezon Oluştur'
    }
    return render(request, 'seasons/season_create.html', context)


def season_detail(request, season_id):
    """Sezon detayı"""
    season = get_object_or_404(Season, id=season_id)
    season_products = SeasonProductService.get_season_products(season_id)
    
    # Sayfalama
    paginator = Paginator(season_products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # İstatistikler
    stats = get_season_statistics(season)
    completeness = check_season_completeness(season)
    
    context = {
        'season': season,
        'season_products': page_obj,
        'stats': stats,
        'completeness': completeness,
        'page_title': f'{season.name} - Detay'
    }
    return render(request, 'seasons/season_detail.html', context)


@require_http_methods(["POST"])
def season_activate(request, season_id):
    """Sezonu aktif yap"""
    try:
        season = SeasonService.activate_season(season_id)
        messages.success(request, f'{season.name} sezonu aktif edildi.')
    except Exception as e:
        messages.error(request, f'Sezon aktif edilirken hata: {str(e)}')
    
    return redirect('seasons:season_list')


def season_product_list(request, season_id):
    """Sezon ürünleri listesi"""
    season = get_object_or_404(Season, id=season_id)
    season_products = SeasonProductService.get_season_products(season_id)
    
    # Filtreleme
    variety_filter = request.GET.get('variety')
    rootstock_filter = request.GET.get('rootstock')
    
    if variety_filter:
        season_products = season_products.filter(variety_id=variety_filter)
    if rootstock_filter:
        season_products = season_products.filter(rootstock_id=rootstock_filter)
    
    # Sayfalama
    paginator = Paginator(season_products, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Filter options
    varieties = Variety.objects.filter(is_active=True).order_by('species__name', 'name')
    rootstocks = Rootstock.objects.filter(is_active=True).order_by('name')
    
    context = {
        'season': season,
        'season_products': page_obj,
        'varieties': varieties,
        'rootstocks': rootstocks,
        'variety_filter': variety_filter,
        'rootstock_filter': rootstock_filter,
        'page_title': f'{season.name} - Ürünler'
    }
    return render(request, 'seasons/season_product_list.html', context)


def season_product_create(request, season_id):
    """Sezon ürünü oluştur"""
    season = get_object_or_404(Season, id=season_id)
    
    if request.method == 'POST':
        variety_id = request.POST.get('variety')
        rootstock_id = request.POST.get('rootstock') or None
        
        # Validation
        if not variety_id:
            messages.error(request, 'Çeşit seçimi zorunludur.')
        else:
            # Duration data
            duration_data = {}
            for field in ['rootstock_planting_duration', 'scion_planting_duration', 
                         'single_stem_grafting_duration', 'double_stem_grafting_duration',
                         'head_formation_duration', 'waiting_on_room_duration']:
                duration_data[field] = request.POST.get(field)
            
            # Price data
            price_data = {}
            for i in range(1, 19):
                price_data[f'price_single_stem_{i}'] = request.POST.get(f'price_single_stem_{i}', '0')
                price_data[f'price_double_stem_{i}'] = request.POST.get(f'price_double_stem_{i}', '0')
            
            try:
                validated_durations = validate_duration_data(duration_data)
                validated_prices = validate_price_data(price_data)
                
                season_product = SeasonProductService.create_season_product(
                    season_id=season_id,
                    variety_id=int(variety_id),
                    rootstock_id=int(rootstock_id) if rootstock_id else None,
                    duration_data=validated_durations,
                    price_data=validated_prices
                )
                
                messages.success(request, 'Sezon ürünü başarıyla oluşturuldu.')
                return redirect('seasons:season_product_edit', season_id=season_id, product_id=season_product.id)
                
            except Exception as e:
                messages.error(request, f'Sezon ürünü oluşturulurken hata: {str(e)}')
    
    varieties = Variety.objects.filter(is_active=True).order_by('species__name', 'name')
    rootstocks = Rootstock.objects.filter(is_active=True).order_by('name')
    duration_fields = get_duration_fields_mapping()
    
    # POST verilerini template'e geç
    form_data = {}
    if request.method == 'POST':
        form_data = {
            'variety': request.POST.get('variety', ''),
            'rootstock': request.POST.get('rootstock', ''),
            'rootstock_planting_duration': request.POST.get('rootstock_planting_duration', '30'),
            'scion_planting_duration': request.POST.get('scion_planting_duration', '45'),
            'single_stem_grafting_duration': request.POST.get('single_stem_grafting_duration', '60'),
            'double_stem_grafting_duration': request.POST.get('double_stem_grafting_duration', '75'),
            'head_formation_duration': request.POST.get('head_formation_duration', '90'),
            'waiting_on_room_duration': request.POST.get('waiting_on_room_duration', '30'),
        }
        
        # Fiyat verilerini de ekle
        for i in range(1, 19):
            form_data[f'price_single_stem_{i}'] = request.POST.get(f'price_single_stem_{i}', '0')
            form_data[f'price_double_stem_{i}'] = request.POST.get(f'price_double_stem_{i}', '0')
    
    context = {
        'season': season,
        'varieties': varieties,
        'rootstocks': rootstocks,
        'duration_fields': duration_fields,
        'form_data': form_data,
        'page_title': f'{season.name} - Yeni Ürün'
    }
    return render(request, 'seasons/season_product_create.html', context)


def season_product_edit(request, season_id, product_id):
    """Sezon ürünü düzenle"""
    season = get_object_or_404(Season, id=season_id)
    season_product = get_object_or_404(SeasonProduct, id=product_id, season=season)
    
    if request.method == 'POST':
        # Duration update
        if 'update_durations' in request.POST:
            duration_data = {}
            for field in ['rootstock_planting_duration', 'scion_planting_duration',
                         'single_stem_grafting_duration', 'double_stem_grafting_duration',
                         'head_formation_duration', 'waiting_on_room_duration']:
                duration_data[field] = request.POST.get(field)
            
            validated_durations = validate_duration_data(duration_data)
            
            try:
                SeasonProductService.update_season_product_durations(
                    product_id, validated_durations
                )
                messages.success(request, 'Süreler başarıyla güncellendi.')
            except Exception as e:
                messages.error(request, f'Süreler güncellenirken hata: {str(e)}')
        
        # Price update
        elif 'update_prices' in request.POST:
            price_data = {}
            for i in range(1, 19):
                price_data[f'price_single_stem_{i}'] = request.POST.get(f'price_single_stem_{i}', '0')
                price_data[f'price_double_stem_{i}'] = request.POST.get(f'price_double_stem_{i}', '0')
            
            validated_prices = validate_price_data(price_data)
            
            try:
                SeasonProductService.update_season_product_prices(
                    product_id, validated_prices
                )
                messages.success(request, 'Fiyatlar başarıyla güncellendi.')
            except Exception as e:
                messages.error(request, f'Fiyatlar güncellenirken hata: {str(e)}')
        
        return redirect('seasons:season_product_edit', season_id=season_id, product_id=product_id)
    
    # Form data
    duration_fields = get_duration_fields_mapping()
    price_fields = get_price_fields_mapping()
    
    # Price data by months
    single_prices = []
    double_prices = []
    for i in range(1, 19):
        single_prices.append({
            'month': i,
            'field': f'price_single_stem_{i}',
            'value': getattr(season_product, f'price_single_stem_{i}')
        })
        double_prices.append({
            'month': i,
            'field': f'price_double_stem_{i}',
            'value': getattr(season_product, f'price_double_stem_{i}')
        })
    
    context = {
        'season': season,
        'season_product': season_product,
        'duration_fields': duration_fields,
        'price_fields': price_fields,
        'single_prices': single_prices,
        'double_prices': double_prices,
        'page_title': f'{season.name} - Ürün Düzenle'
    }
    return render(request, 'seasons/season_product_edit.html', context)


def season_product_bulk_create(request, season_id):
    """Toplu sezon ürünü oluştur"""
    season = get_object_or_404(Season, id=season_id)
    
    if request.method == 'POST':
        variety_ids = request.POST.getlist('varieties')
        rootstock_ids = request.POST.getlist('rootstocks')
        
        # Duration data
        duration_data = {}
        for field in ['rootstock_planting_duration', 'scion_planting_duration',
                     'single_stem_grafting_duration', 'double_stem_grafting_duration', 
                     'head_formation_duration', 'waiting_on_room_duration']:
            duration_data[field] = request.POST.get(field)
        
        # Price data
        price_data = {}
        for i in range(1, 19):
            price_data[f'price_single_stem_{i}'] = request.POST.get(f'price_single_stem_{i}', '0')
            price_data[f'price_double_stem_{i}'] = request.POST.get(f'price_double_stem_{i}', '0')
        
        try:
            validated_durations = validate_duration_data(duration_data)
            validated_prices = validate_price_data(price_data)
            
            variety_ids = [int(v) for v in variety_ids if v]
            rootstock_ids = [int(r) for r in rootstock_ids if r] if rootstock_ids else None
            
            season_products = SeasonProductService.bulk_create_season_products(
                season_id=season_id,
                varieties=variety_ids,
                rootstocks=rootstock_ids,
                default_durations=validated_durations,
                default_prices=validated_prices
            )
            
            messages.success(request, f'{len(season_products)} adet sezon ürünü başarıyla oluşturuldu.')
            return redirect('seasons:season_product_list', season_id=season_id)
            
        except Exception as e:
            messages.error(request, f'Toplu ürün oluşturulurken hata: {str(e)}')
    
    varieties = Variety.objects.filter(is_active=True).order_by('species__name', 'name')
    rootstocks = Rootstock.objects.filter(is_active=True).order_by('name')
    duration_fields = get_duration_fields_mapping()
    
    context = {
        'season': season,
        'varieties': varieties,
        'rootstocks': rootstocks,
        'duration_fields': duration_fields,
        'page_title': f'{season.name} - Toplu Ürün Oluştur'
    }
    return render(request, 'seasons/season_product_bulk_create.html', context)


@require_http_methods(["POST"])
@csrf_exempt
def season_product_quick_price_update(request, season_id, product_id):
    """Hızlı fiyat güncelleme (AJAX)"""
    try:
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value', '0')
        
        if not field.startswith('price_'):
            return JsonResponse({'success': False, 'error': 'Geçersiz alan'})
        
        validated_value = Decimal(str(value)) if value else Decimal('0.00')
        
        SeasonProductService.update_season_product_prices(
            product_id, {field: validated_value}
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def season_export(request, season_id):
    """Sezon verilerini export et"""
    season = get_object_or_404(Season, id=season_id)
    export_data = export_season_products_data(season)
    
    # CSV formatında export
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=export_data[0].keys() if export_data else [])
    writer.writeheader()
    writer.writerows(export_data)
    
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{season.name}_products.csv"'
    
    return response


# API Views (JSON responses)
def api_season_products(request, season_id):
    """Sezon ürünleri API"""
    season_products = SeasonProductService.get_season_products(season_id)
    
    data = []
    for sp in season_products:
        data.append({
            'id': sp.id,
            'variety': sp.variety.get_full_name(),
            'rootstock': sp.rootstock.name if sp.rootstock else None,
            'is_active': sp.is_active,
            'created_at': sp.created_at.isoformat(),
        })
    
    return JsonResponse({'season_products': data})


def api_season_statistics(request, season_id):
    """Sezon istatistikleri API"""
    season = get_object_or_404(Season, id=season_id)
    stats = get_season_statistics(season)
    completeness = check_season_completeness(season)
    
    return JsonResponse({
        'statistics': stats,
        'completeness': completeness
    })


@require_http_methods(["POST"])
def season_product_delete(request, season_id, product_id):
    """Sezon ürünü sil"""
    season = get_object_or_404(Season, id=season_id)
    season_product = get_object_or_404(SeasonProduct, id=product_id, season=season)
    
    try:
        product_name = str(season_product)
        season_product.delete()
        messages.success(request, f'{product_name} başarıyla silindi.')
    except Exception as e:
        messages.error(request, f'Ürün silinirken hata: {str(e)}')
    
    # Referer'a göre yönlendirme
    referer = request.META.get('HTTP_REFERER')
    if referer and 'products' in referer:
        return redirect('seasons:season_product_list', season_id=season_id)
    else:
        return redirect('seasons:season_detail', season_id=season_id)
