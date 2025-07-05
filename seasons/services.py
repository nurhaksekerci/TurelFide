from typing import List, Dict, Optional
from django.db import transaction
from django.db.models import QuerySet
from datetime import date, datetime
from decimal import Decimal

from .models import Season, SeasonProduct
from products.models import Variety, Rootstock


class SeasonService:
    """Sezon yönetimi için servis sınıfı"""
    
    @staticmethod
    def create_season(name: str, start_date: date, is_active: bool = True) -> Season:
        """Yeni sezon oluşturur"""
        # Aktif sezon varsa diğerlerini pasif yap
        if is_active:
            Season.objects.filter(is_active=True).update(is_active=False)
        
        season = Season.objects.create(
            name=name,
            start_date=start_date,
            is_active=is_active
        )
        return season
    
    @staticmethod
    def get_active_season() -> Optional[Season]:
        """Aktif sezonu döner"""
        return Season.objects.filter(is_active=True).first()
    
    @staticmethod
    def get_all_seasons() -> QuerySet[Season]:
        """Tüm sezonları döner"""
        return Season.objects.all().order_by('-start_date')
    
    @staticmethod
    def activate_season(season_id: int) -> Season:
        """Belirtilen sezonu aktif yapar, diğerlerini pasif yapar"""
        with transaction.atomic():
            Season.objects.filter(is_active=True).update(is_active=False)
            season = Season.objects.get(id=season_id)
            season.is_active = True
            season.save()
        return season


class SeasonProductService:
    """Sezonluk ürün yönetimi için servis sınıfı"""
    
    @staticmethod
    def create_season_product(
        season_id: int,
        variety_id: int,
        rootstock_id: Optional[int] = None,
        duration_data: Optional[Dict] = None,
        price_data: Optional[Dict] = None
    ) -> SeasonProduct:
        """Yeni sezonluk ürün oluşturur"""
        
        # Default duration values
        default_durations = {
            'rootstock_planting_duration': 30,
            'scion_planting_duration': 45,
            'single_stem_grafting_duration': 60,
            'double_stem_grafting_duration': 75,
            'head_formation_duration': 90,
            'waiting_on_room_duration': 30
        }
        
        if duration_data:
            default_durations.update(duration_data)
        
        # Default price values (18 months for both single and double stem)
        default_prices = {}
        for i in range(1, 19):
            default_prices[f'price_single_stem_{i}'] = Decimal('0.00')
            default_prices[f'price_double_stem_{i}'] = Decimal('0.00')
        
        if price_data:
            default_prices.update(price_data)
        
        season_product = SeasonProduct.objects.create(
            season_id=season_id,
            variety_id=variety_id,
            rootstock_id=rootstock_id,
            **default_durations,
            **default_prices
        )
        
        return season_product
    
    @staticmethod
    def update_season_product_prices(
        season_product_id: int, 
        price_data: Dict[str, Decimal]
    ) -> SeasonProduct:
        """Sezonluk ürün fiyatlarını günceller"""
        season_product = SeasonProduct.objects.get(id=season_product_id)
        
        # Fiyat alanlarını güncelle
        for field, value in price_data.items():
            if hasattr(season_product, field):
                setattr(season_product, field, value)
        
        season_product.save()
        return season_product
    
    @staticmethod
    def update_season_product_durations(
        season_product_id: int,
        duration_data: Dict[str, int]
    ) -> SeasonProduct:
        """Sezonluk ürün sürelerini günceller"""
        season_product = SeasonProduct.objects.get(id=season_product_id)
        
        # Süre alanlarını güncelle
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
                setattr(season_product, field, value)
        
        season_product.save()
        return season_product
    
    @staticmethod
    def get_season_products(season_id: int) -> QuerySet[SeasonProduct]:
        """Belirtilen sezondaki tüm ürünleri döner"""
        return SeasonProduct.objects.filter(
            season_id=season_id,
            is_active=True
        ).select_related('season', 'variety', 'rootstock')
    
    @staticmethod
    def get_season_product_by_variety(
        season_id: int, 
        variety_id: int, 
        rootstock_id: Optional[int] = None
    ) -> Optional[SeasonProduct]:
        """Belirtilen sezon, çeşit ve anaç kombinasyonuna göre ürün döner"""
        return SeasonProduct.objects.filter(
            season_id=season_id,
            variety_id=variety_id,
            rootstock_id=rootstock_id,
            is_active=True
        ).first()
    
    @staticmethod
    def bulk_create_season_products(
        season_id: int,
        varieties: List[int],
        rootstocks: List[int] = None,
        default_durations: Dict = None,
        default_prices: Dict = None
    ) -> List[SeasonProduct]:
        """Birden fazla çeşit için sezonluk ürün oluşturur"""
        season_products = []
        
        if rootstocks:
            # Çeşit-anaç kombinasyonları
            for variety_id in varieties:
                for rootstock_id in rootstocks:
                    season_product = SeasonProductService.create_season_product(
                        season_id=season_id,
                        variety_id=variety_id,
                        rootstock_id=rootstock_id,
                        duration_data=default_durations,
                        price_data=default_prices
                    )
                    season_products.append(season_product)
        else:
            # Sadece çeşitler
            for variety_id in varieties:
                season_product = SeasonProductService.create_season_product(
                    season_id=season_id,
                    variety_id=variety_id,
                    duration_data=default_durations,
                    price_data=default_prices
                )
                season_products.append(season_product)
        
        return season_products
    
    @staticmethod
    def calculate_delivery_date(
        season_product: SeasonProduct,
        order_date: date,
        stem_type: str = 'single'
    ) -> date:
        """Teslimat tarihini hesaplar"""
        from datetime import timedelta
        
        total_days = (
            season_product.rootstock_planting_duration +
            season_product.scion_planting_duration +
            season_product.waiting_on_room_duration
        )
        
        if stem_type == 'single':
            total_days += season_product.single_stem_grafting_duration
        else:
            total_days += season_product.double_stem_grafting_duration
        
        total_days += season_product.head_formation_duration
        
        return order_date + timedelta(days=total_days)
