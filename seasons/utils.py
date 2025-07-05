from typing import Dict, List, Tuple
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import QuerySet

from .models import Season, SeasonProduct


def format_season_name(name: str) -> str:
    """Sezon adını formatlar"""
    return f"{name} Sezonu"


def get_price_fields_mapping() -> Dict[str, str]:
    """Fiyat alanları için mapping döner"""
    mapping = {}
    for i in range(1, 19):
        mapping[f'price_single_stem_{i}'] = f'{i}. Ay Tek Gövde'
        mapping[f'price_double_stem_{i}'] = f'{i}. Ay Çift Gövde'
    return mapping


def get_duration_fields_mapping() -> Dict[str, str]:
    """Süre alanları için mapping döner"""
    return {
        'rootstock_planting_duration': 'Anaç Ekim Süresi',
        'scion_planting_duration': 'Kalem Ekim Süresi',
        'single_stem_grafting_duration': 'Tek Gövde Aşılama Süresi',
        'double_stem_grafting_duration': 'Çift Gövde Aşılama Süresi',
        'head_formation_duration': 'Kafa Oluşturma Süresi',
        'waiting_on_room_duration': 'Oda Bekleme Süresi'
    }


def calculate_total_production_time(season_product: SeasonProduct, stem_type: str = 'single') -> int:
    """Toplam üretim süresini hesaplar"""
    base_duration = (
        season_product.rootstock_planting_duration +
        season_product.scion_planting_duration +
        season_product.head_formation_duration +
        season_product.waiting_on_room_duration
    )
    
    if stem_type == 'single':
        return base_duration + season_product.single_stem_grafting_duration
    else:
        return base_duration + season_product.double_stem_grafting_duration


def get_monthly_prices(season_product: SeasonProduct, stem_type: str = 'single') -> List[Tuple[int, Decimal]]:
    """Aylık fiyatları liste olarak döner"""
    prices = []
    
    for month in range(1, 19):
        field_name = f'price_{stem_type}_stem_{month}'
        price = getattr(season_product, field_name, Decimal('0.00'))
        prices.append((month, price))
    
    return prices


def validate_price_data(price_data: Dict[str, str]) -> Dict[str, Decimal]:
    """Fiyat verilerini doğrular ve Decimal'a çevirir"""
    validated_prices = {}
    
    for field, value in price_data.items():
        if field.startswith('price_'):
            try:
                validated_prices[field] = Decimal(str(value))
            except (ValueError, TypeError):
                validated_prices[field] = Decimal('0.00')
    
    return validated_prices


def validate_duration_data(duration_data: Dict[str, str]) -> Dict[str, int]:
    """Süre verilerini doğrular ve integer'a çevirir"""
    validated_durations = {}
    
    duration_fields = [
        'rootstock_planting_duration',
        'scion_planting_duration',
        'single_stem_grafting_duration', 
        'double_stem_grafting_duration',
        'head_formation_duration',
        'waiting_on_room_duration'
    ]
    
    for field, value in duration_data.items():
        if field in duration_fields:
            try:
                validated_value = int(value)
                if validated_value < 1:
                    validated_value = 1
                validated_durations[field] = validated_value
            except (ValueError, TypeError):
                # Default values
                default_values = {
                    'rootstock_planting_duration': 30,
                    'scion_planting_duration': 45,
                    'single_stem_grafting_duration': 60,
                    'double_stem_grafting_duration': 75,
                    'head_formation_duration': 90,
                    'waiting_on_room_duration': 30
                }
                validated_durations[field] = default_values.get(field, 30)
    
    return validated_durations


def get_season_statistics(season: Season) -> Dict:
    """Sezon istatistiklerini döner"""
    season_products = SeasonProduct.objects.filter(season=season, is_active=True)
    
    total_products = season_products.count()
    total_varieties = season_products.values('variety').distinct().count()
    total_rootstocks = season_products.exclude(rootstock__isnull=True).values('rootstock').distinct().count()
    
    # Ortalama üretim süreleri
    avg_single_production = 0
    avg_double_production = 0
    
    if total_products > 0:
        total_single = sum(calculate_total_production_time(sp, 'single') for sp in season_products)
        total_double = sum(calculate_total_production_time(sp, 'double') for sp in season_products)
        
        avg_single_production = round(total_single / total_products)
        avg_double_production = round(total_double / total_products)
    
    return {
        'total_products': total_products,
        'total_varieties': total_varieties,
        'total_rootstocks': total_rootstocks,
        'avg_single_production_days': avg_single_production,
        'avg_double_production_days': avg_double_production
    }


def generate_price_structure_template() -> Dict[str, Decimal]:
    """Fiyat yapısı şablonu oluşturur"""
    template = {}
    
    for i in range(1, 19):
        template[f'price_single_stem_{i}'] = Decimal('0.00')
        template[f'price_double_stem_{i}'] = Decimal('0.00')
    
    return template


def export_season_products_data(season: Season) -> List[Dict]:
    """Sezon ürünlerini export için hazırlar"""
    season_products = SeasonProduct.objects.filter(
        season=season, 
        is_active=True
    ).select_related('variety', 'rootstock')
    
    export_data = []
    
    for sp in season_products:
        product_data = {
            'season': season.name,
            'variety': sp.variety.get_full_name(),
            'rootstock': sp.rootstock.name if sp.rootstock else 'Yok',
            'rootstock_planting_duration': sp.rootstock_planting_duration,
            'scion_planting_duration': sp.scion_planting_duration,
            'single_stem_grafting_duration': sp.single_stem_grafting_duration,
            'double_stem_grafting_duration': sp.double_stem_grafting_duration,
            'head_formation_duration': sp.head_formation_duration,
            'waiting_on_room_duration': sp.waiting_on_room_duration,
        }
        
        # Fiyatları ekle
        for i in range(1, 19):
            product_data[f'single_stem_month_{i}'] = getattr(sp, f'price_single_stem_{i}')
            product_data[f'double_stem_month_{i}'] = getattr(sp, f'price_double_stem_{i}')
        
        export_data.append(product_data)
    
    return export_data


def check_season_completeness(season: Season) -> Dict:
    """Sezonun eksiksizlik durumunu kontrol eder"""
    season_products = SeasonProduct.objects.filter(season=season, is_active=True)
    
    missing_prices_count = 0
    zero_duration_count = 0
    
    for sp in season_products:
        # Fiyat kontrolü
        has_prices = False
        for i in range(1, 19):
            single_price = getattr(sp, f'price_single_stem_{i}')
            double_price = getattr(sp, f'price_double_stem_{i}')
            if single_price > 0 or double_price > 0:
                has_prices = True
                break
        
        if not has_prices:
            missing_prices_count += 1
        
        # Süre kontrolü
        durations = [
            sp.rootstock_planting_duration,
            sp.scion_planting_duration,
            sp.single_stem_grafting_duration,
            sp.double_stem_grafting_duration,
            sp.head_formation_duration,
            sp.waiting_on_room_duration
        ]
        
        if any(d <= 0 for d in durations):
            zero_duration_count += 1
    
    total_products = season_products.count()
    
    return {
        'total_products': total_products,
        'missing_prices_count': missing_prices_count,
        'zero_duration_count': zero_duration_count,
        'completeness_percentage': round(
            ((total_products - missing_prices_count - zero_duration_count) / total_products * 100) 
            if total_products > 0 else 0
        )
    }
