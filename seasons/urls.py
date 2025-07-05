from django.urls import path
from . import views

app_name = 'seasons'

urlpatterns = [
    # Season URLs
    path('', views.season_list, name='season_list'),
    path('create/', views.season_create, name='season_create'),
    path('<int:season_id>/', views.season_detail, name='season_detail'),
    path('<int:season_id>/activate/', views.season_activate, name='season_activate'),
    path('<int:season_id>/export/', views.season_export, name='season_export'),
    
    # Season Product URLs
    path('<int:season_id>/products/', views.season_product_list, name='season_product_list'),
    path('<int:season_id>/products/create/', views.season_product_create, name='season_product_create'),
    path('<int:season_id>/products/bulk-create/', views.season_product_bulk_create, name='season_product_bulk_create'),
    path('<int:season_id>/products/<int:product_id>/edit/', views.season_product_edit, name='season_product_edit'),
    path('<int:season_id>/products/<int:product_id>/delete/', views.season_product_delete, name='season_product_delete'),
    path('<int:season_id>/products/<int:product_id>/quick-price-update/', 
         views.season_product_quick_price_update, name='season_product_quick_price_update'),
    
    # API URLs
    path('api/<int:season_id>/products/', views.api_season_products, name='api_season_products'),
    path('api/<int:season_id>/statistics/', views.api_season_statistics, name='api_season_statistics'),
]
