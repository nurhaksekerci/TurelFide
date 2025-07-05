from django.db import models
from django.core.validators import MinValueValidator
from products.models import Variety, Rootstock

# Create your models here.
class Season(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Sezon"
        verbose_name_plural = "Sezonlar"
        ordering = ['start_date']


class SeasonProduct(models.Model):
    """Sezonluk Ürün Modeli - Her sezon için çeşit ve anaç kombinasyonları ile fiyatlandırma"""
    
    season = models.ForeignKey(
        Season, 
        on_delete=models.CASCADE,
        related_name='season_products',
        verbose_name="Sezon"
    )
    variety = models.ForeignKey(
        Variety, 
        on_delete=models.CASCADE,
        related_name='season_products',
        verbose_name="Çeşit"
    )
    rootstock = models.ForeignKey(
        Rootstock,
        on_delete=models.CASCADE,
        related_name='season_products',
        verbose_name="Anaç",
        blank=True,
        null=True,
        help_text="Kullanılacak anaç (opsiyonel)"
    )
    
    # Production Process Durations (in days)
    rootstock_planting_duration = models.PositiveIntegerField(
        verbose_name="Anaç Ekim Süresi (Gün)",
        help_text="Anacın ekilmesi için gereken süre",
        validators=[MinValueValidator(1)],
        default=30
    )
    
    scion_planting_duration = models.PositiveIntegerField(
        verbose_name="Kalem Ekim Süresi (Gün)",
        help_text="Kalemin ekilmesi için gereken süre",
        validators=[MinValueValidator(1)],
        default=45
    )
    
    single_stem_grafting_duration = models.PositiveIntegerField(
        verbose_name="Tek Gövde Aşılama Süresi (Gün)",
        help_text="Tek gövde aşılama için gereken süre",
        validators=[MinValueValidator(1)],
        default=60
    )
    
    double_stem_grafting_duration = models.PositiveIntegerField(
        verbose_name="Çift Gövde Aşılama Süresi (Gün)",
        help_text="Çift gövde aşılama için gereken süre",
        validators=[MinValueValidator(1)],
        default=75
    )
    
    head_formation_duration = models.PositiveIntegerField(
        verbose_name="Kafa Oluşturma Süresi (Gün)",
        help_text="Kafa oluşturma için gereken süre",
        validators=[MinValueValidator(1)],
        default=90
    )
    
    waiting_on_room_duration = models.PositiveIntegerField(
        verbose_name="Oda Bekleme Süresi (Gün)",
        help_text="Oda bekleme süresi",
        validators=[MinValueValidator(1)],
        default=30
    )
    
    price_single_stem_1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_4 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_5 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_6 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_7 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_8 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_9 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_10 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_11 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_12 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_13 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_14 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_15 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_16 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_17 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_single_stem_18 = models.DecimalField(max_digits=10, decimal_places=2, default=0)    
    price_double_stem_1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_4 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_5 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_6 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_7 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_8 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_9 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_10 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_11 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_12 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_13 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_14 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_15 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_16 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_17 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_double_stem_18 = models.DecimalField(max_digits=10, decimal_places=2, default=0)    

    # Additional Information
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif",
        help_text="Bu ürün aktif olarak satılıyor mu?"
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notlar",
        help_text="Ek açıklamalar ve notlar"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )

    def __str__(self):
        rootstock_info = f" ({self.rootstock.name})" if self.rootstock else ""
        return f"{self.season.name} - {self.variety.get_full_name()}{rootstock_info}"
    
    class Meta:
        db_table = 'seasons_seasonproduct'
        verbose_name = "Sezonluk Ürün"
        verbose_name_plural = "Sezonluk Ürünler"
        ordering = ['season__start_date', 'variety__species__name', 'variety__name']
        
        # Unique together - aynı sezonda aynı çeşit-anaç kombinasyonu olamaz
        unique_together = [['season', 'variety', 'rootstock']]
        
        indexes = [
            models.Index(fields=['season', 'variety'], name='season_variety_idx'),
            models.Index(fields=['is_active'], name='seasonproduct_active_idx'),
        ]
    
    @property
    def total_production_duration(self):
        """Toplam üretim süresi (gün)"""
        return (self.rootstock_planting_duration + self.scion_planting_duration + 
                self.single_stem_grafting_duration + self.double_stem_grafting_duration + 
                self.head_formation_duration)

