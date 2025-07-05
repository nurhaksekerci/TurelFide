from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import Species, SeedBrand, Variety, Rootstock
from .services import SpeciesService, SeedBrandService, VarietyService, RootstockService, ProductService
from .utils import (
    product_permission_required, can_edit_products,
    validate_species_data, validate_seed_brand_data, validate_variety_data, validate_rootstock_data,
    clean_product_data, format_product_info, get_vigor_choices, ajax_response_helper,
    ProductFilters
)


# Dashboard Views
@product_permission_required(['admin', 'product_manager', 'readonly'])
def product_dashboard_view(request):
    """Ürün yönetimi ana dashboard"""
    stats = ProductService.get_general_stats()
    
    context = {
        'stats': stats,
        'can_edit': can_edit_products(request.user),
    }
    
    return render(request, 'products/dashboard.html', context)


# Species Views
@product_permission_required(['admin', 'product_manager', 'readonly'])
def species_list_view(request):
    """Tür listesi"""
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    page = request.GET.get('page', 1)
    
    is_active = None
    if status_filter == 'active':
        is_active = True
    elif status_filter == 'inactive':
        is_active = False
    
    result = SpeciesService.get_species_list(
        search_query=search_query,
        is_active=is_active,
        page=page
    )
    
    context = {
        'page_obj': result['page_obj'],
        'species_list': result['species'],
        'total_count': result['total_count'],
        'search_query': search_query,
        'status_filter': status_filter,
        'can_edit': can_edit_products(request.user),
    }
    
    return render(request, 'products/species_list.html', context)


@product_permission_required(['admin', 'product_manager'])
def species_create_view(request):
    """Yeni tür oluşturma"""
    if request.method == 'POST':
        data = {'name': request.POST.get('name', '')}
        
        is_valid, errors = validate_species_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
        else:
            cleaned_data = clean_product_data(data)
            species, error = SpeciesService.create_species(cleaned_data['name'])
            
            if species:
                messages.success(request, f'{species.name} türü başarıyla oluşturuldu.')
                return redirect('products:species_detail', species_id=species.id)
            else:
                messages.error(request, error)
    
    return render(request, 'products/species_create.html')


@product_permission_required(['admin', 'product_manager', 'readonly'])
def species_detail_view(request, species_id):
    """Tür detay"""
    species = get_object_or_404(Species, id=species_id)
    varieties = species.varieties.filter(is_active=True)[:10]
    rootstocks = species.rootstocks.filter(is_active=True)[:10]
    
    context = {
        'species': species,
        'species_info': format_product_info(species, 'species'),
        'varieties': varieties,
        'rootstocks': rootstocks,
        'can_edit': can_edit_products(request.user),
    }
    
    return render(request, 'products/species_detail.html', context)


@product_permission_required(['admin', 'product_manager'])
def species_edit_view(request, species_id):
    """Tür düzenleme"""
    species = get_object_or_404(Species, id=species_id)
    
    if request.method == 'POST':
        data = {'name': request.POST.get('name', '')}
        
        is_valid, errors = validate_species_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
        else:
            cleaned_data = clean_product_data(data)
            updated_species, error = SpeciesService.update_species(species, **cleaned_data)
            
            if updated_species:
                messages.success(request, f'{species.name} türü başarıyla güncellendi.')
                return redirect('products:species_detail', species_id=species.id)
            else:
                messages.error(request, error)
    
    context = {'species': species}
    return render(request, 'products/species_edit.html', context)


# SeedBrand Views
@product_permission_required(['admin', 'product_manager', 'readonly'])
def seed_brand_list_view(request):
    """Tohum markası listesi"""
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    page = request.GET.get('page', 1)
    
    is_active = None
    if status_filter == 'active':
        is_active = True
    elif status_filter == 'inactive':
        is_active = False
    
    result = SeedBrandService.get_seed_brand_list(
        search_query=search_query,
        is_active=is_active,
        page=page
    )
    
    context = {
        'page_obj': result['page_obj'],
        'seed_brands': result['seed_brands'],
        'total_count': result['total_count'],
        'search_query': search_query,
        'status_filter': status_filter,
        'can_edit': can_edit_products(request.user),
    }
    
    return render(request, 'products/seed_brand_list.html', context)


@product_permission_required(['admin', 'product_manager'])
def seed_brand_create_view(request):
    """Yeni tohum markası oluşturma"""
    if request.method == 'POST':
        data = {
            'name': request.POST.get('name', ''),
            'price_per_packet': request.POST.get('price_per_packet', ''),
            'seeds_per_packet': request.POST.get('seeds_per_packet', ''),
        }
        
        is_valid, errors = validate_seed_brand_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
        else:
            cleaned_data = clean_product_data(data)
            seed_brand, error = SeedBrandService.create_seed_brand(
                cleaned_data['name'],
                cleaned_data['price_per_packet'],
                cleaned_data['seeds_per_packet']
            )
            
            if seed_brand:
                messages.success(request, f'{seed_brand.name} markası başarıyla oluşturuldu.')
                return redirect('products:seed_brand_detail', brand_id=seed_brand.id)
            else:
                messages.error(request, error)
    
    return render(request, 'products/seed_brand_create.html')


