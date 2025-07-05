from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Species, SeedBrand, Variety, Rootstock


class SpeciesService:
    """Tür (Species) business logic"""
    
    @staticmethod
    def create_species(name):
        """Yeni tür oluştur"""
        try:
            species = Species(name=name.strip())
            species.full_clean()
            species.save()
            return species, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Tür oluşturulurken hata: {str(e)}"
    
    @staticmethod
    def update_species(species, **kwargs):
        """Tür bilgilerini güncelle"""
        try:
            for field, value in kwargs.items():
                if hasattr(species, field):
                    setattr(species, field, value)
            species.full_clean()
            species.save()
            return species, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Tür güncellenirken hata: {str(e)}"
    
    @staticmethod
    def get_species_list(search_query=None, is_active=None, page=1, per_page=20):
        """Filtrelenmiş tür listesi"""
        queryset = Species.objects.all()
        
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        queryset = queryset.order_by('name')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            'species': page_obj,
            'total_count': queryset.count(),
            'page_obj': page_obj
        }
    
    @staticmethod
    def get_species_stats():
        """Tür istatistikleri"""
        total = Species.objects.count()
        active = Species.objects.filter(is_active=True).count()
        
        # Her tür için çeşit ve anaç sayıları
        species_details = []
        for species in Species.objects.filter(is_active=True):
            species_details.append({
                'name': species.name,
                'varieties_count': species.active_varieties_count,
                'rootstocks_count': species.active_rootstocks_count,
            })
        
        return {
            'total': total,
            'active': active,
            'inactive': total - active,
            'species_details': species_details
        }


class SeedBrandService:
    """Tohum Markası business logic"""
    
    @staticmethod
    def create_seed_brand(name, price_per_packet, seeds_per_packet):
        """Yeni tohum markası oluştur"""
        try:
            seed_brand = SeedBrand(
                name=name.strip(),
                price_per_packet=price_per_packet,
                seeds_per_packet=seeds_per_packet
            )
            seed_brand.full_clean()
            seed_brand.save()
            return seed_brand, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Tohum markası oluşturulurken hata: {str(e)}"
    
    @staticmethod
    def update_seed_brand(seed_brand, **kwargs):
        """Tohum markası bilgilerini güncelle"""
        try:
            for field, value in kwargs.items():
                if hasattr(seed_brand, field):
                    setattr(seed_brand, field, value)
            seed_brand.full_clean()
            seed_brand.save()
            return seed_brand, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Tohum markası güncellenirken hata: {str(e)}"
    
    @staticmethod
    def get_seed_brand_list(search_query=None, is_active=None, page=1, per_page=20):
        """Filtrelenmiş tohum markası listesi"""
        queryset = SeedBrand.objects.all()
        
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        queryset = queryset.order_by('name')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            'seed_brands': page_obj,
            'total_count': queryset.count(),
            'page_obj': page_obj
        }
    
    @staticmethod
    def get_seed_brand_stats():
        """Tohum markası istatistikleri"""
        total = SeedBrand.objects.count()
        active = SeedBrand.objects.filter(is_active=True).count()
        
        # Fiyat istatistikleri
        active_brands = SeedBrand.objects.filter(is_active=True)
        avg_price = active_brands.aggregate(avg_price=Avg('price_per_packet'))['avg_price'] or 0
        avg_seeds = active_brands.aggregate(avg_seeds=Avg('seeds_per_packet'))['avg_seeds'] or 0
        
        # En ucuz ve en pahalı
        cheapest = active_brands.order_by('price_per_packet').first()
        most_expensive = active_brands.order_by('-price_per_packet').first()
        
        return {
            'total': total,
            'active': active,
            'inactive': total - active,
            'avg_price_per_packet': round(avg_price, 2),
            'avg_seeds_per_packet': round(avg_seeds, 0),
            'cheapest_brand': cheapest,
            'most_expensive_brand': most_expensive
        }


