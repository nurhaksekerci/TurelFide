from django.db import models
from django.core.validators import RegexValidator
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

# Create your models here.
class CustomerManager(models.Manager):
    """Customer modeli için optimized manager"""
    
    def get_queryset(self):
        """Base queryset with select_related for better performance"""
        return super().get_queryset().select_related('created_by')
    
    def active(self):
        """Sadece aktif müşteriler"""
        return self.filter(is_active=True)
    
    def inactive(self):
        """Sadece pasif müşteriler"""
        return self.filter(is_active=False)
    
    def by_city(self, city):
        """Şehir bazında filtreleme"""
        return self.filter(city__iexact=city)
    
    def by_district(self, district):
        """İlçe bazında filtreleme"""
        return self.filter(district__iexact=district)
    
    def by_color(self, color):
        """Renk bazında filtreleme"""
        return self.filter(color=color)
    
    def by_color_category(self, category):
        """Renk kategorisi bazında filtreleme (A,B,C,D,E,F,G sınıfı)"""
        color_map = {
            'A': '#0d5016',
            'B': '#2c9c3e', 
            'C': '#8bc34a',
            'D': '#ffeb3b',
            'E': '#ff9800',
            'F': '#ff5722',
            'G': '#d32f2f'
        }
        if category.upper() in color_map:
            return self.filter(color=color_map[category.upper()])
        return self.none()
    
    def created_today(self):
        """Bugün oluşturulan müşteriler"""
        today = timezone.now().date()
        return self.filter(created_at__date=today)
    
    def created_this_week(self):
        """Bu hafta oluşturulan müşteriler"""
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        return self.filter(created_at__gte=week_ago)
    
    def created_this_month(self):
        """Bu ay oluşturulan müşteriler"""
        from datetime import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        return self.filter(created_at__gte=month_ago)
    
    def search(self, query):
        """Gelişmiş arama fonksiyonu"""
        if not query:
            return self.none()
        
        # Telefon numarası temizle
        clean_phone = ''.join(filter(str.isdigit, query))
        
        search_query = models.Q(first_name__icontains=query) | \
                      models.Q(last_name__icontains=query) | \
                      models.Q(city__icontains=query) | \
                      models.Q(district__icontains=query)
        
        if clean_phone:
            search_query |= models.Q(phone_number__icontains=clean_phone)
            
        return self.filter(search_query)
    
    def bulk_activate(self, customer_ids):
        """Toplu aktifleştirme"""
        return self.filter(id__in=customer_ids).update(
            is_active=True,
            updated_at=timezone.now()
        )
    
    def bulk_deactivate(self, customer_ids):
        """Toplu pasifleştirme"""
        return self.filter(id__in=customer_ids).update(
            is_active=False,
            updated_at=timezone.now()
        )
    
    def stats(self):
        """Müşteri istatistikleri"""
        total = self.count()
        active = self.active().count()
        inactive = self.inactive().count()
        
        # Renk bazlı istatistikler
        color_stats = {}
        for color_code, color_name in [
            ('#0d5016', 'A Sınıfı'),
            ('#2c9c3e', 'B Sınıfı'),
            ('#8bc34a', 'C Sınıfı'),
            ('#ffeb3b', 'D Sınıfı'),
            ('#ff9800', 'E Sınıfı'),
            ('#ff5722', 'F Sınıfı'),
            ('#d32f2f', 'G Sınıfı'),
        ]:
            count = self.filter(color=color_code).count()
            color_stats[color_name] = {
                'count': count,
                'percentage': round((count / total * 100) if total > 0 else 0, 2)
            }
        
        return {
            'total': total,
            'active': active,
            'inactive': inactive,
            'active_percentage': round((active / total * 100) if total > 0 else 0, 2),
            'premium_customers': self.premium_customers().count(),
            'attention_needed': self.attention_needed_customers().count(),
            'color_breakdown': color_stats
        }
    
    def premium_customers(self):
        """Premium müşteriler (A ve B sınıfı)"""
        return self.filter(color__in=['#0d5016', '#2c9c3e'])
    
    def standard_customers(self):
        """Standart müşteriler (C ve D sınıfı)"""
        return self.filter(color__in=['#8bc34a', '#ffeb3b'])
    
    def attention_needed_customers(self):
        """Dikkat gereken müşteriler (E, F, G sınıfı)"""
        return self.filter(color__in=['#ff9800', '#ff5722', '#d32f2f'])