@product_permission_required(['admin', 'product_manager', 'readonly'])
def seed_brand_detail_view(request, brand_id):
    """Tohum markası detay"""
    seed_brand = get_object_or_404(SeedBrand, id=brand_id)
    varieties = seed_brand.varieties.filter(is_active=True)[:10]
    
    context = {
        'seed_brand': seed_brand,
        'brand_info': format_product_info(seed_brand, 'seed_brand'),
        'varieties': varieties,
        'can_edit': can_edit_products(request.user),
    }
    
    return render(request, 'products/seed_brand_detail.html', context)


# Variety Views
@product_permission_required(['admin', 'product_manager', 'readonly'])
def variety_list_view(request):
    """Çeşit listesi"""
    search_query = request.GET.get('search', '')
    species_filter = request.GET.get('species', '')
    brand_filter = request.GET.get('brand', '')
    status_filter = request.GET.get('status', '')
    page = request.GET.get('page', 1)
    
    is_active = None
    if status_filter == 'active':
        is_active = True
    elif status_filter == 'inactive':
        is_active = False
    
    result = VarietyService.get_variety_list(
        search_query=search_query,
        species_filter=species_filter or None,
        brand_filter=brand_filter or None,
        is_active=is_active,
        page=page
    )
    
    # Filter seçenekleri
    species_list = ProductFilters.active_species()
    brand_list = ProductFilters.active_seed_brands()
    
    context = {
        'page_obj': result['page_obj'],
        'varieties': result['varieties'],
        'total_count': result['total_count'],
        'search_query': search_query,
        'species_filter': species_filter,
        'brand_filter': brand_filter,
        'status_filter': status_filter,
        'species_list': species_list,
        'brand_list': brand_list,
        'can_edit': can_edit_products(request.user),
    }
    
    return render(request, 'products/variety_list.html', context)


@product_permission_required(['admin', 'product_manager'])
def variety_create_view(request):
    """Yeni çeşit oluşturma"""
    if request.method == 'POST':
        data = {
            'name': request.POST.get('name', ''),
            'species': request.POST.get('species', ''),
            'seed_brand': request.POST.get('seed_brand', ''),
        }
        
        is_valid, errors = validate_variety_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
        else:
            cleaned_data = clean_product_data(data)
            
            try:
                species = Species.objects.get(id=cleaned_data['species'])
                seed_brand = SeedBrand.objects.get(id=cleaned_data['seed_brand'])
                
                variety, error = VarietyService.create_variety(
                    cleaned_data['name'], species, seed_brand
                )
                
                if variety:
                    messages.success(request, f'{variety.get_full_name()} çeşidi başarıyla oluşturuldu.')
                    return redirect('products:variety_list')
                else:
                    messages.error(request, error)
            except (Species.DoesNotExist, SeedBrand.DoesNotExist):
                messages.error(request, 'Geçersiz tür veya tohum markası seçimi.')
    
    species_list = ProductFilters.active_species()
    brand_list = ProductFilters.active_seed_brands()
    
    context = {
        'species_list': species_list,
        'brand_list': brand_list,
    }
    
    return render(request, 'products/variety_create.html', context)


# Rootstock Views
@product_permission_required(['admin', 'product_manager', 'readonly'])
def rootstock_list_view(request):
    """Anaç listesi"""
    search_query = request.GET.get('search', '')
    species_filter = request.GET.get('species', '')
    vigor_filter = request.GET.get('vigor', '')
    status_filter = request.GET.get('status', '')
    page = request.GET.get('page', 1)
    
    is_active = None
    if status_filter == 'active':
        is_active = True
    elif status_filter == 'inactive':
        is_active = False
    
    result = RootstockService.get_rootstock_list(
        search_query=search_query,
        species_filter=species_filter or None,
        vigor_filter=vigor_filter or None,
        is_active=is_active,
        page=page
    )
    
    # Filter seçenekleri
    species_list = ProductFilters.active_species()
    vigor_choices = get_vigor_choices()
    
    context = {
        'page_obj': result['page_obj'],
        'rootstocks': result['rootstocks'],
        'total_count': result['total_count'],
        'search_query': search_query,
        'species_filter': species_filter,
        'vigor_filter': vigor_filter,
        'status_filter': status_filter,
        'species_list': species_list,
        'vigor_choices': vigor_choices,
        'can_edit': can_edit_products(request.user),
    }
    
    return render(request, 'products/rootstock_list.html', context)


