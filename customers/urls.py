from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # Ana sayfalar
    path('', views.customer_list_view, name='list'),
    path('create/', views.customer_create_view, name='create'),
    path('<int:customer_id>/', views.customer_detail_view, name='detail'),
    path('<int:customer_id>/edit/', views.customer_edit_view, name='edit'),
    path('<int:customer_id>/delete/', views.customer_delete_view, name='delete'),
    path('stats/', views.customer_stats_view, name='stats'),
    
    # AJAX endpoints
    path('ajax/toggle-status/<int:customer_id>/', views.ajax_toggle_customer_status, name='ajax_toggle_status'),
    path('ajax/search/', views.ajax_customer_search, name='ajax_search'),
    path('ajax/bulk-update-color/', views.ajax_bulk_update_color, name='ajax_bulk_update_color'),
    path('ajax/bulk-toggle-status/', views.ajax_bulk_toggle_status, name='ajax_bulk_toggle_status'),
]