class Customer(models.Model):
    COLOR_CHOICES = [
        ('#0d5016', 'Koyu Yeşil (A Sınıfı)'),
        ('#2c9c3e', 'Açık Yeşil (B Sınıfı)'),
        ('#8bc34a', 'Fıstık Yeşili (C Sınıfı)'),
        ('#ffeb3b', 'Sarı (D Sınıfı)'),
        ('#ff9800', 'Sarı-Turuncu (E Sınıfı)'),
        ('#ff5722', 'Turuncu (F Sınıfı)'),
        ('#d32f2f', 'Kırmızı (G Sınıfı)'),
    ]
    # Kişisel Bilgiler
    first_name = models.CharField(
        max_length=100,  # 255'den 100'e indirdim, daha gerçekçi
        verbose_name="Ad",
        help_text="Müşterinin adı",
        blank=False,  # Boş bırakılamaz
        null=False   # NULL olamaz
    )
    last_name = models.CharField(
        max_length=100,
        verbose_name="Soyad", 
        help_text="Müşterinin soyadı",
        blank=False,  # Boş bırakılamaz
        null=False   # NULL olamaz
    )

    color = models.CharField(
        max_length=10,
        choices=COLOR_CHOICES,
        default='#ffeb3b',
        db_index=True,  # Renk bazında filtreleme için index
        verbose_name="Renk",
        help_text="Müşterinin renk seçimi"
    )
    
    # İletişim Bilgileri
    phone_number = models.CharField(
        max_length=10,
        unique=True,  # Telefon numarası benzersiz olmalı
        validators=[
            RegexValidator(
                regex=r'^5[0-9]{9}$',
                message='Telefon numarası 5XXXXXXXXX formatında olmalıdır'
            )
        ],
        verbose_name="Telefon Numarası",
        help_text="5XXXXXXXXX formatında (Türkiye)"
    )
    
    # Adres Bilgileri
    city = models.CharField(
        max_length=50,
        db_index=True,  # Şehir bazında sık arama yapılacağı için index
        verbose_name="Şehir"
    )
    district = models.CharField(
        max_length=50,
        db_index=True,  # İlçe bazında sık arama yapılacağı için index
        verbose_name="İlçe"
    )
    neighborhood = models.CharField(
        max_length=100,
        verbose_name="Mahalle"
    )
    address = models.TextField(
        max_length=500,  # TextField için maksimum limit
        verbose_name="Adres",
        help_text="Detaylı adres bilgisi"
    )
    
    # Durum ve Takip
    is_active = models.BooleanField(
        default=True,
        db_index=True,  # Aktif müşteri sorguları için index
        verbose_name="Aktif",
        help_text="Müşteri aktif mi?"
    )
    
    # Zaman Damgaları
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,  # Tarih bazında sıralama ve filtreleme için
        verbose_name="Oluşturulma Tarihi"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi"
    )
    
    # İlişkiler
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  # CASCADE yerine PROTECT - veri güvenliği için
        related_name='created_customers',
        verbose_name="Oluşturan Kullanıcı"
    )
    
    # Custom Manager
    objects = CustomerManager()
    
    class Meta:
        db_table = 'customers_customer'
        verbose_name = "Müşteri"
        verbose_name_plural = "Müşteriler"
        ordering = ['-created_at', 'first_name', 'last_name']
        
        # Composite indexes - yaygın sorgu kombinasyonları için
        indexes = [
            models.Index(fields=['city', 'district'], name='city_district_idx'),
            models.Index(fields=['is_active', 'created_at'], name='active_created_idx'),
            models.Index(fields=['first_name', 'last_name'], name='full_name_idx'),
            models.Index(fields=['created_by', 'is_active'], name='creator_active_idx'),
            models.Index(fields=['color', 'is_active'], name='color_active_idx'),
            models.Index(fields=['color', 'city'], name='color_city_idx'),
        ]
        
        # Constraints
        constraints = [
            # CharField için length lookup'u desteklenmediği için constraint'leri kaldırdık
            # Bunun yerine blank=False, null=False kullanıyoruz
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.phone_number}"
    
    def __repr__(self):
        return f"<Customer: {self.get_full_name()}>"
    
    # Model Methods
    def get_full_name(self):
        """Tam adı döndürür"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_full_address(self):
        """Tam adresi döndürür"""
        return f"{self.neighborhood}, {self.district}/{self.city}\n{self.address}"
    
    def get_short_address(self):
        """Kısa adres (şehir/ilçe)"""
        return f"{self.district}/{self.city}"
    
    def activate(self):
        """Müşteriyi aktif hale getirir"""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
    
    def deactivate(self):
        """Müşteriyi pasif hale getirir"""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def get_absolute_url(self):
        """Customer detail URL'i döndürür"""
        return reverse('customers:detail', kwargs={'pk': self.pk})
    
    @property
    def age_in_system(self):
        """Sistemde kaç gündür kayıtlı"""
        return (timezone.now() - self.created_at).days
    
    @property
    def formatted_phone(self):
        """Formatlanmış telefon numarası (+90 5XX XXX XX XX)"""
        if len(self.phone_number) == 10:
            return f"+90 {self.phone_number[:3]} {self.phone_number[3:6]} {self.phone_number[6:8]} {self.phone_number[8:]}"
        return self.phone_number
    
    @property
    def color_category(self):
        """Renk kategorisini döndürür (A, B, C, D, E, F, G)"""
        color_map = {
            '#0d5016': 'A',
            '#2c9c3e': 'B',
            '#8bc34a': 'C', 
            '#ffeb3b': 'D',
            '#ff9800': 'E',
            '#ff5722': 'F',
            '#d32f2f': 'G'
        }
        return color_map.get(self.color, 'D')
    
    @property
    def color_display_name(self):
        """Renk görüntü adını döndürür"""
        for choice in self.COLOR_CHOICES:
            if choice[0] == self.color:
                return choice[1]
        return "Bilinmeyen"
    
    @property
    def is_premium_customer(self):
        """Premium müşteri mi? (A veya B sınıfı)"""
        return self.color in ['#0d5016', '#2c9c3e']
    
    @property
    def needs_attention(self):
        """Dikkat gerektiren müşteri mi? (E, F, G sınıfı)"""
        return self.color in ['#ff9800', '#ff5722', '#d32f2f']
    
    def get_color_priority(self):
        """Renk öncelik değerini döndürür (1=A sınıfı en yüksek)"""
        priority_map = {
            '#0d5016': 1,  # A Sınıfı
            '#2c9c3e': 2,  # B Sınıfı
            '#8bc34a': 3,  # C Sınıfı
            '#ffeb3b': 4,  # D Sınıfı
            '#ff9800': 5,  # E Sınıfı
            '#ff5722': 6,  # F Sınıfı
            '#d32f2f': 7,  # G Sınıfı
        }
        return priority_map.get(self.color, 4)
    
    # Class Methods
    @classmethod
    def active_customers(cls):
        """Aktif müşterileri döndürür"""
        return cls.objects.filter(is_active=True)
    
    @classmethod
    def by_city(cls, city):
        """Belirli şehirdeki müşterileri döndürür"""
        return cls.objects.filter(city__iexact=city, is_active=True)
    
    @classmethod
    def by_creator(cls, user):
        """Belirli kullanıcı tarafından oluşturulan müşteriler"""
        return cls.objects.filter(created_by=user)
    
    @classmethod
    def search(cls, query):
        """Müşteri arama (ad, soyad, telefon)"""
        return cls.objects.filter(
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query) |
            models.Q(phone_number__icontains=query)
        )
    
    def save(self, *args, **kwargs):
        """Kaydetmeden önce veri temizleme ve validasyon"""
        # İsim ve soyismi başharflerini büyük yap
        self.first_name = self.first_name.strip().title()
        self.last_name = self.last_name.strip().title()
        
        # Boş isim kontrolü
        if not self.first_name:
            raise ValueError("Ad alanı boş olamaz")
        if not self.last_name:
            raise ValueError("Soyad alanı boş olamaz")
        
        # Şehir ve ilçe isimlerini düzenle
        self.city = self.city.strip().title()
        self.district = self.district.strip().title()
        self.neighborhood = self.neighborhood.strip().title()
        
        # Telefon numarasını temizle (sadece rakamlar)
        self.phone_number = ''.join(filter(str.isdigit, self.phone_number))
        
        super().save(*args, **kwargs)


