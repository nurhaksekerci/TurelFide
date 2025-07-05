from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Q
import re


def customer_permission_required(allowed_roles=None):
    """Customer modülü için rol bazlı yetki kontrolü"""
    if allowed_roles is None:
        allowed_roles = ['admin', 'readonly']
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            if request.user.role not in allowed_roles:
                messages.error(request, 'Bu işlem için yetkiniz bulunmamaktadır.')
                return redirect('accounts:dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def can_manage_customers(user):
    """Kullanıcının müşteri yönetimi yetkisi var mı?"""
    return user.is_authenticated and user.role in ['admin', 'readonly']


def can_edit_customers(user):
    """Kullanıcının müşteri düzenleme yetkisi var mı?"""
    return user.is_authenticated and user.role == 'admin'


def can_delete_customers(user):
    """Kullanıcının müşteri silme yetkisi var mı?"""
    return user.is_authenticated and user.role == 'admin'


def validate_phone_number(phone):
    """Türkiye telefon numarası validasyonu"""
    if not phone:
        return False, "Telefon numarası gereklidir"
    
    # Sadece rakamları al
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    if len(clean_phone) != 10:
        return False, "Telefon numarası 10 haneli olmalıdır"
    
    if not clean_phone.startswith('5'):
        return False, "Telefon numarası 5 ile başlamalıdır"
    
    return True, clean_phone


def format_customer_info(customer):
    """Müşteri bilgilerini format et"""
    return {
        'id': customer.id,
        'full_name': customer.get_full_name(),
        'formatted_phone': customer.formatted_phone,
        'short_address': customer.get_short_address(),
        'full_address': customer.get_full_address(),
        'color_category': customer.color_category,
        'color_display': customer.color_display_name,
        'color_hex': customer.color,
        'is_premium': customer.is_premium_customer,
        'needs_attention': customer.needs_attention,
        'is_active': customer.is_active,
        'age_in_system': customer.age_in_system,
        'created_at': customer.created_at,
        'created_by': customer.created_by.get_full_name() if customer.created_by else None
    }


def get_color_choices():
    """Renk seçeneklerini döndür"""
    from .models import Customer
    return Customer.COLOR_CHOICES


def get_color_display(color_code):
    """Renk koduna göre görüntü adını döndür"""
    color_choices = get_color_choices()
    for code, display in color_choices:
        if code == color_code:
            return display
    return "Bilinmeyen"


def search_customers_advanced(search_term):
    """Gelişmiş müşteri arama"""
    from .models import Customer
    
    if not search_term:
        return Customer.objects.none()
    
    # Telefon araması için rakamları temizle
    clean_phone = ''.join(filter(str.isdigit, search_term))
    
    search_query = Q()
    
    # İsim ve soyisim araması
    search_query |= Q(first_name__icontains=search_term)
    search_query |= Q(last_name__icontains=search_term)
    
    # Tam isim araması
    name_parts = search_term.split()
    if len(name_parts) >= 2:
        search_query |= Q(
            first_name__icontains=name_parts[0],
            last_name__icontains=name_parts[1]
        )
    
    # Telefon araması
    if clean_phone:
        search_query |= Q(phone_number__icontains=clean_phone)
    
    # Adres araması
    search_query |= Q(city__icontains=search_term)
    search_query |= Q(district__icontains=search_term)
    search_query |= Q(neighborhood__icontains=search_term)
    search_query |= Q(address__icontains=search_term)
    
    return Customer.objects.filter(search_query)


def get_customer_dashboard_url_by_role(role):
    """Role göre müşteri dashboard URL'i"""
    role_urls = {
        'admin': 'customers:list',
        'readonly': 'customers:list',
        'product_manager': 'customers:list',
        'plant_manager': 'customers:stats',
        'seed_manager': 'customers:stats',
        'finance_personel': 'customers:stats',
        'shipping_personel': 'customers:list',
    }
    return role_urls.get(role, 'accounts:dashboard')


class CustomerFilters:
    """Müşteri filtreleme yardımcı sınıfı"""
    
    @staticmethod
    def by_color_category(category):
        """Renk kategorisine göre filtrele"""
        from .models import Customer
        return Customer.objects.by_color_category(category)
    
    @staticmethod
    def by_priority():
        """Öncelik sırasına göre sırala"""
        from .models import Customer
        return Customer.objects.all().order_by('color')
    
    @staticmethod
    def premium_customers():
        """Premium müşteriler"""
        from .models import Customer
        return Customer.objects.premium_customers()
    
    @staticmethod
    def attention_needed():
        """Dikkat gereken müşteriler"""
        from .models import Customer
        return Customer.objects.attention_needed_customers()
    
    @staticmethod
    def by_location(city=None, district=None):
        """Lokasyon bazlı filtreleme"""
        from .models import Customer
        queryset = Customer.objects.all()
        
        if city:
            queryset = queryset.by_city(city)
        if district:
            queryset = queryset.by_district(district)
            
        return queryset


def ajax_response_helper(success=True, message="", data=None):
    """AJAX yanıtları için yardımcı fonksiyon"""
    response_data = {
        'success': success,
        'message': message
    }
    
    if data:
        response_data.update(data)
    
    return JsonResponse(response_data)


def validate_customer_data(data):
    """Müşteri verisi validasyonu"""
    errors = []
    
    # Ad kontrolü
    if not data.get('first_name', '').strip():
        errors.append('Ad alanı gereklidir')
    
    # Soyad kontrolü
    if not data.get('last_name', '').strip():
        errors.append('Soyad alanı gereklidir')
    
    # Telefon kontrolü
    phone_valid, phone_msg = validate_phone_number(data.get('phone_number', ''))
    if not phone_valid:
        errors.append(phone_msg)
    
    # Şehir kontrolü
    if not data.get('city', '').strip():
        errors.append('Şehir alanı gereklidir')
    
    # İlçe kontrolü
    if not data.get('district', '').strip():
        errors.append('İlçe alanı gereklidir')
    
    # Adres kontrolü
    if not data.get('address', '').strip():
        errors.append('Adres alanı gereklidir')
    
    return len(errors) == 0, errors


def clean_customer_data(data):
    """Müşteri verisini temizle"""
    cleaned_data = {}
    
    # String alanları temizle
    string_fields = ['first_name', 'last_name', 'city', 'district', 'neighborhood', 'address']
    for field in string_fields:
        if field in data:
            cleaned_data[field] = data[field].strip()
    
    # Telefon numarasını temizle
    if 'phone_number' in data:
        cleaned_data['phone_number'] = ''.join(filter(str.isdigit, data['phone_number']))
    
    # Renk kontrolü
    if 'color' in data:
        valid_colors = [choice[0] for choice in get_color_choices()]
        if data['color'] in valid_colors:
            cleaned_data['color'] = data['color']
        else:
            cleaned_data['color'] = '#ffeb3b'  # Default color
    
    return cleaned_data
