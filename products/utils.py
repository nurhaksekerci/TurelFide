from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Q
from decimal import Decimal, InvalidOperation


def product_permission_required(allowed_roles=None):
    """Product modülü için rol bazlı yetki kontrolü"""
    if allowed_roles is None:
        allowed_roles = ['admin', 'product_manager']
    
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


def can_manage_products(user):
    """Kullanıcının ürün yönetimi yetkisi var mı?"""
    return user.is_authenticated and user.role in ['admin', 'product_manager']


def can_edit_products(user):
    """Kullanıcının ürün düzenleme yetkisi var mı?"""
    return user.is_authenticated and user.role in ['admin', 'product_manager']


def validate_decimal_field(value, field_name):
    """Decimal alan validasyonu"""
    if not value:
        return False, f"{field_name} gereklidir"
    
    try:
        decimal_value = Decimal(str(value))
        if decimal_value <= 0:
            return False, f"{field_name} pozitif bir sayı olmalıdır"
        return True, decimal_value
    except (InvalidOperation, ValueError):
        return False, f"{field_name} geçerli bir sayı olmalıdır"


def validate_integer_field(value, field_name, min_value=1):
    """Integer alan validasyonu"""
    if not value:
        return False, f"{field_name} gereklidir"
    
    try:
        int_value = int(value)
        if int_value < min_value:
            return False, f"{field_name} en az {min_value} olmalıdır"
        return True, int_value
    except (ValueError, TypeError):
        return False, f"{field_name} geçerli bir sayı olmalıdır"


def validate_species_data(data):
    """Tür verisi validasyonu"""
    errors = []
    
    if not data.get('name', '').strip():
        errors.append('Tür adı gereklidir')
    elif len(data.get('name', '').strip()) < 2:
        errors.append('Tür adı en az 2 karakter olmalıdır')
    
    return len(errors) == 0, errors


def validate_seed_brand_data(data):
    """Tohum markası verisi validasyonu"""
    errors = []
    
    # Ad kontrolü
    if not data.get('name', '').strip():
        errors.append('Marka adı gereklidir')
    elif len(data.get('name', '').strip()) < 2:
        errors.append('Marka adı en az 2 karakter olmalıdır')
    
    # Fiyat kontrolü
    is_valid_price, price_result = validate_decimal_field(
        data.get('price_per_packet'), 'Paket fiyatı'
    )
    if not is_valid_price:
        errors.append(price_result)
    
    # Tohum sayısı kontrolü
    is_valid_seeds, seeds_result = validate_integer_field(
        data.get('seeds_per_packet'), 'Paket başına tohum sayısı'
    )
    if not is_valid_seeds:
        errors.append(seeds_result)
    
    return len(errors) == 0, errors


def validate_variety_data(data):
    """Çeşit verisi validasyonu"""
    errors = []
    
    # Ad kontrolü
    if not data.get('name', '').strip():
        errors.append('Çeşit adı gereklidir')
    elif len(data.get('name', '').strip()) < 2:
        errors.append('Çeşit adı en az 2 karakter olmalıdır')
    
    # Tür kontrolü
    if not data.get('species'):
        errors.append('Tür seçimi gereklidir')
    
    # Tohum markası kontrolü
    if not data.get('seed_brand'):
        errors.append('Tohum markası seçimi gereklidir')
    
    return len(errors) == 0, errors


def validate_rootstock_data(data):
    """Anaç verisi validasyonu"""
    errors = []
    
    # Ad kontrolü
    if not data.get('name', '').strip():
        errors.append('Anaç adı gereklidir')
    elif len(data.get('name', '').strip()) < 2:
        errors.append('Anaç adı en az 2 karakter olmalıdır')
    
    # Tür kontrolü
    if not data.get('species'):
        errors.append('Tür seçimi gereklidir')
    
    return len(errors) == 0, errors


def clean_product_data(data):
    """Ürün verisini temizle"""
    cleaned_data = {}
    
    # String alanları temizle
    string_fields = ['name', 'description']
    for field in string_fields:
        if field in data:
            cleaned_data[field] = data[field].strip()
    
    # Decimal alanları temizle
    decimal_fields = ['price_per_packet']
    for field in decimal_fields:
        if field in data and data[field]:
            try:
                cleaned_data[field] = Decimal(str(data[field]))
            except (InvalidOperation, ValueError):
                pass  # Validation'da yakalanacak
    
    # Integer alanları temizle
    integer_fields = ['seeds_per_packet', 'species', 'seed_brand']
    for field in integer_fields:
        if field in data and data[field]:
            try:
                cleaned_data[field] = int(data[field])
            except (ValueError, TypeError):
                pass  # Validation'da yakalanacak
    
    # Enum alanları
    if 'vigor_level' in data and data['vigor_level']:
        valid_vigor_levels = ['low', 'medium', 'high']
        if data['vigor_level'] in valid_vigor_levels:
            cleaned_data['vigor_level'] = data['vigor_level']
    
    return cleaned_data


