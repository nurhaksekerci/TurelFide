from django.db import models
from django.core.validators import MinLengthValidator
from django.utils import timezone

# Create your models here.

class Species(models.Model):
    """Tür modeli - Meyve/sebze türlerini tanımlar (Elma, Armut, Kiraz vb.)"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        validators=[MinLengthValidator(2)],
        verbose_name="Tür Adı",
        help_text="Örnek: Domates, Aşılı Domates, Biber, Patlıcan"
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Aktif",
        help_text="Bu tür aktif olarak kullanılıyor mu?"
    )
    
    # Zaman damgaları
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    class Meta:
        db_table = 'products_species'
        verbose_name = "Tür"
        verbose_name_plural = "Türler"
        ordering = ['name']
        
        indexes = [
            models.Index(fields=['name'], name='species_name_idx'),
            models.Index(fields=['is_active'], name='species_active_idx'),
        ]

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f"<Species: {self.name}>"
    
    @property
    def active_varieties_count(self):
        """Bu türe ait aktif çeşit sayısı"""
        return self.varieties.filter(is_active=True).count()
    
    @property
    def active_rootstocks_count(self):
        """Bu türe ait aktif anaç sayısı"""
        return self.rootstocks.filter(is_active=True).count()


class SeedBrand(models.Model):
    """Tohum Markası modeli - Tohum markalarını tanımlar (Kurumsal, Türkiye, İtalya, Almanya, vb.)"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        validators=[MinLengthValidator(2)],
        verbose_name="Marka Adı",
        help_text="Örnek: Kurumsal, Türkiye, İtalya, Almanya"
    )
    
    price_per_packet = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Tohum Paket Fiyatı",
        help_text="Tohum paket fiyatı (TL)"
    )
    
    seeds_per_packet = models.PositiveIntegerField(
        verbose_name="Paket Başına Tohum Sayısı",
        help_text="Bir pakette kaç adet tohum var"
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Aktif",
        help_text="Bu marka aktif olarak kullanılıyor mu?"
    )
    
    # Zaman damgaları
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    class Meta:
        db_table = 'products_seedbrand'
        verbose_name = "Tohum Markası"
        verbose_name_plural = "Tohum Markaları"
        ordering = ['name']
        
        indexes = [
            models.Index(fields=['name'], name='seedbrand_name_idx'),
            models.Index(fields=['is_active'], name='seedbrand_active_idx'),
        ]

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f"<SeedBrand: {self.name}>"
    
    @property
    def price_per_seed(self):
        """Tohum başına fiyat"""
        if self.seeds_per_packet > 0:
            price = self.price_per_packet / self.seeds_per_packet
            # Gereksiz sıfırları kaldır ve makul ondalık basamak sayısını kullan
            return float(f"{price:.2f}") if price != int(price) else int(price)
        return 0


class Variety(models.Model):
    """Çeşit modeli - Her türün çeşitlerini tanımlar (Starking, Granny Smith vb.)"""
    
    name = models.CharField(
        max_length=100,
        validators=[MinLengthValidator(2)],
        verbose_name="Çeşit Adı",
        help_text="Örnek: Starking, Granny Smith, Golden Delicious"
    )
    
    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name='varieties',
        verbose_name="Tür",
        help_text="Bu çeşidin ait olduğu tür"
    )
    
    seed_brand = models.ForeignKey(
        SeedBrand,
        on_delete=models.CASCADE,
        related_name='varieties',
        verbose_name="Tohum Markası",
        help_text="Bu çeşidin ait olduğu tohum markası"
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Aktif",
        help_text="Bu çeşit aktif olarak kullanılıyor mu?"
    )
    
    # Zaman damgaları
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    class Meta:
        db_table = 'products_variety'
        verbose_name = "Çeşit"
        verbose_name_plural = "Çeşitler"
        ordering = ['species__name', 'name']
        
        # Unique together - aynı türde aynı isimde çeşit olamaz
        unique_together = [['species', 'name']]
        
        indexes = [
            models.Index(fields=['name'], name='variety_name_idx'),
            models.Index(fields=['species', 'name'], name='variety_species_name_idx'),
            models.Index(fields=['is_active'], name='variety_active_idx'),
            models.Index(fields=['seed_brand'], name='variety_seedbrand_idx'),
        ]

    def __str__(self):
        return f"{self.species.name} - {self.name}"
    
    def __repr__(self):
        return f"<Variety: {self.species.name} - {self.name}>"
    
    def get_full_name(self):
        """Tam adı döndürür"""
        return f"{self.species.name} {self.name}"
    
    def get_full_name_with_brand(self):
        """Marka ile birlikte tam adı döndürür"""
        return f"{self.species.name} {self.name} ({self.seed_brand.name})"


class Rootstock(models.Model):
    """Anaç modeli - Aşılama için kullanılan anaçları tanımlar"""
    
    name = models.CharField(
        max_length=100,
        validators=[MinLengthValidator(2)],
        verbose_name="Anaç Adı",
        help_text="Örnek: M9, M26, MM106"
    )
    
    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name='rootstocks',
        verbose_name="Tür",
        help_text="Bu anacın ait olduğu tür"
    )
    
    # Anaç özellikleri
    vigor_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Düşük Vigör'),
            ('medium', 'Orta Vigör'),
            ('high', 'Yüksek Vigör'),
        ],
        blank=True,
        null=True,
        verbose_name="Vigör Seviyesi",
        help_text="Anacın büyüme gücü"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Açıklama",
        help_text="Anaç hakkında detaylı bilgiler"
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Aktif",
        help_text="Bu anaç aktif olarak kullanılıyor mu?"
    )
    
    # Zaman damgaları
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    class Meta:
        db_table = 'products_rootstock'
        verbose_name = "Anaç"
        verbose_name_plural = "Anaçlar"
        ordering = ['species__name', 'name']
        
        # Unique together - aynı türde aynı isimde anaç olamaz
        unique_together = [['species', 'name']]
        
        indexes = [
            models.Index(fields=['name'], name='rootstock_name_idx'),
            models.Index(fields=['species', 'name'], name='rootstock_species_name_idx'),
            models.Index(fields=['is_active'], name='rootstock_active_idx'),
            models.Index(fields=['vigor_level'], name='rootstock_vigor_idx'),
        ]

    def __str__(self):
        return f"{self.species.name} - {self.name}"
    
    def __repr__(self):
        return f"<Rootstock: {self.species.name} - {self.name}>"
    
    def get_full_name(self):
        """Tam adı döndürür"""
        return f"{self.species.name} {self.name}"



