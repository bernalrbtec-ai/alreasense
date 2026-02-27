"""
Serviços para envio de notificações personalizadas.
Reutiliza o sistema existente de WhatsApp e WebSocket.
"""

import logging
import re
import requests
import time
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

logger = logging.getLogger(__name__)


def normalize_phone(phone):
    """
    Normaliza telefone para formato E.164.
    
    Args:
        phone: String com telefone em qualquer formato
    
    Returns:
        str: Telefone no formato E.164 (ex: +5517991234567) ou None se inválido
    """
    if not phone:
        return None
    
    # Remover caracteres não numéricos exceto +
    phone_clean = re.sub(r'[^\d+]', '', phone.strip())
    
    # Validar formato básico
    if not phone_clean or len(phone_clean) < 10:
        logger.warning(f'⚠️ [PHONE NORMALIZE] Telefone inválido: {phone}')
        return None
    
    # Garantir formato E.164
    if not phone_clean.startswith('+'):
        if phone_clean.startswith('55'):
            phone_clean = f'+{phone_clean}'
        else:
            # Remover zeros à esquerda e adicionar +55
            phone_digits = ''.join(filter(str.isdigit, phone_clean))
            if phone_digits.startswith('0'):
                phone_digits = phone_digits[1:]
            phone_clean = f'+55{phone_digits}'
    
    # Validar formato final (deve ter pelo menos +5511999999999 = 13 caracteres)
    if len(phone_clean) < 13 or not phone_clean.startswith('+'):
        logger.warning(f'⚠️ [PHONE NORMALIZE] Telefone em formato inválido após normalização: {phone_clean}')
        return None
    
    return phone_clean


def _get_whatsapp_config_for_tenant(tenant):
    """
    Helper para buscar configuração WhatsApp do tenant.
    
    Args:
        tenant: Instância de Tenant
    
    Returns:
        tuple: (base_url, api_key, instance_name) ou (None, None, None) se não encontrado
    """
    instance = WhatsAppInstance.objects.filter(
        tenant=tenant,
        is_active=True,
        status='active'
    ).select_related('tenant').first()
    if instance and instance.api_url and instance.api_key:
        return instance.api_url.rstrip('/'), instance.api_key, instance.instance_name
    connection = EvolutionConnection.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('tenant').first()
    if connection and connection.base_url and connection.api_key:
        instance = WhatsAppInstance.objects.filter(tenant=tenant, is_active=True).first()
        instance_name = instance.instance_name if instance else 'default'
        return connection.base_url.rstrip('/'), connection.api_key, instance_name
    return None, None, None


def _get_whatsapp_config(user):
    """
    Helper para buscar configuração WhatsApp do tenant (via user).
    
    Args:
        user: Instância de User
    
    Returns:
        tuple: (base_url, api_key, instance_name) ou (None, None, None) se não encontrado
    """
    return _get_whatsapp_config_for_tenant(user.tenant)


