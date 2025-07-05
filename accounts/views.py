from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
import json

from .services import UserService
from .utils import (
    validate_pin, validate_phone_number, role_required, 
    permission_required, format_user_info, can_manage_users,
    get_dashboard_url_by_role, get_role_display_name
)
from django.contrib.auth import get_user_model

User = get_user_model()


def login_view(request):
    """PIN ile giriş sayfası"""
    if request.user.is_authenticated:
        # Zaten giriş yapmışsa dashboard'a yönlendir
        dashboard_url = get_dashboard_url_by_role(request.user.role)
        return redirect(dashboard_url)
    
    if request.method == 'POST':
        pin_code = request.POST.get('pin_code', '').strip()
        
        # PIN validasyonu
        is_valid, message = validate_pin(pin_code)
        if not is_valid:
            messages.error(request, message)
            return render(request, 'accounts/login.html')
        
        # Kullanıcı doğrulama
        user = authenticate(request, pin_code=pin_code)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Hoş geldiniz, {user.get_full_name() or user.username}!')
            
            # Role göre dashboard'a yönlendir
            dashboard_url = get_dashboard_url_by_role(user.role)
            return redirect(dashboard_url)
        else:
            messages.error(request, 'Geçersiz PIN kodu!')
    
    return render(request, 'accounts/login.html')


@csrf_exempt
@require_http_methods(["POST"])
def ajax_login(request):
    """AJAX ile PIN doğrulama"""
    try:
        data = json.loads(request.body)
        pin_code = data.get('pin_code', '').strip()
        
        # PIN validasyonu
        is_valid, message = validate_pin(pin_code)
        if not is_valid:
            return JsonResponse({'success': False, 'message': message})
        
        # Kullanıcı doğrulama
        user = authenticate(request, pin_code=pin_code)
        
        if user is not None:
            login(request, user)
            return JsonResponse({
                'success': True, 
                'message': f'Hoş geldiniz, {user.get_full_name() or user.username}!',
                'redirect_url': get_dashboard_url_by_role(user.role),
                'user_info': format_user_info(user)
            })
        else:
            return JsonResponse({'success': False, 'message': 'Geçersiz PIN kodu!'})
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Geçersiz veri formatı'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Bir hata oluştu'})


@login_required
def logout_view(request):
    """Çıkış yapma"""
    user_name = request.user.get_full_name() or request.user.username
    logout(request)
    messages.success(request, f'Güle güle, {user_name}!')
    return redirect('accounts:login')


@login_required
def dashboard_view(request):
    """Ana dashboard sayfası"""
    user = request.user
    
    context = {
        'user': user,
        'user_info': format_user_info(user),
        'role_display': get_role_display_name(user.role),
        'can_manage_users': can_manage_users(user),
    }
    
    # Role'e göre özel dashboard template'i kullan
    template_map = {
        'admin': 'accounts/dashboard.html',
        'readonly': 'accounts/dashboard.html',
        'product_manager': 'accounts/dashboard.html',
        'plant_manager': 'accounts/dashboard.html',
        'seed_manager': 'accounts/dashboard.html',
    }
    
    template = template_map.get(user.role, 'accounts/dashboard.html')
    return render(request, template, context)


@login_required
@role_required(['admin', 'readonly'])
def user_list_view(request):
    """Kullanıcı listesi (sadece admin ve readonly)"""
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    
    users = User.objects.all().order_by('-date_joined')
    
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Sayfalama
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'roles': User.ROLES,
        'total_users': users.count()
    }
    
    return render(request, 'accounts/user_list.html', context)


