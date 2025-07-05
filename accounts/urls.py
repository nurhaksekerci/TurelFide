from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('ajax/login/', views.ajax_login, name='ajax_login'),
    
    # Dashboard URLs
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    
    # User Management URLs (Admin/Readonly only)
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.create_user_view, name='create_user'),
    path('users/<int:user_id>/', views.user_detail_view, name='user_detail'),
    path('users/<int:user_id>/reset-pin/', views.reset_pin_view, name='reset_pin'),
    
    # AJAX URLs
    path('ajax/toggle-user-status/<int:user_id>/', views.ajax_toggle_user_status, name='ajax_toggle_user_status'),
    path('ajax/user-search/', views.ajax_user_search, name='ajax_user_search'),
    path('ajax/get-pin/<int:user_id>/', views.ajax_get_pin, name='ajax_get_pin'),
    path('ajax/get-own-pin/', views.ajax_get_own_pin, name='ajax_get_own_pin'),
]