def send_whatsapp_notification(user, message):
    """
    Envia notificação via WhatsApp.
    
    ⚠️ NOTA: Esta função usa o sistema existente de envio de WhatsApp.
    Reutiliza a lógica de _notify_task_user do scheduler.
    
    Args:
        user: Instância de User
        message: String com a mensagem formatada
    
    Returns:
        bool: True se enviado com sucesso
    
    Raises:
        ValueError: Se usuário não tem telefone ou telefone inválido
    """
    # ✅ VALIDAÇÃO: Verificar se usuário tem telefone
    if not user.phone:
        raise ValueError(f"Usuário {user.email} não tem telefone cadastrado")
    
    # ✅ NORMALIZAÇÃO: Garantir formato E.164
    phone_normalized = normalize_phone(user.phone)
    if not phone_normalized:
        raise ValueError(f"Telefone do usuário {user.email} não pôde ser normalizado: {user.phone}")
    
    # Buscar configuração WhatsApp
    base_url, api_key, instance_name = _get_whatsapp_config(user)
    
    if not base_url or not api_key:
        logger.warning(f'⚠️ [WHATSAPP NOTIFICATION] API URL ou API Key não configurados para tenant {user.tenant_id}')
        raise ValueError(f"API URL ou API Key não configurados para tenant {user.tenant.name}")
    
    url = f"{base_url}/message/sendText/{instance_name}"
    headers = {
        'apikey': api_key,
        'Content-Type': 'application/json'
    }
    
    # Remover + do telefone para envio (Evolution API espera sem +)
    phone_for_api = phone_normalized.replace('+', '')
    
    payload = {
        'number': phone_for_api,
        'text': message
    }
    
    # ✅ RETRY com backoff exponencial
    max_retries = 3
    base_delay = 1  # 1 segundo base
    
    logger.info(f'📱 [WHATSAPP NOTIFICATION] ====== INICIANDO ENVIO ======')
    logger.info(f'   Usuário: {user.email} (ID: {user.id})')
    logger.info(f'   Telefone normalizado: {phone_normalized}')
    logger.info(f'   URL: {url}')
    logger.info(f'   Instance: {instance_name}')
    logger.info(f'   Mensagem (primeiros 100 chars): {message[:100]}...')
    
    for attempt in range(max_retries):
        try:
            logger.info(f'📱 [WHATSAPP NOTIFICATION] Tentativa {attempt + 1}/{max_retries} - Enviando para {phone_normalized} (usuário: {user.email})')
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info(f'✅ [WHATSAPP NOTIFICATION] WhatsApp enviado com sucesso para {phone_normalized} (usuário: {user.email}, ID: {user.id})')
                return True
            else:
                error_msg = f"Status {response.status_code}: {response.text[:200]}"
                logger.warning(f'⚠️ [WHATSAPP NOTIFICATION] Erro ao enviar (tentativa {attempt + 1}/{max_retries}): {error_msg}')
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f'⏳ [WHATSAPP NOTIFICATION] Aguardando {delay}s antes de tentar novamente...')
                    time.sleep(delay)
                else:
                    raise Exception(f"Falha após {max_retries} tentativas: {error_msg}")
        
        except requests.exceptions.Timeout:
            logger.warning(f'⏱️ [WHATSAPP NOTIFICATION] Timeout na tentativa {attempt + 1}/{max_retries}')
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise Exception("Timeout após múltiplas tentativas")
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f'🔌 [WHATSAPP NOTIFICATION] Erro de conexão na tentativa {attempt + 1}/{max_retries}: {e}')
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise Exception(f"Erro de conexão após múltiplas tentativas: {e}")
        
        except Exception as e:
            logger.error(f'❌ [WHATSAPP NOTIFICATION] Erro inesperado na tentativa {attempt + 1}/{max_retries}: {e}', exc_info=True)
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise
    
    return False


def send_whatsapp_to_phone(tenant, phone, message):
    """
    Envia notificação via WhatsApp para um número específico usando a config do tenant.

    Args:
        tenant: Instância de Tenant
        phone: String com o telefone de destino
        message: String com a mensagem

    Returns:
        bool: True se enviado com sucesso

    Raises:
        ValueError: Se telefone inválido ou config WhatsApp não disponível
    """
    if not phone or not str(phone).strip():
        raise ValueError("Telefone de destino não informado")
    phone_normalized = normalize_phone(str(phone).strip())
    if not phone_normalized:
        raise ValueError(f"Telefone não pôde ser normalizado: {phone}")
    base_url, api_key, instance_name = _get_whatsapp_config_for_tenant(tenant)
    if not base_url or not api_key:
        logger.warning(
            "⚠️ [WHATSAPP NOTIFICATION] API URL ou API Key não configurados para tenant %s",
            getattr(tenant, "id", tenant),
        )
        raise ValueError("API WhatsApp não configurada para o tenant")
    url = f"{base_url}/message/sendText/{instance_name}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    phone_for_api = phone_normalized.replace("+", "")
    payload = {"number": phone_for_api, "text": message}
    max_retries = 3
    base_delay = 1
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code in [200, 201]:
                logger.info(
                    "✅ [WHATSAPP NOTIFICATION] Enviado para %s (tenant %s)",
                    phone_normalized,
                    getattr(tenant, "id", "?"),
                )
                return True
            logger.warning(
                "⚠️ [WHATSAPP NOTIFICATION] Erro ao enviar para %s: %s %s (tentativa %s/%s)",
                phone_normalized,
                response.status_code,
                response.text[:200],
                attempt + 1,
                max_retries,
            )
        except Exception as e:
            logger.warning(
                "⚠️ [WHATSAPP NOTIFICATION] Falha ao enviar para %s (tentativa %s/%s): %s",
                phone_normalized,
                attempt + 1,
                max_retries,
                e,
            )
        if attempt < max_retries - 1:
            time.sleep(base_delay * (2 ** attempt))
    return False


