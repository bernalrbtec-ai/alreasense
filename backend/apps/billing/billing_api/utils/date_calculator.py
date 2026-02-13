"""
BillingDateCalculator - Calcula dias de atraso ou até vencimento
"""
from datetime import datetime, date, timedelta
from typing import Optional, Union
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class DateCalculator:
    """
    Calcula datas ajustadas para envio (dia útil, horário comercial)
    """
    
    @staticmethod
    def is_weekend(target_date: date) -> bool:
        """Verifica se é fim de semana"""
        return target_date.weekday() >= 5
    
    @staticmethod
    def is_holiday(target_date: date, tenant) -> bool:
        """Verifica se é feriado (implementar se tiver modelo Holiday)"""
        # TODO: Implementar verificação de feriados se necessário
        return False
    
    @staticmethod
    def calculate_send_date(target_date: date, tenant) -> date:
        """
        Calcula data de envio ajustada para dia útil
        
        Regras:
        - Se target_date é fim de semana → antecipa para última sexta
        - Se target_date é feriado → antecipa para último dia útil anterior
        - Se target_date é dia útil → usa target_date
        
        Args:
            target_date: Data desejada para envio
            tenant: Tenant para verificar feriados
        
        Returns:
            Data ajustada (sempre dia útil)
        """
        current_date = target_date
        
        # Máximo 30 dias para trás (proteção contra loop infinito)
        max_attempts = 30
        attempts = 0
        
        while attempts < max_attempts:
            # Verifica fim de semana
            if DateCalculator.is_weekend(current_date):
                if is_overdue:
                    # Posterga para próxima segunda
                    days_forward = 7 - current_date.weekday()  # 5=sábado->2, 6=domingo->1
                    current_date = current_date + timedelta(days=days_forward)
                    logger.debug(f"📅 {target_date} é fim de semana (overdue), postergado para {current_date}")
                else:
                    # Antecipa para última sexta
                    days_back = current_date.weekday() - 4  # 5=sábado->1, 6=domingo->2
                    current_date = current_date - timedelta(days=days_back)
                    logger.debug(f"📅 {target_date} é fim de semana (upcoming), antecipado para {current_date}")
                attempts += 1
                continue
            
            # Verifica feriado
            if DateCalculator.is_holiday(current_date, tenant):
                if is_overdue:
                    # Posterga 1 dia
                    current_date = current_date + timedelta(days=1)
                    logger.debug(f"📅 {target_date} é feriado (overdue), postergado para {current_date}")
                else:
                    # Antecipa 1 dia
                    current_date = current_date - timedelta(days=1)
                    logger.debug(f"📅 {target_date} é feriado (upcoming), antecipado para {current_date}")
                attempts += 1
                continue
            
            # ✅ Dia útil encontrado
            if current_date != target_date:
                logger.info(
                    f"📅 Data ajustada: {target_date} → {current_date}",
                    extra={'original_date': str(target_date), 'adjusted_date': str(current_date)}
                )
            
            return current_date
        
        # Fallback: retorna target_date mesmo se não conseguir ajustar
        logger.warning(
            f"⚠️ Não foi possível ajustar data {target_date} após {max_attempts} tentativas",
            extra={'target_date': str(target_date)}
        )
        return target_date


class BillingDateCalculator:
    """
    Calcula dias de atraso ou dias até vencimento
    
    Uso:
        calculator = BillingDateCalculator()
        dias_atraso = calculator.calculate_days_overdue(data_vencimento)
        dias_vencimento = calculator.calculate_days_until_due(data_vencimento)
    """
    
    @staticmethod
    def calculate_days_overdue(due_date: Union[date, datetime]) -> int:
        """
        Calcula quantos dias a cobrança está atrasada
        
        Args:
            due_date: Data de vencimento (date ou datetime)
        
        Returns:
            Número de dias atrasados (0 se ainda não venceu)
        
        Examples:
            >>> calculator = BillingDateCalculator()
            >>> calculator.calculate_days_overdue(date(2025, 1, 1))  # Se hoje é 5/1/2025
            4
            >>> calculator.calculate_days_overdue(date(2025, 12, 31))  # Se ainda não venceu
            0
        """
        today = timezone.now().date()
        
        # Se for datetime, converter para date
        if isinstance(due_date, datetime):
            due_date = due_date.date()
        
        if due_date >= today:
            return 0
        
        days_overdue = (today - due_date).days
        logger.debug(f"Calculado dias de atraso: {days_overdue} (vencimento: {due_date}, hoje: {today})")
        return days_overdue
    
    @staticmethod
    def calculate_days_until_due(due_date: Union[date, datetime]) -> int:
        """
        Calcula quantos dias faltam até o vencimento
        
        Args:
            due_date: Data de vencimento (date ou datetime)
        
        Returns:
            Número de dias até o vencimento (0 se já venceu)
        
        Examples:
            >>> calculator = BillingDateCalculator()
            >>> calculator.calculate_days_until_due(date(2025, 12, 31))  # Se hoje é 25/12/2025
            6
            >>> calculator.calculate_days_until_due(date(2025, 1, 1))  # Se já venceu
            0
        """
        today = timezone.now().date()
        
        # Se for datetime, converter para date
        if isinstance(due_date, datetime):
            due_date = due_date.date()
        
        if due_date <= today:
            return 0
        
        days_until = (due_date - today).days
        logger.debug(f"Calculado dias até vencimento: {days_until} (vencimento: {due_date}, hoje: {today})")
        return days_until
    
    @staticmethod
    def format_date_for_template(due_date: Union[date, datetime]) -> str:
        """
        Formata data para usar em templates (DD/MM/YYYY)
        
        Args:
            due_date: Data de vencimento
        
        Returns:
            Data formatada como string (ex: "31/12/2025")
        """
        if isinstance(due_date, datetime):
            due_date = due_date.date()
        
        return due_date.strftime('%d/%m/%Y')



