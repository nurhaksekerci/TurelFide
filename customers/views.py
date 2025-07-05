from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
import json

from .models import Customer
from .services import CustomerService
from .utils import (
    customer_permission_required, can_edit_customers, can_delete_customers,
    format_customer_info, get_color_choices, validate_customer_data,
    clean_customer_data, ajax_response_helper
)


@customer_permission_required(['admin', 'readonly'])
def customer_list_view(request):
    """Müşteri listesi sayfası"""
    search_query = request.GET.get('search', '')
    color_filter = request.GET.get('color', '')
    city_filter = request.GET.get('city', '')
    status_filter = request.GET.get('status', '')
    page = request.GET.get('page', 1)
    
    # Durum filtresi
    is_active = None
    if status_filter == 'active':
        is_active = True
    elif status_filter == 'inactive':
        is_active = False
    
    # Müşteri listesini al
    result = CustomerService.get_customer_list(
        search_query=search_query,
        color_filter=color_filter,
        city_filter=city_filter,
        is_active=is_active,
        page=page,
        per_page=20
    )
    
    # Şehir listesi (filtreleme için)
    cities = CustomerService.get_cities_with_count()
    
    context = {
        'page_obj': result['page_obj'],
        'customers': result['customers'],
        'total_count': result['total_count'],
        'search_query': search_query,
        'color_filter': color_filter,
        'city_filter': city_filter,
        'status_filter': status_filter,
        'color_choices': get_color_choices(),
        'cities': cities,
        'can_edit': can_edit_customers(request.user),
        'can_delete': can_delete_customers(request.user),
    }
    
    return render(request, 'customers/customer_list.html', context)


@customer_permission_required(['admin', 'readonly'])
def customer_detail_view(request, customer_id):
    """Müşteri detay sayfası"""
    customer = get_object_or_404(Customer, id=customer_id)
    
    context = {
        'customer': customer,
        'customer_info': format_customer_info(customer),
        'can_edit': can_edit_customers(request.user),
        'can_delete': can_delete_customers(request.user),
    }
    
    return render(request, 'customers/customer_detail.html', context)


@customer_permission_required(['admin'])
def customer_create_view(request):
    """Yeni müşteri oluşturma sayfası"""
    if request.method == 'POST':
        # Form verilerini al
        data = {
            'first_name': request.POST.get('first_name', ''),
            'last_name': request.POST.get('last_name', ''),
            'phone_number': request.POST.get('phone_number', ''),
            'city': request.POST.get('city', ''),
            'district': request.POST.get('district', ''),
            'neighborhood': request.POST.get('neighborhood', ''),
            'address': request.POST.get('address', ''),
            'color': request.POST.get('color', '#ffeb3b'),
        }
        
        # Veri validasyonu
        is_valid, errors = validate_customer_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
        else:
            # Veriyi temizle
            cleaned_data = clean_customer_data(data)
            
            # Müşteriyi oluştur
            customer, error = CustomerService.create_customer(
                user=request.user,
                **cleaned_data
            )
            
            if customer:
                messages.success(request, f'{customer.get_full_name()} başarıyla oluşturuldu.')
                return redirect('customers:detail', customer_id=customer.id)
            else:
                messages.error(request, error)
    
    context = {
        'color_choices': get_color_choices(),
    }
    
    return render(request, 'customers/customer_create.html', context)


@customer_permission_required(['admin'])
def customer_edit_view(request, customer_id):
    """Müşteri düzenleme sayfası"""
    customer = get_object_or_404(Customer, id=customer_id)
    
    if request.method == 'POST':
        # Form verilerini al
        data = {
            'first_name': request.POST.get('first_name', ''),
            'last_name': request.POST.get('last_name', ''),
            'phone_number': request.POST.get('phone_number', ''),
            'city': request.POST.get('city', ''),
            'district': request.POST.get('district', ''),
            'neighborhood': request.POST.get('neighborhood', ''),
            'address': request.POST.get('address', ''),
            'color': request.POST.get('color', customer.color),
        }
        
        # Veri validasyonu
        is_valid, errors = validate_customer_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
        else:
            # Veriyi temizle
            cleaned_data = clean_customer_data(data)
            
            # Müşteriyi güncelle
            updated_customer, error = CustomerService.update_customer(
                customer, **cleaned_data
            )
            
            if updated_customer:
                messages.success(request, f'{customer.get_full_name()} başarıyla güncellendi.')
                return redirect('customers:detail', customer_id=customer.id)
            else:
                messages.error(request, error)
    
    context = {
        'customer': customer,
        'color_choices': get_color_choices(),
    }
    
    return render(request, 'customers/customer_edit.html', context)


@customer_permission_required(['admin'])
def customer_delete_view(request, customer_id):
    """Müşteri silme (pasifleştirme)"""
    customer = get_object_or_404(Customer, id=customer_id)
    
    if request.method == 'POST':
        success, message = CustomerService.delete_customer(customer)
        
        if success:
            messages.success(request, message)
            return redirect('customers:list')
        else:
            messages.error(request, message)
    
    context = {
        'customer': customer,
    }
    
    return render(request, 'customers/customer_delete.html', context)


