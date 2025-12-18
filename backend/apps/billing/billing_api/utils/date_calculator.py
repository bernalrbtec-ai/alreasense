"""
BillingDateCalculator - Calcula dias de atraso ou até vencimento
"""
from datetime import datetime, date
from typing import Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class BillingDateCalculator:
    """
    Calcula dias de atraso ou dias até vencimento
    
    Uso:
        calculator = BillingDateCalculator()
        dias_atraso = calculator.calculate_days_overdue(data_vencimento)
        dias_vencimento = calculator.calculate_days_until_due(data_vencimento)
    """
    
    @staticmethod
    def calculate_days_overdue(due_date: date | datetime) -> int:
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
    def calculate_days_until_due(due_date: date | datetime) -> int:
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
    def format_date_for_template(due_date: date | datetime) -> str:
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



