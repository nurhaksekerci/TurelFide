from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
import random
import string

User = get_user_model()


class UserService:
    """Kullanıcı işlemleri için servis sınıfı"""
    
    @staticmethod
    def authenticate_with_pin(pin_code):
        """4 haneli PIN kodu ile kullanıcı doğrulama"""
        try:
            if not pin_code or len(pin_code) != 4:
                return None
                
            if not pin_code.isdigit():
                return None
                
            user = User.objects.get(pin_code=pin_code, is_active=True)
            return user
            
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def create_user(username, first_name, last_name, role, phone_number, email=None):
        """Yeni kullanıcı oluşturma"""
        try:
            # Benzersiz pin kodu üret
            pin_code = UserService.generate_unique_pin()
            
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email or '',
                role=role,
                phone_number=phone_number,
                pin_code=pin_code
            )
            
            return user, pin_code
            
        except IntegrityError as e:
            if 'pin_code' in str(e):
                # PIN kodu zaten varsa, tekrar dene
                return UserService.create_user(username, first_name, last_name, role, phone_number, email)
            raise ValidationError("Kullanıcı oluşturulurken hata oluştu")
    
    @staticmethod
    def generate_unique_pin():
        """Benzersiz 4 haneli PIN kodu üretme"""
        max_attempts = 100
        attempts = 0
        
        while attempts < max_attempts:
            pin = ''.join(random.choices(string.digits, k=4))
            
            # 0000 gibi çok basit PIN'leri engelle
            if pin == '0000' or pin == '1234' or pin == '1111':
                attempts += 1
                continue
                
            if not User.objects.filter(pin_code=pin).exists():
                return pin
                
            attempts += 1
        
        raise ValidationError("Benzersiz PIN kodu üretilemedi")
    
    @staticmethod
    def reset_pin(user):
        """Kullanıcının PIN kodunu sıfırlama"""
        try:
            new_pin = UserService.generate_unique_pin()
            user.pin_code = new_pin
            user.save()
            return new_pin
        except Exception:
            raise ValidationError("PIN kodu sıfırlanırken hata oluştu")
    
    @staticmethod
    def get_users_by_role(role):
        """Role göre kullanıcıları getirme"""
        return User.objects.filter(role=role, is_active=True)
    
    @staticmethod
    def update_user_role(user, new_role):
        """Kullanıcının rolünü güncelleme"""
        valid_roles = [choice[0] for choice in User.ROLES]
        if new_role not in valid_roles:
            raise ValidationError("Geçersiz rol")
            
        user.role = new_role
        user.save()
        return user
    
    @staticmethod
    def deactivate_user(user):
        """Kullanıcıyı deaktive etme"""
        user.is_active = False
        user.save()
        return user
    
    @staticmethod
    def activate_user(user):
        """Kullanıcıyı aktive etme"""
        user.is_active = True
        user.save()
        return user
