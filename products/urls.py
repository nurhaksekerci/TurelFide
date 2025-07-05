from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Dashboard
    path('', views.product_dashboard_view, name='dashboard'),
    
    # Species URLs
    path('species/', views.species_list_view, name='species_list'),
    path('species/create/', views.species_create_view, name='species_create'),
    path('species/<int:species_id>/', views.species_detail_view, name='species_detail'),
    path('species/<int:species_id>/edit/', views.species_edit_view, name='species_edit'),
    
    # SeedBrand URLs
    path('brands/', views.seed_brand_list_view, name='seed_brand_list'),
    path('brands/create/', views.seed_brand_create_view, name='seed_brand_create'),
    path('brands/<int:brand_id>/', views.seed_brand_detail_view, name='seed_brand_detail'),
    
    # Variety URLs
    path('varieties/', views.variety_list_view, name='variety_list'),
    path('varieties/create/', views.variety_create_view, name='variety_create'),
    
    # Rootstock URLs
    path('rootstocks/', views.rootstock_list_view, name='rootstock_list'),
    path('rootstocks/create/', views.rootstock_create_view, name='rootstock_create'),
    
    # AJAX Endpoints
    path('ajax/toggle-status/<str:model_type>/<int:object_id>/', 
         views.ajax_toggle_status, name='ajax_toggle_status'),
    path('ajax/search/', views.ajax_search_products, name='ajax_search_products'),
    path('ajax/bulk-toggle/', views.ajax_bulk_toggle_status, name='ajax_bulk_toggle_status'),
    path('ajax/varieties-by-species/<int:species_id>/', 
         views.ajax_get_varieties_by_species, name='ajax_varieties_by_species'),
    path('ajax/rootstocks-by-species/<int:species_id>/', 
         views.ajax_get_rootstocks_by_species, name='ajax_rootstocks_by_species'),
]
