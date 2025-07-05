from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Ana giriş - Sezon seçimi
    path('', views.season_selection, name='season_selection'),
    
    # Ekim takip için sezon seçimi
    path('planting/season-selection/', views.planting_season_selection, name='planting_season_selection'),
    
    # Sezon bazlı sipariş yönetimi
    path('season/<int:season_id>/', views.order_list, name='order_list'),
    path('season/<int:season_id>/create/', views.order_create, name='order_create'),
    path('season/<int:season_id>/statistics/', views.season_statistics, name='season_statistics'),
    path('season/<int:season_id>/export/', views.season_export, name='season_export'),
    path('season/<int:season_id>/bulk-send-to-planting/', views.bulk_send_to_planting, name='bulk_send_to_planting'),
    path('season/<int:season_id>/bulk-send-to-rootstock-planting/', views.bulk_send_to_rootstock_planting, name='bulk_send_to_rootstock_planting'),
    path('season/<int:season_id>/planting/', views.planting_list, name='planting_list'),
    path('season/<int:season_id>/planting/<int:request_id>/', views.planting_detail, name='planting_detail'),
    path('season/<int:season_id>/planting/<int:request_id>/status/', views.planting_status_update, name='planting_status_update'),
    
    # Sipariş detay ve yönetimi
    path('season/<int:season_id>/order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('season/<int:season_id>/order/<int:order_id>/edit/', views.order_edit, name='order_edit'),
    path('season/<int:season_id>/order/<int:order_id>/delete/', views.order_delete, name='order_delete'),
    path('season/<int:season_id>/order/<int:order_id>/status/', views.order_status_update, name='order_status_update'),
    path('season/<int:season_id>/order/<int:order_id>/clone/', views.order_clone, name='order_clone'),
    
    # Sipariş kalemi yönetimi
    path('season/<int:season_id>/order/<int:order_id>/items/', views.order_items_manage, name='order_items_manage'),
    path('season/<int:season_id>/order/<int:order_id>/item/add/', views.order_item_add, name='order_item_add'),
    path('season/<int:season_id>/order/<int:order_id>/item/<int:item_id>/edit/', views.order_item_edit, name='order_item_edit'),
    path('season/<int:season_id>/order/<int:order_id>/item/<int:item_id>/delete/', views.order_item_delete, name='order_item_delete'),
    
    # Müşteri bazlı görünümler
    path('season/<int:season_id>/customer/<int:customer_id>/', views.customer_orders, name='customer_orders'),
    
    # AJAX API endpoints
    path('api/season-products/<int:season_id>/', views.api_season_products, name='api_season_products'),
    path('api/season-product-by-variety/<int:season_id>/', views.api_season_product_by_variety, name='api_season_product_by_variety'),
    path('api/varieties-by-species/<int:species_id>/', views.api_varieties_by_species, name='api_varieties_by_species'),
    path('api/product-price/<int:season_product_id>/', views.api_product_price, name='api_product_price'),
    path('api/order-totals/<int:order_id>/', views.api_order_totals, name='api_order_totals'),
    
    # Raporlar
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/season/<int:season_id>/', views.season_report, name='season_report'),
    path('reports/customer/<int:customer_id>/', views.customer_report, name='customer_report'),
]
