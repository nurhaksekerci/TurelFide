from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, datetime, timedelta
import csv
from io import StringIO

from .models import Order, OrderItem
from seasons.models import Season


def validate_order_data(order_data: Dict) -> Dict:
    """Sipariş verilerini doğrular"""
    errors = {}
    
    # Müşteri kontrolü
    if not order_data.get('customer_id'):
        errors['customer'] = 'Müşteri seçimi zorunludur.'
    
    # Sezon kontrolü
    if not order_data.get('season_id'):
        errors['season'] = 'Sezon seçimi zorunludur.'
    
    # Teslimat tarihi kontrolü
    requested_date = order_data.get('requested_delivery_date')
    if not requested_date:
        errors['requested_delivery_date'] = 'Teslimat tarihi zorunludur.'
    elif isinstance(requested_date, str):
        try:
            requested_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
        except ValueError:
            errors['requested_delivery_date'] = 'Geçersiz tarih formatı.'
    
    if requested_date and requested_date <= timezone.now().date():
        errors['requested_delivery_date'] = 'Teslimat tarihi bugünden sonra olmalıdır.'
    
    return errors


def validate_order_item_data(item_data: Dict) -> Dict:
    """Sipariş kalemi verilerini doğrular"""
    errors = {}
    
    # SeasonProduct kontrolü
    if not item_data.get('season_product_id'):
        errors['season_product'] = 'Ürün seçimi zorunludur.'
    
    # Miktar kontrolü
    quantity = item_data.get('quantity', 0)
    if not quantity or quantity <= 0:
        errors['quantity'] = 'Miktar 0\'dan büyük olmalıdır.'
    elif quantity > 100000:  # Maksimum miktar kontrolü
        errors['quantity'] = 'Miktar çok yüksek.'
    
    # Viol sayısı kontrolü
    viol_count = item_data.get('viol_count', 0)
    if not viol_count or viol_count <= 0:
        errors['viol_count'] = 'Viol sayısı 0\'dan büyük olmalıdır.'
    elif viol_count > 1000:  # Maksimum viol kontrolü
        errors['viol_count'] = 'Viol sayısı çok yüksek.'
    
    # Viol başına fide sayısı kontrolü
    if quantity and viol_count:
        plants_per_viol = quantity / viol_count
        if plants_per_viol < 1:
            errors['viol_count'] = 'Viol sayısı fide sayısından fazla olamaz.'
        elif plants_per_viol > 500:  # Viol başına maksimum fide
            errors['viol_count'] = 'Viol başına çok fazla fide.'
    
    # Birim fiyat kontrolü (opsiyonel)
    unit_price = item_data.get('unit_price')
    if unit_price is not None:
        try:
            unit_price = Decimal(str(unit_price))
            if unit_price < 0:
                errors['unit_price'] = 'Birim fiyat negatif olamaz.'
            elif unit_price > 1000:  # Maksimum birim fiyat
                errors['unit_price'] = 'Birim fiyat çok yüksek.'
        except (ValueError, TypeError):
            errors['unit_price'] = 'Geçersiz fiyat formatı.'
    
    return errors


def format_order_number(order: Order) -> str:
    """Sipariş numarasını formatlar"""
    return f"{order.order_number}"


def get_order_status_color(status: str) -> str:
    """Sipariş durumuna göre renk kodu döner"""
    status_colors = {
        'draft': 'secondary',
        'confirmed': 'primary',
        'waiting': 'info',
        'awaiting_shipment': 'success',
        'shipped': 'success',
        'delivered': 'success',
        'cancelled': 'danger'
    }
    return status_colors.get(status, 'secondary')


def get_order_status_icon(status: str) -> str:
    """Sipariş durumuna göre ikon döner"""
    status_icons = {
        'draft': 'fas fa-edit',
        'confirmed': 'fas fa-check',
        'waiting': 'fas fa-clock',
        'awaiting_shipment': 'fas fa-box',
        'shipped': 'fas fa-truck',
        'delivered': 'fas fa-check-circle',
        'cancelled': 'fas fa-times-circle'
    }
    return status_icons.get(status, 'fas fa-question')


def calculate_delivery_urgency(order: Order) -> Tuple[str, str]:
    """Teslimat aciliyetini hesaplar"""
    if not order.requested_delivery_date:
        return 'unknown', 'Tarih Yok'
    
    today = timezone.now().date()
    days_remaining = (order.requested_delivery_date - today).days
    
    if days_remaining < 0:
        return 'overdue', f'{abs(days_remaining)} gün gecikmiş'
    elif days_remaining == 0:
        return 'today', 'Bugün'
    elif days_remaining <= 7:
        return 'urgent', f'{days_remaining} gün kaldı'
    elif days_remaining <= 30:
        return 'soon', f'{days_remaining} gün kaldı'
    else:
        return 'normal', f'{days_remaining} gün kaldı'


def get_urgency_color(urgency: str) -> str:
    """Aciliyet durumuna göre renk döner"""
    urgency_colors = {
        'overdue': 'danger',
        'today': 'danger',
        'urgent': 'warning',
        'soon': 'info',
        'normal': 'success',
        'unknown': 'secondary'
    }
    return urgency_colors.get(urgency, 'secondary')


def format_currency(amount: Decimal) -> str:
    """Para birimini formatlar"""
    if amount is None:
        return '0,00 TL'
    return f'{amount:,.2f} TL'.replace(',', 'X').replace('.', ',').replace('X', '.')