def send_websocket_notification(user, notification_type, data):
    """
    Envia notificação via WebSocket.
    
    ⚠️ NOTA: Esta função usa o sistema existente de WebSocket (Channels).
    Reutiliza a lógica de _notify_task_user do scheduler.
    
    Args:
        user: Instância de User
        notification_type: String com o tipo de notificação ('daily_summary', 'agenda_reminder', etc)
        data: Dict com os dados da notificação
    
    Returns:
        bool: True se enviado com sucesso
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning('⚠️ [WEBSOCKET NOTIFICATION] Channel layer não configurado')
            return False
        
        # Enviar para o grupo do tenant (padrão do sistema)
        group_name = f'tenant_{user.tenant_id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification',
                'notification_type': notification_type,
                'user_id': str(user.id),
                'data': data,
            }
        )
        
        logger.debug(f'📡 [WEBSOCKET NOTIFICATION] Notificação enviada para {user.email}: {notification_type}')
        return True
    
    except Exception as e:
        logger.error(f'❌ [WEBSOCKET NOTIFICATION] Erro ao enviar notificação WebSocket para {user.email}: {e}', exc_info=True)
        return False


def check_channels_enabled(preferences, user):
    """
    Verifica se pelo menos um canal de notificação está habilitado.
    
    Args:
        preferences: Instância de UserNotificationPreferences ou DepartmentNotificationPreferences
        user: Instância de User
    
    Returns:
        tuple: (has_whatsapp, has_websocket, has_email, has_any)
    """
    has_whatsapp = preferences.notify_via_whatsapp and user.notify_whatsapp
    has_websocket = preferences.notify_via_websocket
    has_email = preferences.notify_via_email
    has_any = has_whatsapp or has_websocket or has_email
    
    return has_whatsapp, has_websocket, has_email, has_any


def send_notifications(user, preferences, message, notification_type, data, context_name=''):
    """
    Envia notificações através de todos os canais habilitados.
    
    Args:
        user: Instância de User
        preferences: Instância de UserNotificationPreferences ou DepartmentNotificationPreferences
        message: String com a mensagem formatada (para WhatsApp/Email)
        notification_type: String com o tipo de notificação
        data: Dict com os dados da notificação (para WebSocket)
        context_name: String com contexto adicional para logs (ex: "departamento X")
    
    Returns:
        tuple: (notifications_sent, notifications_failed)
    """
    notifications_sent = 0
    notifications_failed = 0
    
    # Verificar canais habilitados
    has_whatsapp, has_websocket, has_email, has_any = check_channels_enabled(preferences, user)
    
    if not has_any:
        logger.debug(f'⏭️ [NOTIFICATIONS] Pulando {user.email} - Nenhum canal habilitado')
        return 0, 0
    
    # WhatsApp
    if has_whatsapp:
        try:
            success = send_whatsapp_notification(user, message)
            if success:
                notifications_sent += 1
            else:
                notifications_failed += 1
        except Exception as e:
            logger.error(f'❌ [NOTIFICATIONS] Erro ao enviar WhatsApp para {user.email} {context_name}: {e}', exc_info=True)
            notifications_failed += 1
    
    # WebSocket
    if has_websocket:
        try:
            success = send_websocket_notification(user, notification_type, data)
            if success:
                notifications_sent += 1
            else:
                notifications_failed += 1
        except Exception as e:
            logger.error(f'❌ [NOTIFICATIONS] Erro ao enviar WebSocket para {user.email} {context_name}: {e}', exc_info=True)
            notifications_failed += 1
    
    # Email (se implementado)
    if has_email:
        try:
            # TODO: Implementar envio de email
            logger.debug(f'📧 [NOTIFICATIONS] Email não implementado ainda para {user.email}')
        except Exception as e:
            logger.error(f'❌ [NOTIFICATIONS] Erro ao enviar Email para {user.email} {context_name}: {e}', exc_info=True)
            notifications_failed += 1
    
    return notifications_sent, notifications_failed


def calculate_time_window(current_time, window_minutes=1):
    """
    Calcula janela de tempo para verificação de notificações.
    
    Args:
        current_time: time object
        window_minutes: int - minutos de margem (±)
    
    Returns:
        tuple: (time_window_start, time_window_end)
    """
    from datetime import datetime, timedelta
    time_window_start = (datetime.combine(datetime.min, current_time) - timedelta(minutes=window_minutes)).time()
    time_window_end = (datetime.combine(datetime.min, current_time) + timedelta(minutes=window_minutes)).time()
    return time_window_start, time_window_end


def get_greeting():
    """
    Retorna saudação personalizada baseada no horário atual.
    
    Returns:
        str: "Bom dia", "Boa tarde" ou "Boa noite"
    """
    current_hour = timezone.localtime(timezone.now()).hour
    if 5 <= current_hour < 12:
        return "Bom dia"
    elif 12 <= current_hour < 18:
        return "Boa tarde"
    else:
        return "Boa noite"


def format_weekday_pt(date_obj):
    """
    Retorna nome do dia da semana em português.
    
    Args:
        date_obj: date object
    
    Returns:
        str: Nome do dia da semana em português
    """
    weekday = date_obj.strftime('%A')
    weekdays_pt = {
        'Monday': 'Segunda-feira',
        'Tuesday': 'Terça-feira',
        'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira',
        'Friday': 'Sexta-feira',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo',
    }
    return weekdays_pt.get(weekday, weekday)
