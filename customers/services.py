from django.core.exceptions import ValidationError
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Customer


class CustomerService:
    """Customer business logic ve CRUD operasyonları"""
    
    @staticmethod
    def create_customer(user, first_name, last_name, phone_number, city, district, 
                       neighborhood, address, color='#ffeb3b'):
        """Yeni müşteri oluştur"""
        try:
            customer = Customer(
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                city=city,
                district=district,
                neighborhood=neighborhood,
                address=address,
                color=color,
                created_by=user
            )
            customer.full_clean()  # Model validasyonu
            customer.save()
            return customer, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Müşteri oluşturulurken hata: {str(e)}"
    
    @staticmethod
    def update_customer(customer, **kwargs):
        """Müşteri bilgilerini güncelle"""
        try:
            for field, value in kwargs.items():
                if hasattr(customer, field):
                    setattr(customer, field, value)
            
            customer.full_clean()
            customer.save()
            return customer, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Müşteri güncellenirken hata: {str(e)}"
    
    @staticmethod
    def delete_customer(customer):
        """Müşteriyi sil (soft delete - pasif yap)"""
        try:
            customer.deactivate()
            return True, "Müşteri pasifleştirildi"
        except Exception as e:
            return False, f"Müşteri silinirken hata: {str(e)}"
    
    @staticmethod
    def get_customer_list(search_query=None, color_filter=None, city_filter=None, 
                         is_active=None, page=1, per_page=20):
        """Filtrelenmiş müşteri listesi"""
        queryset = Customer.objects.all()
        
        # Arama filtresi
        if search_query:
            # search metodunu kullanmak yerine burada direkt filtreleme yapacağız
            from django.db.models import Q
            # Telefon numarası temizle
            clean_phone = ''.join(filter(str.isdigit, search_query))
            
            search_q = Q(first_name__icontains=search_query) | \
                      Q(last_name__icontains=search_query) | \
                      Q(city__icontains=search_query) | \
                      Q(district__icontains=search_query) | \
                      Q(neighborhood__icontains=search_query) | \
                      Q(address__icontains=search_query)
            
            if clean_phone:
                search_q |= Q(phone_number__icontains=clean_phone)
                
            queryset = queryset.filter(search_q)
        
        # Renk filtresi
        if color_filter:
            queryset = queryset.filter(color=color_filter)
        
        # Şehir filtresi
        if city_filter:
            queryset = queryset.filter(city__iexact=city_filter)
        
        # Durum filtresi
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        # Sıralama
        queryset = queryset.order_by('-created_at', 'first_name', 'last_name')
        
        # Sayfalama
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            'customers': page_obj,
            'total_count': queryset.count(),
            'page_obj': page_obj
        }
    
    @staticmethod
    def get_customer_stats():
        """Müşteri istatistikleri"""
        return Customer.objects.stats()
    
    @staticmethod
    def get_cities_with_count():
        """Şehirleri müşteri sayısı ile birlikte getir"""
        return Customer.objects.values('city').annotate(
            count=Count('id')
        ).order_by('-count')
    
    @staticmethod
    def bulk_update_color(customer_ids, new_color):
        """Toplu renk güncelleme"""
        try:
            updated = Customer.objects.filter(
                id__in=customer_ids
            ).update(color=new_color, updated_at=timezone.now())
            return updated, None
        except Exception as e:
            return 0, f"Toplu güncelleme hatası: {str(e)}"
    
    @staticmethod
    def bulk_activate(customer_ids):
        """Toplu aktifleştirme"""
        return Customer.objects.bulk_activate(customer_ids)
    
    @staticmethod
    def bulk_deactivate(customer_ids):
        """Toplu pasifleştirme"""
        return Customer.objects.bulk_deactivate(customer_ids)
    
    @staticmethod
    def export_customers_data(filters=None):
        """Müşteri verilerini export için hazırla"""
        queryset = Customer.objects.all()
        
        if filters:
            if filters.get('color'):
                queryset = queryset.by_color(filters['color'])
            if filters.get('city'):
                queryset = queryset.by_city(filters['city'])
            if filters.get('is_active') is not None:
                if filters['is_active']:
                    queryset = queryset.active()
                else:
                    queryset = queryset.inactive()
        
        customers_data = []
        for customer in queryset:
            customers_data.append({
                'id': customer.id,
                'full_name': customer.get_full_name(),
                'phone': customer.formatted_phone,
                'city': customer.city,
                'district': customer.district,
                'address': customer.get_full_address(),
                'color_category': customer.color_category,
                'color_display': customer.color_display_name,
                'is_active': 'Aktif' if customer.is_active else 'Pasif',
                'created_at': customer.created_at.strftime('%d.%m.%Y %H:%M'),
                'created_by': customer.created_by.get_full_name()
            })
        
        return customers_data
