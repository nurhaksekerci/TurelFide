from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.
class User(AbstractUser):
    ROLES = [
        ('admin', 'Admin'),
        ('readonly', 'Patron'),
        ('product_manager', 'Proje Müdürü'),
        ('plant_manager', 'Ekim Sorumlusu'),
        ('plant_personel', 'Ekim Personeli'),
        ('seed_manager', 'Aşı Sorumlusu'),
        ('seed_personel', 'Aşı Personeli'),
        ('finance_personel', 'Finans Personeli'),
        ('shipping_personel', 'Sevkiyat Personeli')
    ]
    role = models.CharField(max_length=20, choices=ROLES)
    phone_number = models.CharField(max_length=10)
    pin_code = models.CharField(max_length=4, unique=True, db_index=True)
    
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    class Meta:
        verbose_name = 'Kullanıcı'
        verbose_name_plural = 'Kullanıcılar'
