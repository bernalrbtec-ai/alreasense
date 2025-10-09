"""
Services para lógica de negócio de campanhas
"""
from django.utils import timezone
from datetime import datetime, timedelta, time
from apps.campaigns.models import Holiday
import random


def is_allowed_to_send(campaign, current_datetime):
    """
    Valida se campanha pode enviar AGORA
    
    Returns:
        tuple: (can_send: bool, reason: str)
    """
    from apps.campaigns.models import Campaign
    
    hour = current_datetime.hour
    weekday = current_datetime.weekday()  # 0=seg, 6=dom
    today = current_datetime.date()
    current_time = current_datetime.time()
    
    # TIPO 1: IMEDIATO
    if campaign.schedule_type == Campaign.ScheduleType.IMMEDIATE:
        return True, "OK"
    
    # TIPO 2: DIAS ÚTEIS (seg-sex 9h-18h)
    if campaign.schedule_type == Campaign.ScheduleType.BUSINESS_DAYS:
        if weekday >= 5:
            return False, "fim_de_semana"
        
        if Holiday.is_holiday(today, campaign.tenant):
            return False, "feriado"
        
        if not (9 <= hour < 18):
            return False, "fora_horario_comercial"
        
        return True, "OK"
    
    # TIPO 3: HORÁRIO COMERCIAL (9h-18h qualquer dia)
    if campaign.schedule_type == Campaign.ScheduleType.BUSINESS_HOURS:
        if not (9 <= hour < 18):
            return False, "fora_horario_comercial"
        return True, "OK"
    
    # TIPO 4: PERÍODO PERSONALIZADO
    if campaign.schedule_type == Campaign.ScheduleType.CUSTOM_PERIOD:
        if campaign.skip_weekends and weekday >= 5:
            return False, "fim_de_semana"
        
        if campaign.skip_holidays and Holiday.is_holiday(today, campaign.tenant):
            return False, "feriado"
        
        in_morning = False
        in_afternoon = False
        
        if campaign.morning_start and campaign.morning_end:
            in_morning = (campaign.morning_start <= current_time < campaign.morning_end)
        
        if campaign.afternoon_start and campaign.afternoon_end:
            in_afternoon = (campaign.afternoon_start <= current_time < campaign.afternoon_end)
        
        if not (in_morning or in_afternoon):
            return False, "fora_janela_horario"
        
        return True, "OK"
    
    return False, "configuracao_invalida"


def calculate_next_send_time(campaign, current_datetime):
    """
    Calcula próxima janela válida
    
    Exemplo: Sexta 18h → Segunda 9h
    """
    can_send, reason = is_allowed_to_send(campaign, current_datetime)
    
    if can_send:
        # Pode enviar agora, delay normal
        delay = random.randint(
            campaign.instance.delay_min_seconds or 20,
            campaign.instance.delay_max_seconds or 50
        )
        return current_datetime + timedelta(seconds=delay)
    
    # NÃO pode enviar, buscar próxima janela
    next_day = current_datetime.date() + timedelta(days=1)
    
    for attempt in range(30):  # Máximo 30 dias
        weekday = next_day.weekday()
        
        # Validar fim de semana
        if campaign.skip_weekends and weekday >= 5:
            next_day += timedelta(days=1)
            continue
        
        # Validar feriado
        if campaign.skip_holidays and Holiday.is_holiday(next_day, campaign.tenant):
            next_day += timedelta(days=1)
            continue
        
        # Dia válido encontrado
        break
    
    # Determinar horário de início
    if campaign.schedule_type == campaign.ScheduleType.CUSTOM_PERIOD:
        start_hour = campaign.morning_start or time(9, 0)
    else:
        start_hour = time(9, 0)
    
    # Combinar data + hora
    next_send = datetime.combine(next_day, start_hour)
    next_send = timezone.make_aware(next_send)
    
    return next_send