@product_permission_required(['admin', 'product_manager'])
def rootstock_create_view(request):
    """Yeni anaç oluşturma"""
    if request.method == 'POST':
        data = {
            'name': request.POST.get('name', ''),
            'species': request.POST.get('species', ''),
            'vigor_level': request.POST.get('vigor_level', ''),
            'description': request.POST.get('description', ''),
        }
        
        is_valid, errors = validate_rootstock_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
        else:
            cleaned_data = clean_product_data(data)
            
            try:
                species = Species.objects.get(id=cleaned_data['species'])
                
                rootstock, error = RootstockService.create_rootstock(
                    cleaned_data['name'], 
                    species, 
                    cleaned_data.get('vigor_level'),
                    cleaned_data.get('description')
                )
                
                if rootstock:
                    messages.success(request, f'{rootstock.get_full_name()} anacı başarıyla oluşturuldu.')
                    return redirect('products:rootstock_list')
                else:
                    messages.error(request, error)
            except Species.DoesNotExist:
                messages.error(request, 'Geçersiz tür seçimi.')
    
    species_list = ProductFilters.active_species()
    vigor_choices = get_vigor_choices()
    
    context = {
        'species_list': species_list,
        'vigor_choices': vigor_choices,
    }
    
    return render(request, 'products/rootstock_create.html', context)


# AJAX Views
@csrf_exempt
@product_permission_required(['admin', 'product_manager'])
@require_http_methods(["POST"])
def ajax_toggle_status(request, model_type, object_id):
    """AJAX ile durum değiştirme"""
    model_map = {
        'species': Species,
        'seed_brand': SeedBrand,
        'variety': Variety,
        'rootstock': Rootstock,
    }
    
    if model_type not in model_map:
        return ajax_response_helper(False, 'Geçersiz model tipi')
    
    try:
        model_class = model_map[model_type]
        obj = get_object_or_404(model_class, id=object_id)
        
        obj.is_active = not obj.is_active
        obj.save()
        
        status_text = 'aktifleştirildi' if obj.is_active else 'pasifleştirildi'
        message = f'{obj.name} {status_text}'
        
        return ajax_response_helper(
            success=True,
            message=message,
            data={'is_active': obj.is_active}
        )
    except Exception as e:
        return ajax_response_helper(
            success=False,
            message=f'Bir hata oluştu: {str(e)}'
        )


@csrf_exempt
@product_permission_required(['admin', 'product_manager', 'readonly'])
@require_http_methods(["GET"])
def ajax_search_products(request):
    """AJAX ile ürün arama"""
    query = request.GET.get('q', '').strip()
    product_type = request.GET.get('type', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    from .utils import search_products_advanced
    results = search_products_advanced(query, product_type or None)
    
    return JsonResponse({'results': results})


@csrf_exempt
@product_permission_required(['admin', 'product_manager'])
@require_http_methods(["POST"])
def ajax_bulk_toggle_status(request):
    """AJAX ile toplu durum değiştirme"""
    try:
        data = json.loads(request.body)
        model_type = data.get('model_type', '')
        object_ids = data.get('object_ids', [])
        action = data.get('action', '')  # 'activate' or 'deactivate'
        
        model_map = {
            'species': Species,
            'seed_brand': SeedBrand,
            'variety': Variety,
            'rootstock': Rootstock,
        }
        
        if model_type not in model_map:
            return ajax_response_helper(False, 'Geçersiz model tipi')
        
        if not object_ids:
            return ajax_response_helper(False, 'Hiç öğe seçilmedi')
        
        is_active = action == 'activate'
        updated_count, error = ProductService.bulk_toggle_status(
            model_map[model_type], object_ids, is_active
        )
        
        if error:
            return ajax_response_helper(False, error)
        
        action_text = 'aktifleştirildi' if is_active else 'pasifleştirildi'
        message = f'{updated_count} öğe {action_text}'
        
        return ajax_response_helper(
            success=True,
            message=message,
            data={'updated_count': updated_count}
        )
        
    except json.JSONDecodeError:
        return ajax_response_helper(False, 'Geçersiz veri formatı')
    except Exception as e:
        return ajax_response_helper(False, f'Bir hata oluştu: {str(e)}')


@csrf_exempt
@product_permission_required(['admin', 'product_manager', 'readonly'])
@require_http_methods(["GET"])
def ajax_get_varieties_by_species(request, species_id):
    """AJAX ile türe göre çeşitler"""
    try:
        varieties = ProductFilters.varieties_by_species(species_id)
        variety_list = []
        
        for variety in varieties:
            variety_list.append({
                'id': variety.id,
                'name': variety.name,
                'brand_name': variety.seed_brand.name,
                'full_name': variety.get_full_name_with_brand()
            })
        
        return JsonResponse({'varieties': variety_list})
    except Exception as e:
        return ajax_response_helper(False, f'Bir hata oluştu: {str(e)}')


@csrf_exempt
@product_permission_required(['admin', 'product_manager', 'readonly'])
@require_http_methods(["GET"])
def ajax_get_rootstocks_by_species(request, species_id):
    """AJAX ile türe göre anaçlar"""
    try:
        rootstocks = ProductFilters.rootstocks_by_species(species_id)
        rootstock_list = []
        
        for rootstock in rootstocks:
            rootstock_list.append({
                'id': rootstock.id,
                'name': rootstock.name,
                'vigor_level': rootstock.vigor_level,
                'vigor_display': rootstock.get_vigor_level_display() if rootstock.vigor_level else None,
                'full_name': rootstock.get_full_name()
            })
        
        return JsonResponse({'rootstocks': rootstock_list})
    except Exception as e:
        return ajax_response_helper(False, f'Bir hata oluştu: {str(e)}')
