from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from functools import wraps
import re

User = get_user_model()


class PinAuthenticationBackend(BaseBackend):
    """PIN kodu ile authentication backend"""
    
    def authenticate(self, request, pin_code=None, **kwargs):
        """PIN kodu ile kullanıcı doğrulama"""
        if pin_code:
            try:
                if len(pin_code) == 4 and pin_code.isdigit():
                    user = User.objects.get(pin_code=pin_code, is_active=True)
                    return user
            except User.DoesNotExist:
                pass
        return None
    
    def get_user(self, user_id):
        """Kullanıcı ID'si ile kullanıcı getirme"""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


def validate_pin(pin_code):
    """PIN kodu validasyonu"""
    if not pin_code:
        return False, "PIN kodu gereklidir"
    
    if len(pin_code) != 4:
        return False, "PIN kodu 4 haneli olmalıdır"
    
    if not pin_code.isdigit():
        return False, "PIN kodu sadece rakamlardan oluşmalıdır"
    
    # Basit PIN kodlarını engelle
    if pin_code in ['0000', '1234', '1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999']:
        return False, "Çok basit PIN kodu kullanılamaz"
    
    return True, "Geçerli PIN kodu"


def validate_phone_number(phone_number):
    """Telefon numarası validasyonu"""
    if not phone_number:
        return False, "Telefon numarası gereklidir"
    
    # Türkiye telefon numarası formatı (5XX XXX XX XX)
    phone_pattern = r'^5\d{9}$'
    
    if not re.match(phone_pattern, phone_number):
        return False, "Geçerli bir telefon numarası giriniz (5XXXXXXXXX)"
    
    return True, "Geçerli telefon numarası"


def get_role_display_name(role_code):
    """Role koduna göre görünen ismi getirme"""
    role_dict = dict(User.ROLES)
    return role_dict.get(role_code, role_code)


def get_user_permissions_by_role(role):
    """Role göre kullanıcı yetkilerini getirme"""
    permissions = {
        'admin': [
            'can_view_all',
            'can_create_all',
            'can_edit_all',
            'can_delete_all',
            'can_manage_users',
            'can_view_reports'
        ],
        'readonly': [
            'can_view_all',
            'can_view_reports'
        ],
        'product_manager': [
            'can_view_products',
            'can_create_products',
            'can_edit_products',
            'can_view_orders',
            'can_view_reports'
        ],
        'plant_manager': [
            'can_view_plants',
            'can_create_plants',
            'can_edit_plants',
            'can_view_seasons',
            'can_edit_seasons'
        ],
        'plant_personel': [
            'can_view_plants',
            'can_edit_plants',
            'can_view_seasons'
        ],
        'seed_manager': [
            'can_view_seeds',
            'can_create_seeds',
            'can_edit_seeds',
            'can_view_seasons'
        ],
        'seed_personel': [
            'can_view_seeds',
            'can_edit_seeds',
            'can_view_seasons'
        ],
        'finance_personel': [
            'can_view_orders',
            'can_edit_orders',
            'can_view_reports'
        ],
        'shipping_personel': [
            'can_view_orders',
            'can_edit_shipping',
            'can_view_shipping'
        ]
    }
    
    return permissions.get(role, [])


def role_required(allowed_roles):
    """Role bazlı yetkilendirme decorator'ı"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            if request.user.role not in allowed_roles:
                return JsonResponse({
                    'error': 'Bu işlem için yetkiniz yoktur',
                    'required_roles': allowed_roles,
                    'user_role': request.user.role
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def permission_required(permission_name):
    """İzin bazlı yetkilendirme decorator'ı"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            user_permissions = get_user_permissions_by_role(request.user.role)
            
            if permission_name not in user_permissions:
                return JsonResponse({
                    'error': 'Bu işlem için yetkiniz yoktur',
                    'required_permission': permission_name,
                    'user_permissions': user_permissions
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def format_user_info(user):
    """Kullanıcı bilgilerini formatla"""
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name() or user.username,
        'role': user.role,
        'role_display': get_role_display_name(user.role),
        'phone_number': user.phone_number,
        'email': user.email,
        'is_active': user.is_active,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        'last_login': user.last_login.isoformat() if user.last_login else None
    }


def is_admin_user(user):
    """Kullanıcının admin olup olmadığını kontrol et"""
    return user.is_authenticated and user.role == 'admin'


def is_manager_user(user):
    """Kullanıcının manager rolünde olup olmadığını kontrol et"""
    manager_roles = ['product_manager', 'plant_manager', 'seed_manager']
    return user.is_authenticated and user.role in manager_roles


def can_manage_users(user):
    """Kullanıcının diğer kullanıcıları yönetebilip yönetemeyeceğini kontrol et"""
    return user.is_authenticated and user.role in ['admin', 'readonly']


def get_dashboard_url_by_role(role):
    """Role göre dashboard URL'i getirme"""
    dashboard_urls = {
        'admin': 'admin:index',
        'readonly': 'accounts:dashboard',
        'product_manager': 'products:dashboard',
        'plant_manager': 'seasons:plant_dashboard',
        'plant_personel': 'seasons:plant_dashboard',
        'seed_manager': 'seasons:seed_dashboard',
        'seed_personel': 'seasons:seed_dashboard',
        'finance_personel': 'orders:finance_dashboard',
        'shipping_personel': 'orders:shipping_dashboard'
    }
    
    return dashboard_urls.get(role, 'accounts:dashboard')
