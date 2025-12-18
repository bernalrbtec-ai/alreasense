"""
BillingBusinessHoursScheduler - Wrapper do BusinessHoursService existente
"""
from datetime import datetime, timedelta, time
from django.utils import timezone
from typing import Optional
from apps.chat.services.business_hours_service import BusinessHoursService
from apps.tenancy.models import Tenant
import logging

logger = logging.getLogger(__name__)


class BillingBusinessHoursScheduler:
    """
    Wrapper do BusinessHoursService para uso no sistema de billing
    
    Reutiliza toda a lógica existente de horário comercial
    """
    
    @staticmethod
    def is_within_business_hours(tenant: Tenant, check_time: Optional[datetime] = None) -> bool:
        """
        Verifica se está dentro do horário comercial
        
        Args:
            tenant: Tenant a verificar
            check_time: Horário para verificar (default: agora)
        
        Returns:
            True se está no horário comercial
        """
        is_open, _ = BusinessHoursService.is_business_hours(tenant, None, check_time)
        return is_open
    
    @staticmethod
    def get_next_valid_datetime(tenant: Tenant) -> datetime:
        """
        Retorna próximo horário válido (dentro do horário comercial)
        
        Args:
            tenant: Tenant
        
        Returns:
            datetime do próximo horário comercial disponível
        """
        from apps.chat.models_business_hours import BusinessHours
        from datetime import timedelta, time
        
        business_hours = BusinessHoursService.get_business_hours(tenant, None)
        if not business_hours:
            # Sem horário configurado = retorna agora + 1h
            return timezone.now() + timedelta(hours=1)
        
        next_open = BusinessHoursService._get_next_open_datetime(business_hours, timezone.now())
        if next_open:
            return next_open
        
        # Fallback: amanhã às 9h
        tomorrow = timezone.now().date() + timedelta(days=1)
        return timezone.make_aware(datetime.combine(tomorrow, time(9, 0)))
    
    @staticmethod
    def calculate_delay_until_next_hours(tenant: Tenant) -> int:
        """
        Calcula delay em segundos até próximo horário comercial
        
        Args:
            tenant: Tenant
        
        Returns:
            Segundos até próximo horário válido
        """
        now = timezone.now()
        next_valid = BillingBusinessHoursScheduler.get_next_valid_datetime(tenant)
        delay = (next_valid - now).total_seconds()
        
        return max(int(delay), 0)