@login_required
@role_required(['admin'])
def create_user_view(request):
    """Yeni kullanıcı oluşturma (sadece admin)"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', '').strip()
        
        # Validasyonlar
        errors = []
        
        if not username:
            errors.append('Kullanıcı adı gereklidir')
        elif User.objects.filter(username=username).exists():
            errors.append('Bu kullanıcı adı zaten kullanılıyor')
        
        if not first_name:
            errors.append('Ad gereklidir')
        
        if not last_name:
            errors.append('Soyad gereklidir')
        
        # Telefon numarası validasyonu
        is_valid_phone, phone_message = validate_phone_number(phone_number)
        if not is_valid_phone:
            errors.append(phone_message)
        elif User.objects.filter(phone_number=phone_number).exists():
            errors.append('Bu telefon numarası zaten kullanılıyor')
        
        if role not in [choice[0] for choice in User.ROLES]:
            errors.append('Geçersiz rol seçimi')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                user, pin_code = UserService.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    email=email,
                    role=role
                )
                
                messages.success(request, f'Kullanıcı başarıyla oluşturuldu. PIN Kodu: {pin_code}')
                return redirect('accounts:user_detail', user_id=user.id)
                
            except Exception as e:
                messages.error(request, f'Kullanıcı oluşturulurken hata oluştu: {str(e)}')
    
    context = {
        'roles': User.ROLES
    }
    
    return render(request, 'accounts/create_user.html', context)


@login_required
@role_required(['admin', 'readonly'])
def user_detail_view(request, user_id):
    """Kullanıcı detay sayfası"""
    user = get_object_or_404(User, id=user_id)
    
    context = {
        'target_user': user,
        'user_info': format_user_info(user),
        'can_edit': request.user.role == 'admin'
    }
    
    return render(request, 'accounts/user_detail.html', context)


@login_required
@role_required(['admin'])
def reset_pin_view(request, user_id):
    """Kullanıcının PIN kodunu sıfırlama (sadece admin)"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        try:
            new_pin = UserService.reset_pin(user)
            messages.success(request, f'{user.get_full_name()} kullanıcısının yeni PIN kodu: {new_pin}')
        except Exception as e:
            messages.error(request, f'PIN sıfırlanırken hata oluştu: {str(e)}')
    
    return redirect('accounts:user_detail', user_id=user_id)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def ajax_toggle_user_status(request, user_id):
    """AJAX ile kullanıcı durumunu aktif/pasif yapma"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'message': 'Yetkiniz yoktur'})
    
    user = get_object_or_404(User, id=user_id)
    
    if user == request.user:
        return JsonResponse({'success': False, 'message': 'Kendi hesabınızı deaktive edemezsiniz'})
    
    try:
        if user.is_active:
            UserService.deactivate_user(user)
            message = f'{user.get_full_name()} deaktive edildi'
        else:
            UserService.activate_user(user)
            message = f'{user.get_full_name()} aktive edildi'
        
        return JsonResponse({
            'success': True, 
            'message': message,
            'is_active': user.is_active
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def profile_view(request):
    """Kullanıcı profil sayfası"""
    user = request.user
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        
        # Validasyonlar
        errors = []
        
        if not first_name:
            errors.append('Ad gereklidir')
        
        if not last_name:
            errors.append('Soyad gereklidir')
        
        # Telefon numarası validasyonu
        is_valid_phone, phone_message = validate_phone_number(phone_number)
        if not is_valid_phone:
            errors.append(phone_message)
        elif User.objects.filter(phone_number=phone_number).exclude(id=user.id).exists():
            errors.append('Bu telefon numarası zaten kullanılıyor')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            user.first_name = first_name
            user.last_name = last_name
            user.phone_number = phone_number
            user.email = email
            user.save()
            
            messages.success(request, 'Profil bilgileriniz güncellendi')
            return redirect('accounts:profile')
    
    context = {
        'user_info': format_user_info(user)
    }
    
    return render(request, 'accounts/profile.html', context)


@csrf_exempt
@require_http_methods(["GET"])
def ajax_user_search(request):
    """AJAX ile kullanıcı arama"""
    if not request.user.is_authenticated or not can_manage_users(request.user):
        return JsonResponse({'success': False, 'message': 'Yetkiniz yoktur'})
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    users = User.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(username__icontains=query)
    ).filter(is_active=True)[:10]
    
    user_list = []
    for user in users:
        user_list.append({
            'id': user.id,
            'name': user.get_full_name() or user.username,
            'role': get_role_display_name(user.role),
            'phone': user.phone_number
        })
    
    return JsonResponse({'users': user_list})


@csrf_exempt
@login_required
@require_http_methods(["GET"])
def ajax_get_pin(request, user_id):
    """AJAX ile PIN kodunu getirme (sadece superuser ve staff)"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'success': False, 'message': 'Bu işlem için yetkiniz yoktur'})
    
    try:
        target_user = get_object_or_404(User, id=user_id)
        
        # Kendi PIN'ini her zaman görebilir, diğerleri için superuser/staff kontrolü
        if target_user != request.user and not (request.user.is_superuser or request.user.is_staff):
            return JsonResponse({'success': False, 'message': 'Bu kullanıcının PIN kodunu görüntüleme yetkiniz yoktur'})
        
        return JsonResponse({
            'success': True,
            'pin_code': target_user.pin_code,
            'user_name': target_user.get_full_name() or target_user.username
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'PIN kodu alınırken hata oluştu'})


@csrf_exempt
@login_required
@require_http_methods(["GET"])
def ajax_get_own_pin(request):
    """AJAX ile kendi PIN kodunu getirme"""
    try:
        return JsonResponse({
            'success': True,
            'pin_code': request.user.pin_code,
            'user_name': request.user.get_full_name() or request.user.username
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'PIN kodu alınırken hata oluştu'})