class VarietyService:
    """Çeşit business logic"""
    
    @staticmethod
    def create_variety(name, species, seed_brand):
        """Yeni çeşit oluştur"""
        try:
            variety = Variety(
                name=name.strip(),
                species=species,
                seed_brand=seed_brand
            )
            variety.full_clean()
            variety.save()
            return variety, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Çeşit oluşturulurken hata: {str(e)}"
    
    @staticmethod
    def update_variety(variety, **kwargs):
        """Çeşit bilgilerini güncelle"""
        try:
            for field, value in kwargs.items():
                if hasattr(variety, field):
                    setattr(variety, field, value)
            variety.full_clean()
            variety.save()
            return variety, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Çeşit güncellenirken hata: {str(e)}"
    
    @staticmethod
    def get_variety_list(search_query=None, species_filter=None, brand_filter=None, 
                        is_active=None, page=1, per_page=20):
        """Filtrelenmiş çeşit listesi"""
        queryset = Variety.objects.select_related('species', 'seed_brand').all()
        
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(species__name__icontains=search_query)
            )
        
        if species_filter:
            queryset = queryset.filter(species_id=species_filter)
        
        if brand_filter:
            queryset = queryset.filter(seed_brand_id=brand_filter)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        queryset = queryset.order_by('species__name', 'name')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            'varieties': page_obj,
            'total_count': queryset.count(),
            'page_obj': page_obj
        }
    
    @staticmethod
    def get_variety_stats():
        """Çeşit istatistikleri"""
        total = Variety.objects.count()
        active = Variety.objects.filter(is_active=True).count()
        
        # Tür bazında çeşit dağılımı
        species_breakdown = Variety.objects.filter(is_active=True).values(
            'species__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        # Marka bazında çeşit dağılımı
        brand_breakdown = Variety.objects.filter(is_active=True).values(
            'seed_brand__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        return {
            'total': total,
            'active': active,
            'inactive': total - active,
            'species_breakdown': list(species_breakdown),
            'brand_breakdown': list(brand_breakdown)
        }


class RootstockService:
    """Anaç business logic"""
    
    @staticmethod
    def create_rootstock(name, species, vigor_level=None, description=None):
        """Yeni anaç oluştur"""
        try:
            rootstock = Rootstock(
                name=name.strip(),
                species=species,
                vigor_level=vigor_level,
                description=description
            )
            rootstock.full_clean()
            rootstock.save()
            return rootstock, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Anaç oluşturulurken hata: {str(e)}"
    
    @staticmethod
    def update_rootstock(rootstock, **kwargs):
        """Anaç bilgilerini güncelle"""
        try:
            for field, value in kwargs.items():
                if hasattr(rootstock, field):
                    setattr(rootstock, field, value)
            rootstock.full_clean()
            rootstock.save()
            return rootstock, None
        except ValidationError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Anaç güncellenirken hata: {str(e)}"
    
    @staticmethod
    def get_rootstock_list(search_query=None, species_filter=None, vigor_filter=None,
                          is_active=None, page=1, per_page=20):
        """Filtrelenmiş anaç listesi"""
        queryset = Rootstock.objects.select_related('species').all()
        
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(species__name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if species_filter:
            queryset = queryset.filter(species_id=species_filter)
        
        if vigor_filter:
            queryset = queryset.filter(vigor_level=vigor_filter)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        queryset = queryset.order_by('species__name', 'name')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            'rootstocks': page_obj,
            'total_count': queryset.count(),
            'page_obj': page_obj
        }
    
    @staticmethod
    def get_rootstock_stats():
        """Anaç istatistikleri"""
        total = Rootstock.objects.count()
        active = Rootstock.objects.filter(is_active=True).count()
        
        # Tür bazında anaç dağılımı
        species_breakdown = Rootstock.objects.filter(is_active=True).values(
            'species__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        # Vigör seviyesi bazında dağılım
        vigor_breakdown = Rootstock.objects.filter(is_active=True).values(
            'vigor_level'
        ).annotate(count=Count('id')).order_by('-count')
        
        return {
            'total': total,
            'active': active,
            'inactive': total - active,
            'species_breakdown': list(species_breakdown),
            'vigor_breakdown': list(vigor_breakdown)
        }


class ProductService:
    """Genel ürün istatistikleri ve işlemleri"""
    
    @staticmethod
    def get_general_stats():
        """Genel ürün istatistikleri"""
        species_stats = SpeciesService.get_species_stats()
        brand_stats = SeedBrandService.get_seed_brand_stats()
        variety_stats = VarietyService.get_variety_stats()
        rootstock_stats = RootstockService.get_rootstock_stats()
        
        return {
            'species': species_stats,
            'seed_brands': brand_stats,
            'varieties': variety_stats,
            'rootstocks': rootstock_stats,
            'summary': {
                'total_species': species_stats['active'],
                'total_brands': brand_stats['active'],
                'total_varieties': variety_stats['active'],
                'total_rootstocks': rootstock_stats['active']
            }
        }
    
    @staticmethod
    def bulk_toggle_status(model_class, ids, is_active):
        """Toplu durum değiştirme"""
        try:
            updated = model_class.objects.filter(id__in=ids).update(
                is_active=is_active,
                updated_at=timezone.now()
            )
            return updated, None
        except Exception as e:
            return 0, f"Toplu işlem hatası: {str(e)}"
    
    @staticmethod
    def search_all_products(query):
        """Tüm ürünlerde arama"""
        if not query or len(query) < 2:
            return {
                'species': [],
                'varieties': [],
                'rootstocks': [],
                'seed_brands': []
            }
        
        results = {
            'species': list(Species.objects.filter(
                name__icontains=query, is_active=True
            )[:10]),
            'varieties': list(Variety.objects.filter(
                Q(name__icontains=query) | Q(species__name__icontains=query),
                is_active=True
            ).select_related('species', 'seed_brand')[:10]),
            'rootstocks': list(Rootstock.objects.filter(
                Q(name__icontains=query) | Q(species__name__icontains=query),
                is_active=True
            ).select_related('species')[:10]),
            'seed_brands': list(SeedBrand.objects.filter(
                name__icontains=query, is_active=True
            )[:10])
        }
        
        return results
