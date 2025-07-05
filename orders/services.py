from typing import List, Dict, Optional, Tuple
from django.db import transaction
from django.db.models import QuerySet, Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from datetime import date, datetime

from .models import Order, OrderItem, OrderStatusHistory
from customers.models import Customer
from seasons.models import Season, SeasonProduct
from products.models import Variety, Rootstock


class OrderService:
    """Sipariş yönetimi için servis sınıfı"""
    
    @staticmethod
    def get_orders_by_season(season_id: int) -> QuerySet[Order]:
        """Belirtilen sezondaki tüm siparişleri döner"""
        return Order.objects.filter(
            season_id=season_id
        ).select_related('customer', 'season', 'created_by').prefetch_related('items')
    
    @staticmethod
    def create_order(
        customer_id: int,
        season_id: int,
        requested_delivery_date: date,
        created_by_id: Optional[int] = None,
        **kwargs
    ) -> Order:
        """Yeni sipariş oluşturur"""
        order = Order.objects.create(
            customer_id=customer_id,
            season_id=season_id,
            requested_delivery_date=requested_delivery_date,
            created_by_id=created_by_id,
            **kwargs
        )
        
        # Durum geçmişi oluştur
        OrderStatusHistoryService.create_status_change(
            order=order,
            to_status=order.status,
            changed_by_id=created_by_id,
            notes="Sipariş oluşturuldu"
        )
        
        return order
    
    @staticmethod
    def update_order_status(
        order_id: int,
        new_status: str,
        changed_by_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Order:
        """Sipariş durumunu günceller"""
        order = Order.objects.get(id=order_id)
        old_status = order.status
        
        order.status = new_status
        order.save()
        
        # Durum geçmişi oluştur
        OrderStatusHistoryService.create_status_change(
            order=order,
            from_status=old_status,
            to_status=new_status,
            changed_by_id=changed_by_id,
            notes=notes
        )
        
        return order
    
    @staticmethod
    def get_season_order_statistics(season_id: int) -> Dict:
        """Sezon sipariş istatistikleri"""
        orders = Order.objects.filter(season_id=season_id)
        
        stats = {
            'total_orders': orders.count(),
            'total_amount': orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00'),
            'total_quantity': 0,
            'total_viol_count': 0,
            'status_breakdown': {},
            'overdue_orders': 0,
            'pending_orders': 0
        }
        
        # Durum bazında sayımlar
        for status_choice in Order.OrderStatus.choices:
            status_code = status_choice[0]
            status_label = status_choice[1]
            count = orders.filter(status=status_code).count()
            stats['status_breakdown'][status_label] = count
        
        # Toplam miktar ve viol sayısı
        order_items = OrderItem.objects.filter(order__season_id=season_id)
        stats['total_quantity'] = order_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
        stats['total_viol_count'] = order_items.aggregate(Sum('viol_count'))['viol_count__sum'] or 0
        
        # Geciken siparişler
        today = timezone.now().date()
        stats['overdue_orders'] = orders.filter(
            requested_delivery_date__lt=today,
            status__in=[Order.OrderStatus.DRAFT, Order.OrderStatus.CONFIRMED, 
                       Order.OrderStatus.WAITING]
        ).count()
        
        # Bekleyen siparişler
        stats['pending_orders'] = orders.filter(
            status__in=[Order.OrderStatus.DRAFT, Order.OrderStatus.CONFIRMED]
        ).count()
        
        return stats
    
    @staticmethod
    def get_customer_orders_in_season(customer_id: int, season_id: int) -> QuerySet[Order]:
        """Belirtilen müşterinin sezonluk siparişleri"""
        return Order.objects.filter(
            customer_id=customer_id,
            season_id=season_id
        ).order_by('-created_at')
    
    @staticmethod
    def calculate_planned_delivery_dates(order_id: int) -> None:
        """Sipariş için planlanan teslimat tarihlerini hesapla"""
        order = Order.objects.get(id=order_id)
        
        # En uzun teslimat süresini bul
        max_delivery_date = None
        for item in order.items.all():
            item_delivery_date = item.planned_delivery_date
            if not max_delivery_date or (item_delivery_date and item_delivery_date > max_delivery_date):
                max_delivery_date = item_delivery_date
        
        # Ana siparişin planlanan teslimat tarihini güncelle (eğer alan varsa)
        # Not: Bu alan models.py'da planned_delivery_date silinmiş, gerekirse ekleyebiliriz


class OrderItemService:
    """Sipariş kalemi yönetimi için servis sınıfı"""
    
    @staticmethod
    def create_order_item(
        order_id: int,
        season_product_id: int,
        stem_type: str,
        viol_type: str,
        quantity: int,
        viol_count: int,
        unit_price: Optional[Decimal] = None,
        **kwargs
    ) -> OrderItem:
        """Yeni sipariş kalemi oluşturur"""
        
        season_product = SeasonProduct.objects.get(id=season_product_id)
        
        # Eğer birim fiyat verilmemişse, season_product'tan otomatik hesapla
        if unit_price is None:
            unit_price = OrderItemService.calculate_unit_price(
                season_product, stem_type, order_id
            )
        
        order_item = OrderItem.objects.create(
            order_id=order_id,
            season_product=season_product,
            variety=season_product.variety,
            rootstock=season_product.rootstock,
            stem_type=stem_type,
            viol_type=viol_type,
            quantity=quantity,
            viol_count=viol_count,
            unit_price=unit_price,
            **kwargs
        )
        
        return order_item
    
    @staticmethod
    def calculate_unit_price(
        season_product: SeasonProduct, 
        stem_type: str, 
        order_id: int
    ) -> Decimal:
        """Teslimat ayına göre birim fiyat hesaplar"""
        try:
            order = Order.objects.get(id=order_id)
            
            # Teslimat tarihini hesapla
            from seasons.services import SeasonProductService
            delivery_date = SeasonProductService.calculate_delivery_date(
                season_product,
                order.order_date.date(),
                stem_type
            )
            
            if not delivery_date:
                return Decimal('0.00')
            
            # Ay farkını hesapla
            order_month = order.order_date.month
            delivery_month = delivery_date.month
            year_diff = delivery_date.year - order.order_date.year
            month_diff = (year_diff * 12) + (delivery_month - order_month) + 1
            
            # 1-18 ay arasında sınırla
            month_diff = max(1, min(18, month_diff))
            
            # Gövde tipine göre fiyat al
            if stem_type == 'single':
                price_field = f'price_single_stem_{month_diff}'
            else:
                price_field = f'price_double_stem_{month_diff}'
            
            return getattr(season_product, price_field, Decimal('0.00'))
            
        except Exception:
            return Decimal('0.00')
    
    @staticmethod
    def bulk_create_order_items(
        order_id: int,
        items_data: List[Dict]
    ) -> List[OrderItem]:
        """Toplu sipariş kalemi oluşturur"""
        order_items = []
        
        with transaction.atomic():
            for item_data in items_data:
                order_item = OrderItemService.create_order_item(
                    order_id=order_id,
                    **item_data
                )
                order_items.append(order_item)
        
        return order_items
    
    @staticmethod
    def get_items_by_order(order_id: int) -> QuerySet[OrderItem]:
        """Sipariş kalemlerini döner"""
        return OrderItem.objects.filter(
            order_id=order_id
        ).select_related('season_product', 'variety', 'rootstock')
    
    @staticmethod
    def get_items_by_variety_in_season(variety_id: int, season_id: int) -> QuerySet[OrderItem]:
        """Belirtilen çeşitin sezonluk sipariş kalemlerini döner"""
        return OrderItem.objects.filter(
            variety_id=variety_id,
            order__season_id=season_id
        ).select_related('order', 'season_product')
    
    @staticmethod
    def update_item_quantity_and_price(
        item_id: int,
        quantity: int,
        unit_price: Optional[Decimal] = None
    ) -> OrderItem:
        """Sipariş kalemi miktarını ve fiyatını günceller"""
        order_item = OrderItem.objects.get(id=item_id)
        
        order_item.quantity = quantity
        if unit_price is not None:
            order_item.unit_price = unit_price
        
        order_item.save()
        return order_item


class OrderStatusHistoryService:
    """Sipariş durum geçmişi yönetimi"""
    
    @staticmethod
    def create_status_change(
        order: Order,
        to_status: str,
        from_status: Optional[str] = None,
        changed_by_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> OrderStatusHistory:
        """Durum değişikliği kaydı oluşturur"""
        return OrderStatusHistory.objects.create(
            order=order,
            from_status=from_status,
            to_status=to_status,
            changed_by_id=changed_by_id,
            notes=notes
        )
    
    @staticmethod
    def get_order_history(order_id: int) -> QuerySet[OrderStatusHistory]:
        """Sipariş durum geçmişini döner"""
        return OrderStatusHistory.objects.filter(
            order_id=order_id
        ).order_by('-changed_at')


class SeasonOrderService:
    """Sezon bazlı sipariş operasyonları"""
    
    @staticmethod
    def get_available_season_products(season_id: int) -> QuerySet[SeasonProduct]:
        """Sezonun sipariş verilebilir ürünleri"""
        return SeasonProduct.objects.filter(
            season_id=season_id,
            is_active=True
        ).select_related('variety', 'rootstock').order_by('variety__species__name', 'variety__name')
    
    @staticmethod
    def get_season_production_summary(season_id: int) -> Dict:
        """Sezon üretim özeti"""
        order_items = OrderItem.objects.filter(order__season_id=season_id)
        
        summary = {
            'total_orders': Order.objects.filter(season_id=season_id).count(),
            'total_items': order_items.count(),
            'total_plants': order_items.aggregate(Sum('quantity'))['quantity__sum'] or 0,
            'total_viols': order_items.aggregate(Sum('viol_count'))['viol_count__sum'] or 0,
            'variety_breakdown': {},
            'stem_type_breakdown': {
                'single': 0,
                'double': 0
            },
            'viol_type_breakdown': {}
        }
        
        # Çeşit bazında breakdown
        varieties = order_items.values('variety__name').annotate(
            total_quantity=Sum('quantity')
        ).order_by('-total_quantity')
        
        for variety in varieties:
            summary['variety_breakdown'][variety['variety__name']] = variety['total_quantity']
        
        # Gövde tipi breakdown
        stem_types = order_items.values('stem_type').annotate(
            total_quantity=Sum('quantity')
        )
        
        for stem_type in stem_types:
            summary['stem_type_breakdown'][stem_type['stem_type']] = stem_type['total_quantity']
        
        # Viol tipi breakdown
        viol_types = order_items.values('viol_type').annotate(
            total_count=Sum('viol_count')
        )
        
        for viol_type in viol_types:
            summary['viol_type_breakdown'][viol_type['viol_type']] = viol_type['total_count']
        
        return summary