@customer_permission_required(['admin', 'readonly'])
def customer_stats_view(request):
    """Müşteri istatistikleri sayfası"""
    stats = CustomerService.get_customer_stats()
    cities = CustomerService.get_cities_with_count()
    
    # Renk bilgilerini template için düzenle
    color_choices = get_color_choices()
    color_list = []
    
    # Her renk için istatistik hesapla
    total_customers = stats['total'] if stats['total'] > 0 else 1  # Division by zero'dan korunmak için
    
    for color_code, color_name in color_choices:
        # Bu renkteki müşteri sayısını al - color_breakdown'dan al
        count = 0
        for color_key, color_data in stats.get('color_breakdown', {}).items():
            # Color code'u karşılaştır
            if color_code == '#0d5016' and 'A Sınıfı' in color_key:
                count = color_data.get('count', 0)
                break
            elif color_code == '#2c9c3e' and 'B Sınıfı' in color_key:
                count = color_data.get('count', 0)
                break
            elif color_code == '#8bc34a' and 'C Sınıfı' in color_key:
                count = color_data.get('count', 0)
                break
            elif color_code == '#ffeb3b' and 'D Sınıfı' in color_key:
                count = color_data.get('count', 0)
                break
            elif color_code == '#ff9800' and 'E Sınıfı' in color_key:
                count = color_data.get('count', 0)
                break
            elif color_code == '#ff5722' and 'F Sınıfı' in color_key:
                count = color_data.get('count', 0)
                break
            elif color_code == '#d32f2f' and 'G Sınıfı' in color_key:
                count = color_data.get('count', 0)
                break
        
        percentage = round((count / total_customers) * 100, 1) if count > 0 else 0
        
        color_list.append({
            'name': color_name,
            'color_code': color_code,
            'count': count,
            'percentage': percentage
        })
    
    # Standard customers hesapla (C ve D sınıfı)
    standard_customers = 0
    for color_info in color_list:
        if 'C Sınıfı' in color_info['name'] or 'D Sınıfı' in color_info['name']:
            standard_customers += color_info['count']
    
    # Stats'e ek bilgileri ekle
    stats['color_list'] = color_list
    stats['standard_customers'] = standard_customers
    
    context = {
        'stats': stats,
        'cities': cities,
        'color_choices': get_color_choices(),
    }
    
    return render(request, 'customers/customer_stats.html', context)


# AJAX Views
@csrf_exempt
@customer_permission_required(['admin'])
@require_http_methods(["POST"])
def ajax_toggle_customer_status(request, customer_id):
    """AJAX ile müşteri durumunu aktif/pasif yapma"""
    customer = get_object_or_404(Customer, id=customer_id)
    
    try:
        if customer.is_active:
            customer.deactivate()
            message = f'{customer.get_full_name()} pasifleştirildi'
        else:
            customer.activate()
            message = f'{customer.get_full_name()} aktifleştirildi'
        
        return ajax_response_helper(
            success=True,
            message=message,
            data={'is_active': customer.is_active}
        )
    except Exception as e:
        return ajax_response_helper(
            success=False,
            message=f'Bir hata oluştu: {str(e)}'
        )


@csrf_exempt
@customer_permission_required(['admin', 'readonly'])
@require_http_methods(["GET"])
def ajax_customer_search(request):
    """AJAX ile müşteri arama"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'customers': []})
    
    customers = Customer.objects.search(query)[:10]
    
    customer_list = []
    for customer in customers:
        customer_list.append({
            'id': customer.id,
            'name': customer.get_full_name(),
            'phone': customer.formatted_phone,
            'city': customer.get_short_address(),
            'color': customer.color_display_name,
            'is_active': customer.is_active
        })
    
    return JsonResponse({'customers': customer_list})


@csrf_exempt
@customer_permission_required(['admin'])
@require_http_methods(["POST"])
def ajax_bulk_update_color(request):
    """AJAX ile toplu renk güncelleme"""
    try:
        data = json.loads(request.body)
        customer_ids = data.get('customer_ids', [])
        new_color = data.get('color', '')
        
        if not customer_ids:
            return ajax_response_helper(
                success=False,
                message='Hiç müşteri seçilmedi'
            )
        
        if new_color not in [choice[0] for choice in get_color_choices()]:
            return ajax_response_helper(
                success=False,
                message='Geçersiz renk seçimi'
            )
        
        updated_count, error = CustomerService.bulk_update_color(customer_ids, new_color)
        
        if error:
            return ajax_response_helper(success=False, message=error)
        
        return ajax_response_helper(
            success=True,
            message=f'{updated_count} müşterinin rengi güncellendi',
            data={'updated_count': updated_count}
        )
        
    except json.JSONDecodeError:
        return ajax_response_helper(
            success=False,
            message='Geçersiz veri formatı'
        )
    except Exception as e:
        return ajax_response_helper(
            success=False,
            message=f'Bir hata oluştu: {str(e)}'
        )


@csrf_exempt
@customer_permission_required(['admin'])
@require_http_methods(["POST"])
def ajax_bulk_toggle_status(request):
    """AJAX ile toplu durum değiştirme"""
    try:
        data = json.loads(request.body)
        customer_ids = data.get('customer_ids', [])
        action = data.get('action', '')  # 'activate' or 'deactivate'
        
        if not customer_ids:
            return ajax_response_helper(
                success=False,
                message='Hiç müşteri seçilmedi'
            )
        
        if action == 'activate':
            updated_count = CustomerService.bulk_activate(customer_ids)
            message = f'{updated_count} müşteri aktifleştirildi'
        elif action == 'deactivate':
            updated_count = CustomerService.bulk_deactivate(customer_ids)
            message = f'{updated_count} müşteri pasifleştirildi'
        else:
            return ajax_response_helper(
                success=False,
                message='Geçersiz işlem'
            )
        
        return ajax_response_helper(
            success=True,
            message=message,
            data={'updated_count': updated_count}
        )
        
    except json.JSONDecodeError:
        return ajax_response_helper(
            success=False,
            message='Geçersiz veri formatı'
        )
    except Exception as e:
        return ajax_response_helper(
            success=False,
            message=f'Bir hata oluştu: {str(e)}'
        )