def format_product_info(product, product_type):
    """Ürün bilgilerini format et"""
    base_info = {
        'id': product.id,
        'name': product.name,
        'is_active': product.is_active,
        'created_at': product.created_at,
        'updated_at': product.updated_at,
        'type': product_type
    }
    
    if product_type == 'species':
        base_info.update({
            'varieties_count': product.active_varieties_count,
            'rootstocks_count': product.active_rootstocks_count,
        })
    elif product_type == 'seed_brand':
        base_info.update({
            'price_per_packet': product.price_per_packet,
            'seeds_per_packet': product.seeds_per_packet,
            'price_per_seed': product.price_per_seed,
        })
    elif product_type == 'variety':
        base_info.update({
            'species_name': product.species.name,
            'seed_brand_name': product.seed_brand.name,
            'full_name': product.get_full_name(),
            'full_name_with_brand': product.get_full_name_with_brand(),
        })
    elif product_type == 'rootstock':
        base_info.update({
            'species_name': product.species.name,
            'vigor_level': product.vigor_level,
            'vigor_level_display': product.get_vigor_level_display() if product.vigor_level else None,
            'description': product.description,
            'full_name': product.get_full_name(),
        })
    
    return base_info


def get_vigor_choices():
    """Vigör seviyesi seçeneklerini döndür"""
    return [
        ('low', 'Düşük Vigör'),
        ('medium', 'Orta Vigör'),
        ('high', 'Yüksek Vigör'),
    ]


def ajax_response_helper(success=True, message="", data=None):
    """AJAX yanıtları için yardımcı fonksiyon"""
    response_data = {
        'success': success,
        'message': message
    }
    
    if data:
        response_data.update(data)
    
    return JsonResponse(response_data)


def search_products_advanced(search_term, product_type=None):
    """Gelişmiş ürün arama"""
    from .models import Species, SeedBrand, Variety, Rootstock
    
    if not search_term or len(search_term) < 2:
        return []
    
    results = []
    
    if not product_type or product_type == 'species':
        species = Species.objects.filter(
            name__icontains=search_term, is_active=True
        )[:5]
        for s in species:
            results.append({
                'type': 'species',
                'id': s.id,
                'name': s.name,
                'display': f"Tür: {s.name}"
            })
    
    if not product_type or product_type == 'seed_brand':
        brands = SeedBrand.objects.filter(
            name__icontains=search_term, is_active=True
        )[:5]
        for b in brands:
            results.append({
                'type': 'seed_brand',
                'id': b.id,
                'name': b.name,
                'display': f"Marka: {b.name} ({b.price_per_packet}₺)"
            })
    
    if not product_type or product_type == 'variety':
        varieties = Variety.objects.filter(
            Q(name__icontains=search_term) | Q(species__name__icontains=search_term),
            is_active=True
        ).select_related('species', 'seed_brand')[:5]
        for v in varieties:
            results.append({
                'type': 'variety',
                'id': v.id,
                'name': v.name,
                'display': f"Çeşit: {v.get_full_name_with_brand()}"
            })
    
    if not product_type or product_type == 'rootstock':
        rootstocks = Rootstock.objects.filter(
            Q(name__icontains=search_term) | Q(species__name__icontains=search_term),
            is_active=True
        ).select_related('species')[:5]
        for r in rootstocks:
            results.append({
                'type': 'rootstock',
                'id': r.id,
                'name': r.name,
                'display': f"Anaç: {r.get_full_name()}"
            })
    
    return results


def get_product_dashboard_url_by_role(role):
    """Role göre ürün dashboard URL'i"""
    role_urls = {
        'admin': 'products:dashboard',
        'product_manager': 'products:dashboard',
        'plant_manager': 'products:dashboard',
        'seed_manager': 'products:species_list',
        'readonly': 'products:dashboard',
    }
    return role_urls.get(role, 'accounts:dashboard')


class ProductFilters:
    """Ürün filtreleme yardımcı sınıfı"""
    
    @staticmethod
    def active_species():
        """Aktif türler"""
        from .models import Species
        return Species.objects.filter(is_active=True)
    
    @staticmethod
    def active_seed_brands():
        """Aktif tohum markaları"""
        from .models import SeedBrand
        return SeedBrand.objects.filter(is_active=True)
    
    @staticmethod
    def varieties_by_species(species_id):
        """Türe göre çeşitler"""
        from .models import Variety
        return Variety.objects.filter(species_id=species_id, is_active=True)
    
    @staticmethod
    def rootstocks_by_species(species_id):
        """Türe göre anaçlar"""
        from .models import Rootstock
        return Rootstock.objects.filter(species_id=species_id, is_active=True)
    
    @staticmethod
    def by_vigor_level(vigor_level):
        """Vigör seviyesine göre anaçlar"""
        from .models import Rootstock
        return Rootstock.objects.filter(vigor_level=vigor_level, is_active=True)