def export_orders_to_csv(orders: List[Order]) -> str:
    """Siparişleri CSV formatında export eder"""
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Sipariş No', 'Müşteri', 'Sezon', 'Durum', 'Sipariş Tarihi',
        'İstenen Teslimat', 'Toplam Tutar', 'Toplam Miktar', 'Viol Sayısı'
    ])
    
    # Data rows
    for order in orders:
        writer.writerow([
            order.order_number,
            order.customer.company_name,
            order.season.name,
            order.get_status_display(),
            order.order_date.strftime('%d.%m.%Y'),
            order.requested_delivery_date.strftime('%d.%m.%Y') if order.requested_delivery_date else '',
            format_currency(order.total_amount),
            order.total_quantity,
            order.total_viol_count
        ])
    
    return output.getvalue()


def export_order_items_to_csv(order_items: List[OrderItem]) -> str:
    """Sipariş kalemlerini CSV formatında export eder"""
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Sipariş No', 'Çeşit', 'Anaç', 'Gövde Tipi', 'Viol Tipi',
        'Miktar', 'Viol Sayısı', 'Birim Fiyat', 'Toplam Fiyat'
    ])
    
    # Data rows
    for item in order_items:
        writer.writerow([
            item.order.order_number,
            item.variety.get_full_name(),
            item.rootstock.name if item.rootstock else 'Anaçsız',
            item.get_stem_type_display(),
            item.viol_type,
            item.quantity,
            item.viol_count,
            format_currency(item.unit_price),
            format_currency(item.total_price)
        ])
    
    return output.getvalue()


def get_season_order_fields_mapping() -> Dict[str, str]:
    """Sipariş form alanları mapping"""
    return {
        'customer': 'Müşteri',
        'requested_delivery_date': 'İstenen Teslimat Tarihi',
        'notes': 'Notlar',
        'internal_notes': 'İç Notlar',
        'special_packaging': 'Özel Ambalaj',
        'urgent': 'Acil Sipariş'
    }


def get_order_item_fields_mapping() -> Dict[str, str]:
    """Sipariş kalemi form alanları mapping"""
    return {
        'season_product': 'Ürün',
        'stem_type': 'Gövde Tipi',
        'viol_type': 'Viol Tipi',
        'quantity': 'Miktar',
        'viol_count': 'Viol Sayısı',
        'unit_price': 'Birim Fiyat',
        'notes': 'Notlar'
    }


def calculate_season_order_totals(season_id: int) -> Dict:
    """Sezon sipariş toplamlarını hesaplar"""
    from .services import OrderService
    
    orders = OrderService.get_orders_by_season(season_id)
    
    totals = {
        'total_orders': orders.count(),
        'total_amount': sum(order.total_amount for order in orders),
        'total_quantity': sum(order.total_quantity for order in orders),
        'total_viol_count': sum(order.total_viol_count for order in orders),
        'average_order_value': Decimal('0.00')
    }
    
    if totals['total_orders'] > 0:
        totals['average_order_value'] = totals['total_amount'] / totals['total_orders']
    
    return totals


def get_next_production_stage(current_status: str) -> Optional[str]:
    """Sonraki üretim aşamasını döner"""
    stage_progression = [
        'draft', 'confirmed', 'waiting', 'awaiting_shipment',
        'shipped', 'delivered'
    ]
    
    try:
        current_index = stage_progression.index(current_status)
        if current_index < len(stage_progression) - 1:
            return stage_progression[current_index + 1]
    except ValueError:
        pass
    
    return None


def can_advance_to_next_stage(order: Order) -> bool:
    """Siparişin bir sonraki aşamaya geçip geçemeyeceğini kontrol eder"""
    if order.status == Order.OrderStatus.DRAFT:
        return True  # Taslaktan onaya geçebilir
    elif order.status == Order.OrderStatus.CONFIRMED:
        return True  # Onaydan bekleme aşamasına geçebilir
    elif order.status == Order.OrderStatus.WAITING:
        return True  # Beklemeden üretime geçebilir
    else:
        return False  # Diğer durumlar daha kompleks kontroller gerektirir


def calculate_planting_date_urgency(planting_date: date, order_status: str) -> Tuple[str, str]:
    """Ekim tarihi aciliyetini hesaplar (sadece belirli durumlarda)"""
    # Sadece Taslak, Onaylandı veya Bekliyor durumlarında renklendirme yap
    allowed_statuses = ['draft', 'confirmed', 'waiting']
    if order_status not in allowed_statuses:
        return 'normal', ''
        
    if not planting_date:
        return 'normal', ''
    
    today = timezone.now().date()
    days_remaining = (planting_date - today).days
    
    if days_remaining < 0:
        return 'overdue', 'Gecikmiş'  # Kırmızı
    elif days_remaining <= 7:
        return 'urgent', 'Yaklaşıyor'   # Sarı
    elif days_remaining <= 14:
        return 'ready', 'Zamanı Geldi'  # Yeşil
    else:
        return 'normal', 'Vakit Var'    # Renk yok


def get_planting_date_bg_color(urgency: str) -> str:
    """Ekim tarihi aciliyetine göre background rengi döner"""
    urgency_colors = {
        'overdue': 'table-danger',    # Kırmızı
        'urgent': 'table-warning',    # Sarı
        'ready': 'table-success',     # Yeşil
        'normal': ''                  # Renk yok
    }
    return urgency_colors.get(urgency, '')
