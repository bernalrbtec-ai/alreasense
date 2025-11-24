"""
Serviços para envio de notificações personalizadas.
Reutiliza o sistema existente de WhatsApp e WebSocket.
"""

import logging
import re
import requests
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
    phone = user.phone
    if not phone:
        raise ValueError(f"Usuário {user.email} não tem telefone cadastrado")
    
    # ✅ VALIDAÇÃO: Verificar se telefone tem formato mínimo válido (pelo menos 10 dígitos)
    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) < 10:
        raise ValueError(f"Telefone do usuário {user.email} é inválido: {phone}")
    
    # ✅ NORMALIZAÇÃO: Garantir formato E.164
    phone_normalized = normalize_phone(phone)
    if not phone_normalized:
        raise ValueError(f"Telefone do usuário {user.email} não pôde ser normalizado: {phone}")
    
    # Buscar instância WhatsApp ativa do tenant
    instance = WhatsAppInstance.objects.filter(
        tenant=user.tenant,
        is_active=True,
        status='active'
    ).first()
    
    if not instance:
        logger.warning(f'⚠️ [WHATSAPP NOTIFICATION] Nenhuma instância WhatsApp ativa para tenant {user.tenant_id}')
        raise ValueError(f"Nenhuma instância WhatsApp ativa para tenant {user.tenant.name}")
    
    # ✅ MELHORIA: Usar api_url e api_key da instância diretamente
    base_url = instance.api_url
    api_key = instance.api_key
    
    if not base_url or not api_key:
        # Fallback: buscar EvolutionConnection
        connection = EvolutionConnection.objects.filter(
            tenant=user.tenant,
            is_active=True
        ).first()
        
        if connection:
            base_url = connection.base_url
            api_key = connection.api_key
        else:
            # Buscar conexão global (sem tenant)
            connection = EvolutionConnection.objects.filter(
                is_active=True
            ).first()
            
            if connection:
                base_url = connection.base_url
                api_key = connection.api_key
    
    if not base_url or not api_key:
        logger.warning(f'⚠️ [WHATSAPP NOTIFICATION] API URL ou API Key não configurados para tenant {user.tenant_id}')
        raise ValueError(f"API URL ou API Key não configurados para tenant {user.tenant.name}")
    
    # ✅ MELHORIA: Usar instance_name da instância e base_url normalizado
    base_url = base_url.rstrip('/')
    url = f"{base_url}/message/sendText/{instance.instance_name}"
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
                    import time
                    time.sleep(delay)
                else:
                    raise Exception(f"Falha após {max_retries} tentativas: {error_msg}")
        
        except requests.exceptions.Timeout:
            logger.warning(f'⏱️ [WHATSAPP NOTIFICATION] Timeout na tentativa {attempt + 1}/{max_retries}')
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                import time
                time.sleep(delay)
            else:
                raise Exception("Timeout após múltiplas tentativas")
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f'🔌 [WHATSAPP NOTIFICATION] Erro de conexão na tentativa {attempt + 1}/{max_retries}: {e}')
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                import time
                time.sleep(delay)
            else:
                raise Exception(f"Erro de conexão após múltiplas tentativas: {e}")
        
        except Exception as e:
            logger.error(f'❌ [WHATSAPP NOTIFICATION] Erro inesperado na tentativa {attempt + 1}/{max_retries}: {e}', exc_info=True)
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                import time
                time.sleep(delay)
            else:
                raise
    
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

