from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal

from customers.models import Customer
from seasons.models import Season, SeasonProduct
from products.models import Variety, Rootstock
from accounts.models import User


class Order(models.Model):
    """Sipariş Modeli - Ana Sipariş Bilgileri"""
    
    class OrderStatus(models.TextChoices):
        DRAFT = 'draft', 'Taslak'
        CONFIRMED = 'confirmed', 'Onaylandı'
        WAITING = 'waiting', 'Bekliyor'
        AWAITING_SHIPMENT = 'awaiting_shipment', 'Sevkiyat Bekliyor'
        SHIPPED = 'shipped', 'Sevkiyatta'
        DELIVERED = 'delivered', 'Teslim Edildi'
        CANCELLED = 'cancelled', 'İptal Edildi'
    
    class StemType(models.TextChoices):
        SINGLE = 'single', 'Tek Gövde'
        DOUBLE = 'double', 'Çift Gövde'
    
    class ViolType(models.TextChoices):
        V96 = '96', '96'
        V128 = '128', '128'
        V150 = '150', '150'
        V192 = '192', '192'
        V216 = '216', '216'
    
    # Temel Bilgiler
    order_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Sipariş Numarası",
        help_text="Otomatik oluşturulur"
    )
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name="Müşteri"
    )
    
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name="Sezon"
    )
    
    # Tarih Bilgileri
    order_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="Sipariş Tarihi"
    )
    
    requested_delivery_date = models.DateField(
        verbose_name="İstenen Teslimat Tarihi",
        help_text="Müşterinin talep ettiği teslimat tarihi"
    )
    
    actual_shipment_date = models.DateField(
        verbose_name="Fiili Sevk Tarihi",
        help_text="Siparişin gerçekte sevk edildiği tarih",
        blank=True,
        null=True
    )
    
    actual_delivery_date = models.DateField(
        verbose_name="Fiili Teslimat Tarihi",
        help_text="Siparişin müşteriye teslim edildiği tarih",
        blank=True,
        null=True
    )
    
    # Durum ve Notlar
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT,
        verbose_name="Durum"
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notlar",
        help_text="Sipariş ile ilgili özel notlar"
    )
    
    internal_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="İç Notlar",
        help_text="Müşteriye gösterilmeyen dahili notlar"
    )
    
    # Özel Talepler
    special_packaging = models.BooleanField(
        default=False,
        verbose_name="Özel Ambalaj",
        help_text="Özel ambalaj gerekli mi?"
    )
    
    urgent = models.BooleanField(
        default=False,
        verbose_name="Acil",
        help_text="Acil sipariş mi?"
    )
    
    # Fiyat Özeti (OrderItem'lardan hesaplanacak)
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Toplam Tutar (TL)",
        help_text="Tüm kalemlerin toplam tutarı"
    )
    
    # Audit Fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='created_orders',
        verbose_name="Oluşturan",
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        # Sipariş numarası otomatik oluştur
        if not self.order_number:
            self.order_number = self.generate_order_number()
        
        super().save(*args, **kwargs)
        
        # Toplam tutarı hesapla
        self.calculate_total_amount()
    
    def generate_order_number(self):
        """Sipariş numarası oluşturur: ORD-2024-001"""
        year = timezone.now().year
        last_order = Order.objects.filter(
            order_number__startswith=f'ORD-{year}-'
        ).order_by('order_number').last()
        
        if last_order:
            last_number = int(last_order.order_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'ORD-{year}-{new_number:03d}'
    
    def get_status_display(self):
        """Durumun görüntüleme adını döndürür"""
        return self.OrderStatus(self.status).label
    
    def calculate_total_amount(self):
        """Toplam tutarı hesapla"""
        total = sum(item.total_price for item in self.items.all())
        if self.total_amount != total:
            self.total_amount = total
            Order.objects.filter(pk=self.pk).update(total_amount=total)
    
    def calculate_planned_delivery_date(self):
        """Planlanan teslimat tarihini hesapla (en uzun üretim süresi)"""
        if not self.items.exists():
            return None
        
        max_delivery_date = None
        for item in self.items.all():
            if item.season_product:
                from seasons.services import SeasonProductService
                item_delivery_date = SeasonProductService.calculate_delivery_date(
                    item.season_product,
                    self.order_date.date(),
                    item.stem_type
                )
                if not max_delivery_date or item_delivery_date > max_delivery_date:
                    max_delivery_date = item_delivery_date
        
        return max_delivery_date
    
    @property
    def planned_delivery_date(self):
        """Planlanan teslimat tarihi"""
        return self.calculate_planned_delivery_date()
    
    @property
    def is_overdue(self):
        """Teslimat tarihi geçmiş mi?"""
        planned_date = self.planned_delivery_date
        if planned_date:
            return timezone.now().date() > planned_date
        return False
    
    @property
    def days_until_delivery(self):
        """Teslimat tarihine kaç gün kaldı?"""
        planned_date = self.planned_delivery_date
        if planned_date:
            delta = planned_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def total_quantity(self):
        """Toplam fide adedi"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_viol_count(self):
        """Toplam viol adedi"""
        return sum(item.viol_count for item in self.items.all())
    
    @property
    def production_status(self):
        """Üretim durumu yüzdesi"""
        if self.status == self.OrderStatus.DRAFT:
            return 0
        elif self.status == self.OrderStatus.CONFIRMED:
            return 25
        elif self.status == self.OrderStatus.WAITING:
            return 50
        elif self.status == self.OrderStatus.AWAITING_SHIPMENT:
            return 90
        elif self.status == self.OrderStatus.SHIPPED:
            return 95
        elif self.status == self.OrderStatus.DELIVERED:
            return 100
        elif self.status == self.OrderStatus.CANCELLED:
            return 0
        return 0
    
    def __str__(self):
        return f"{self.order_number} - {self.customer.first_name} {self.customer.last_name}"
    
    class Meta:
        db_table = 'orders_order'
        verbose_name = "Sipariş"
        verbose_name_plural = "Siparişler"
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['customer', 'season'], name='order_customer_season_idx'),
            models.Index(fields=['status'], name='order_status_idx'),
            models.Index(fields=['order_date'], name='order_date_idx'),
            models.Index(fields=['requested_delivery_date'], name='order_requested_delivery_idx'),
        ]


class OrderItem(models.Model):
    """Sipariş Kalemi - Her Ürün için Ayrı Kayıt"""
    
    class OrderItemStatus(models.TextChoices):
        WAITING = 'waiting', 'Bekliyor'
        ROOTSTOCK_PLANTING_SENT = 'rootstock_planting_sent', 'Anaç Gönderildi'
        ROOTSTOCK_PLANTING_CONFIRMED = 'rootstock_planting_confirmed', 'Anaç Onaylandı'
        ROOTSTOCK_PLANTING_PLANTED = 'rootstock_planting_planted', 'Anaç Ekildi'
        SCION_PLANTING_SENT = 'scion_planting_sent', 'Kalem Gönderildi'
        SCION_PLANTING_CONFIRMED = 'scion_planting_confirmed', 'Kalem Onaylandı'
        SCION_PLANTING_PLANTED = 'scion_planting_planted', 'Kalem Ekildi'
        GRAFTING_SENT = 'grafting_sent', 'Aşıya Gönderildi'
        GRAFTING_CONFIRMED = 'grafting_confirmed', 'Aşı Onaylandı'
        GRAFTING_PLANTED = 'grafting_planted', 'Aşı Ekildi'
        HEAD_FORMATION_SENT = 'head_formation_sent', 'Kafa Kesime Gönderildi'
        HEAD_FORMATION_CONFIRMED = 'head_formation_confirmed', 'Kafa Kesime Onaylandı'
        HEAD_FORMATION_FORMED = 'head_formation_formed', 'Kafa Kesime Ekildi'
        CUTTING_SENT = 'cutting_sent', 'Bekleme Odasına Gönderildi'
        CUTTING_CONFIRMED = 'cutting_confirmed', 'Bekleme Odasına Onaylandı'
        CUTTING_CUT = 'cutting_cut', 'Bekleme Odasında'
        READY_FOR_SHIPMENT = 'ready_for_shipment', 'Sevkiyata Hazır'
    class StemType(models.TextChoices):
        SINGLE = 'single', 'Tek Gövde'
        DOUBLE = 'double', 'Çift Gövde'
    
    class ViolType(models.TextChoices):
        V96 = '96', '96'
        V128 = '128', '128'
        V150 = '150', '150'
        V192 = '192', '192'
        V216 = '216', '216'
    
    # Bağlantılar
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Sipariş"
    )
    
    season_product = models.ForeignKey(
        SeasonProduct,
        on_delete=models.CASCADE,
        related_name='order_items',
        verbose_name="Sezonluk Ürün",
        help_text="Çeşit, anaç ve sezon kombinasyonu"
    )
    
    variety = models.ForeignKey(
        Variety,
        on_delete=models.CASCADE,
        related_name='order_items',
        verbose_name="Çeşit"
    )
    
    rootstock = models.ForeignKey(
        Rootstock,
        on_delete=models.CASCADE,
        related_name='order_items',
        verbose_name="Anaç",
        blank=True,
        null=True,
        help_text="Anaçsız ürünler için boş bırakılabilir"
    )
    
    # Ürün Detayları
    stem_type = models.CharField(
        max_length=10,
        choices=StemType.choices,
        default=StemType.SINGLE,
        verbose_name="Gövde Tipi"
    )
    
    viol_type = models.CharField(
        max_length=15,
        choices=ViolType.choices,
        default=ViolType.V128,
        verbose_name="Viol Tipi"
    )
    
    quantity = models.PositiveIntegerField(
        verbose_name="Miktar (Adet)",
        help_text="Bu kalem için fide adedi",
        validators=[MinValueValidator(1)]
    )
    
    viol_count = models.PositiveIntegerField(
        verbose_name="Viol Adedi",
        help_text="Bu kalem için viol adedi",
        validators=[MinValueValidator(1)]
    )
    
    # Fiyat Bilgileri
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Birim Fiyat (TL)",
        help_text="Tek fide için fiyat",
        default=Decimal('0.00')
    )
    
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Toplam Fiyat (TL)",
        help_text="Miktar × Birim Fiyat",
        default=Decimal('0.00')
    )
    
    # Notlar
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Kalem Notları",
        help_text="Bu kalem için özel notlar"
    )
    
    # Audit Fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    status = models.CharField(
        max_length=30,
        choices=OrderItemStatus.choices,
        default=OrderItemStatus.WAITING,
        verbose_name="Durum"
    )

    def save(self, *args, **kwargs):
        # Toplam fiyatı hesapla
        self.total_price = self.unit_price * self.quantity
        
        # Variety ve rootstock bilgilerini season_product'tan al
        if self.season_product:
            self.variety = self.season_product.variety
            self.rootstock = self.season_product.rootstock
        
        super().save(*args, **kwargs)
        
        # Ana siparişin toplam tutarını güncelle
        self.order.calculate_total_amount()
    
    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        # Silindikten sonra ana siparişin toplam tutarını güncelle
        order.calculate_total_amount()
    
    @property
    def planned_delivery_date(self):
        """Bu kalem için planlanan teslimat tarihi"""
        if self.season_product:
            from seasons.services import SeasonProductService
            return SeasonProductService.calculate_delivery_date(
                self.season_product,
                self.order.order_date.date(),
                self.stem_type
            )
        return None
    
    @property
    def unit_price_for_month(self):
        """Teslimat ayına göre birim fiyat (seasons modelindeki 18 aylık fiyattan)"""
        if not self.season_product or not self.planned_delivery_date:
            return Decimal('0.00')
        
        # Sipariş tarihi ile teslimat tarihi arasındaki ay farkı
        order_month = self.order.order_date.month
        delivery_month = self.planned_delivery_date.month
        
        # Yıl farkını da hesaba kat
        year_diff = self.planned_delivery_date.year - self.order.order_date.year
        month_diff = (year_diff * 12) + (delivery_month - order_month) + 1
        
        # 1-18 ay arasında sınırla
        month_diff = max(1, min(18, month_diff))
        
        # SeasonProduct'tan ilgili ayın fiyatını al
        if self.stem_type == self.StemType.SINGLE:
            price_field = f'price_single_stem_{month_diff}'
        else:
            price_field = f'price_double_stem_{month_diff}'
        
        return getattr(self.season_product, price_field, Decimal('0.00'))
    
    @property
    def rootstock_planting_date(self):
        """Anaç ekim tarihi - teslimat tarihinden geriye doğru hesaplanan"""
        if not self.season_product:
            return None
        
        # Teslimat tarihi
        delivery_date = self.order.requested_delivery_date
        if not delivery_date:
            return None
        
        from datetime import timedelta
        
        # Toplam süre hesaplama
        total_days = (
            self.season_product.waiting_on_room_duration +
            self.season_product.head_formation_duration +
            self.season_product.scion_planting_duration
        )
        
        # Gövde tipine göre aşılama süresi
        if self.stem_type == self.StemType.SINGLE:
            total_days += self.season_product.single_stem_grafting_duration
        else:
            total_days += self.season_product.double_stem_grafting_duration
        
        return delivery_date - timedelta(days=total_days)
    
    @property
    def scion_planting_date(self):
        """Kalem ekim tarihi"""
        if not self.season_product:
            return None
        
        delivery_date = self.order.requested_delivery_date
        if not delivery_date:
            return None
        
        from datetime import timedelta
        
        total_days = (
            self.season_product.waiting_on_room_duration +
            self.season_product.head_formation_duration +
            self.season_product.scion_planting_duration
        )
        
        # Gövde tipine göre aşılama süresi
        if self.stem_type == self.StemType.SINGLE:
            total_days += self.season_product.single_stem_grafting_duration
        else:
            total_days += self.season_product.double_stem_grafting_duration
        
        # Anaç ekim süresini çıkar
        total_days -= self.season_product.rootstock_planting_duration
        
        return delivery_date - timedelta(days=total_days)
    
    @property
    def grafting_date(self):
        """Aşılama tarihi"""
        if not self.season_product:
            return None
        
        delivery_date = self.order.requested_delivery_date
        if not delivery_date:
            return None
        
        from datetime import timedelta
        
        total_days = (
            self.season_product.waiting_on_room_duration +
            self.season_product.head_formation_duration
        )
        
        # Gövde tipine göre aşılama süresi
        if self.stem_type == self.StemType.SINGLE:
            total_days += self.season_product.single_stem_grafting_duration
        else:
            total_days += self.season_product.double_stem_grafting_duration
        
        return delivery_date - timedelta(days=total_days)
    
    @property
    def head_formation_date(self):
        """Kafa kesimi/oluşturma tarihi"""
        if not self.season_product:
            return None
        
        delivery_date = self.order.requested_delivery_date
        if not delivery_date:
            return None
        
        from datetime import timedelta
        
        total_days = (
            self.season_product.waiting_on_room_duration +
            self.season_product.head_formation_duration
        )
        
        return delivery_date - timedelta(days=total_days)
    
    def __str__(self):
        return f"{self.order.order_number} - {self.variety.get_full_name()} ({self.quantity} adet)"
    
    class Meta:
        db_table = 'orders_orderitem'
        verbose_name = "Sipariş Kalemi"
        verbose_name_plural = "Sipariş Kalemleri"
        ordering = ['order', 'created_at']
        
        indexes = [
            models.Index(fields=['order'], name='orderitem_order_idx'),
            models.Index(fields=['season_product'], name='orderitem_seasonproduct_idx'),
            models.Index(fields=['variety'], name='orderitem_variety_idx'),
        ]


class OrderStatusHistory(models.Model):
    """Sipariş Durum Geçmişi"""
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name="Sipariş"
    )
    
    from_status = models.CharField(
        max_length=20,
        choices=Order.OrderStatus.choices,
        verbose_name="Önceki Durum",
        blank=True,
        null=True
    )
    
    to_status = models.CharField(
        max_length=20,
        choices=Order.OrderStatus.choices,
        verbose_name="Yeni Durum"
    )
    
    changed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Değişim Tarihi"
    )
    
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        verbose_name="Değiştiren",
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notlar"
    )
    
    def __str__(self):
        return f"{self.order.order_number}: {self.from_status} → {self.to_status}"
    
    class Meta:
        db_table = 'orders_orderstatushistory'
        verbose_name = "Sipariş Durum Geçmişi"
        verbose_name_plural = "Sipariş Durum Geçmişleri"
        ordering = ['-changed_at']


class PlantingRequest(models.Model):
    """Ekim Talep Kartı - Aynı tarihte aynı tür/çeşit için ekim talebi"""
    
    class PlantingType(models.TextChoices):
        ROOTSTOCK = 'rootstock', 'Anaç Ekimi'
        SCION = 'scion', 'Kalem Ekimi'
    
    class RequestStatus(models.TextChoices):
        PENDING = 'pending', 'Bekliyor'
        SENT = 'sent', 'Ekime Gönderildi'
        CONFIRMED = 'confirmed', 'Ekim Onaylandı'
        PLANTED = 'planted', 'Ekildi'
        COMPLETED = 'completed', 'Tamamlandı'
        CANCELLED = 'cancelled', 'İptal Edildi'
    
    # Temel Bilgiler
    request_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Talep Numarası",
        help_text="Otomatik oluşturulur"
    )
    
    planting_type = models.CharField(
        max_length=10,
        choices=PlantingType.choices,
        verbose_name="Ekim Türü",
        help_text="Anaç mı kalem ekimi mi?"
    )
    
    variety = models.ForeignKey(
        'products.Variety',
        on_delete=models.CASCADE,
        verbose_name="Çeşit",
        blank=True,
        null=True,
        help_text="Ana çeşit (birden fazla çeşit olabilir)"
    )
    
    rootstock = models.ForeignKey(
        'products.Rootstock',
        on_delete=models.CASCADE,
        verbose_name="Anaç",
        blank=True,
        null=True,
        help_text="Anaçsız ürünler için boş"
    )
    
    # İlişkiler
    order_items = models.ManyToManyField(
        OrderItem,
        related_name='planting_requests',
        verbose_name="Sipariş Kalemleri",
        help_text="Bu talebe dahil sipariş kalemleri"
    )
    
    season = models.ForeignKey(
        'seasons.Season',
        on_delete=models.CASCADE,
        related_name='planting_requests',
        verbose_name="Sezon"
    )
    
    # Tarih Bilgileri
    requested_planting_date = models.DateField(
        verbose_name="Talep Edilen Ekim Tarihi",
        help_text="Bu tarihte ekim yapılması isteniyor"
    )
    
    sent_to_planting_date = models.DateTimeField(
        verbose_name="Ekime Gönderilme Tarihi",
        blank=True,
        null=True,
        help_text="Ekim bölümüne gönderildiği tarih"
    )
    
    confirmed_date = models.DateTimeField(
        verbose_name="Onaylanma Tarihi",
        blank=True,
        null=True,
        help_text="Ekim bölümü tarafından onaylandığı tarih"
    )
    
    actual_planting_date = models.DateField(
        verbose_name="Gerçek Ekim Tarihi",
        blank=True,
        null=True,
        help_text="Fiili olarak ekildiği tarih"
    )
    
    completion_date = models.DateTimeField(
        verbose_name="Tamamlanma Tarihi",
        blank=True,
        null=True,
        help_text="İşlemin tamamlandığı tarih"
    )
    
    # Durum ve Lokasyon
    status = models.CharField(
        max_length=15,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        verbose_name="Durum"
    )
    
    planting_location = models.CharField(
        max_length=100,
        verbose_name="Ekim Lokasyonu",
        blank=True,
        null=True,
        help_text="Hangi sera, blok, sıra vs."
    )
    
    planting_area = models.CharField(
        max_length=50,
        verbose_name="Ekim Alanı",
        blank=True,
        null=True,
        help_text="A Serası, B Bloku vs."
    )
    
    # Miktar Bilgileri
    total_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Toplam Miktar",
        help_text="Bu talepteki toplam fide sayısı"
    )
    
    total_viol_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Toplam Viol Sayısı",
        help_text="Bu talepteki toplam viol sayısı"
    )
    
    planting_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Ekim Adedi",
        help_text="Gerçekte ekilecek fide sayısı (kullanıcı girer)"
    )
    
    # Notlar
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notlar",
        help_text="Ekim talebi ile ilgili notlar"
    )
    
    internal_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="İç Notlar",
        help_text="Dahili kullanım için notlar"
    )
    
    # Audit Fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='created_planting_requests',
        verbose_name="Oluşturan",
        null=True,
        blank=True
    )
    
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='confirmed_planting_requests',
        verbose_name="Onaylayan",
        null=True,
        blank=True
    )
    
    planted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='planted_requests',
        verbose_name="Eken Kişi",
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        # Talep numarası otomatik oluştur
        if not self.request_number:
            self.request_number = self.generate_request_number()
        
        super().save(*args, **kwargs)
        
        # Toplam miktarları hesapla
        self.calculate_totals()
    
    def generate_request_number(self):
        """Talep numarası oluşturur: PLT-2024-001"""
        year = timezone.now().year
        last_request = PlantingRequest.objects.filter(
            request_number__startswith=f'PLT-{year}-'
        ).order_by('request_number').last()
        
        if last_request:
            last_number = int(last_request.request_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'PLT-{year}-{new_number:03d}'
    
    def calculate_totals(self):
        """Toplam miktarları hesapla"""
        if self.pk:  # Nesne kaydedildiyse
            total_qty = sum(item.quantity for item in self.order_items.all())
            total_viol = sum(item.viol_count for item in self.order_items.all())
            
            if self.total_quantity != total_qty or self.total_viol_count != total_viol:
                PlantingRequest.objects.filter(pk=self.pk).update(
                    total_quantity=total_qty,
                    total_viol_count=total_viol
                )
    
    def get_orders(self):
        """Bu talebe dahil olan siparişleri döndürür"""
        return Order.objects.filter(
            items__planting_requests=self
        ).distinct()
    
    def get_customers(self):
        """Bu talebe dahil olan müşterileri döndürür"""
        return Customer.objects.filter(
            orders__items__planting_requests=self
        ).distinct()
    
    @property
    def product_display(self):
        """Ürün görüntü adı"""
        if self.pk:
            # OrderItem'lardan çeşitleri al
            varieties = self.order_items.values_list('variety__name', flat=True).distinct()
            if varieties:
                varieties_str = ', '.join(filter(None, varieties))
                if self.rootstock:
                    return f"{varieties_str} ({self.rootstock.name})"
                return f"{varieties_str} (Anaçsız)"
        
        # Fallback - tek çeşit varsa
        if self.variety:
            if self.rootstock:
                return f"{self.variety.get_full_name()} ({self.rootstock.name})"
            return f"{self.variety.get_full_name()} (Anaçsız)"
        
        # Sadece anaç bilgisi
        if self.rootstock:
            return f"Çoklu Çeşit ({self.rootstock.name})"
        return "Anaçsız Ürünler"
    
    @property
    def days_until_planting(self):
        """Ekim tarihine kaç gün kaldı?"""
        if self.requested_planting_date:
            delta = self.requested_planting_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def is_overdue(self):
        """Ekim tarihi geçmiş mi?"""
        if self.requested_planting_date and self.status not in ['planted', 'completed']:
            return timezone.now().date() > self.requested_planting_date
        return False
    
    @property
    def order_count(self):
        """Kaç farklı sipariş var?"""
        return self.get_orders().count()
    
    @property
    def customer_count(self):
        """Kaç farklı müşteri var?"""
        return self.get_customers().count()
    
    def can_send_to_planting(self):
        """Ekime gönderilebilir mi?"""
        return self.status == self.RequestStatus.PENDING
    
    def can_confirm(self):
        """Onaylanabilir mi?"""
        return self.status == self.RequestStatus.SENT
    
    def can_plant(self):
        """Ekilebilir mi?"""
        return self.status == self.RequestStatus.CONFIRMED
    
    def send_to_planting(self, user=None):
        """Ekime gönder"""
        if self.can_send_to_planting():
            self.status = self.RequestStatus.SENT
            self.sent_to_planting_date = timezone.now()
            if user:
                self.created_by = user
            self.save()
            return True
        return False
    
    def confirm_planting(self, user=None):
        """Ekimi onayla"""
        if self.can_confirm():
            self.status = self.RequestStatus.CONFIRMED
            self.confirmed_date = timezone.now()
            if user:
                self.confirmed_by = user
            self.save()
            return True
        return False
    
    def mark_as_planted(self, actual_date=None, location=None, area=None, user=None):
        """Ekildi olarak işaretle"""
        if self.can_plant():
            self.status = self.RequestStatus.PLANTED
            self.actual_planting_date = actual_date or timezone.now().date()
            if location:
                self.planting_location = location
            if area:
                self.planting_area = area
            if user:
                self.planted_by = user
            self.save()
            return True
        return False
    
    def __str__(self):
        return f"{self.request_number} - {self.product_display} ({self.get_planting_type_display()})"
    
    class Meta:
        db_table = 'orders_plantingrequest'
        verbose_name = "Ekim Talep Kartı"
        verbose_name_plural = "Ekim Talep Kartları"
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['rootstock', 'planting_type'], name='planting_rootstock_type_idx'),
            models.Index(fields=['status'], name='planting_status_idx'),
            models.Index(fields=['requested_planting_date'], name='planting_date_idx'),
            models.Index(fields=['planting_area'], name='planting_area_idx'),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['rootstock', 'planting_type', 'requested_planting_date', 'season'],
                name='unique_planting_request'
            )
        ]


class PlantingRequestHistory(models.Model):
    """Ekim Talep Kartı Durum Geçmişi"""
    
    planting_request = models.ForeignKey(
        PlantingRequest,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name="Ekim Talebi"
    )
    
    from_status = models.CharField(
        max_length=15,
        choices=PlantingRequest.RequestStatus.choices,
        verbose_name="Önceki Durum",
        blank=True,
        null=True
    )
    
    to_status = models.CharField(
        max_length=15,
        choices=PlantingRequest.RequestStatus.choices,
        verbose_name="Yeni Durum"
    )
    
    changed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Değişim Tarihi"
    )
    
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        verbose_name="Değiştiren",
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notlar"
    )
    
    location_info = models.CharField(
        max_length=200,
        verbose_name="Lokasyon Bilgisi",
        blank=True,
        null=True,
        help_text="Değişiklik sırasındaki lokasyon bilgisi"
    )
    
    def __str__(self):
        return f"{self.planting_request.request_number}: {self.from_status} → {self.to_status}"
    
    class Meta:
        db_table = 'orders_plantingrequesthistory'
        verbose_name = "Ekim Talep Geçmişi"
        verbose_name_plural = "Ekim Talep Geçmişleri"
        ordering = ['-changed_at']


