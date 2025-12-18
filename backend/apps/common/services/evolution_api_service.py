"""
Serviço centralizado para Evolution API

Features:
- Retry automático com backoff exponencial
- Health check de instância (opcional)
- Error handling robusto
- Logging estruturado
"""
from typing import Tuple, Dict, Any, Optional
from apps.notifications.models import WhatsAppInstance
import requests
import time
import logging

logger = logging.getLogger(__name__)


class EvolutionAPIService:
    """
    Serviço centralizado para comunicação com Evolution API
    
    Uso:
        service = EvolutionAPIService(instance)
        success, response = service.send_text_message(
            phone='+5511999999999',
            message='Olá!'
        )
    """
    
    # Timeouts padrão
    DEFAULT_TIMEOUT = 10  # segundos
    DEFAULT_MEDIA_TIMEOUT = 30  # segundos
    HEALTH_CHECK_TIMEOUT = 5  # segundos
    
    # Retry padrão
    DEFAULT_MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1  # segundo
    
    def __init__(self, instance: WhatsAppInstance):
        """
        Inicializa serviço com instância
        
        Args:
            instance: Instância da Evolution API (WhatsAppInstance model)
        
        Raises:
            ValueError: Se instância não tem configuração completa
        """
        self.instance = instance
        self.base_url = instance.api_url or ''
        self.api_key = instance.api_key or ''
        self.instance_name = instance.instance_name or ''
        self.instance_id = instance.id
        
        if not self.base_url or not self.api_key or not self.instance_name:
            raise ValueError(
                f"Instância {instance.id} não tem configuração completa. "
                f"Necessário: api_url, api_key, instance_name"
            )
    
    def send_text_message(
        self,
        phone: str,
        message: str,
        retry: bool = True,
        max_retries: int = None,
        timeout: int = None,
        quoted_message_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia mensagem de texto via Evolution API
        
        Args:
            phone: Telefone no formato E.164 (ex: +5511999999999)
                   Será normalizado automaticamente se não estiver no formato correto
            message: Texto da mensagem (máximo ~4096 caracteres)
            retry: Se True, tenta novamente em caso de falha temporária
            max_retries: Máximo de tentativas se retry=True (padrão: 3)
            timeout: Timeout em segundos para cada tentativa (padrão: 10s)
            quoted_message_id: ID da mensagem para responder (opcional)
        
        Returns:
            Tuple[bool, Dict[str, Any]]:
            - success (bool): True se enviou com sucesso
            - response (dict): Resposta da API ou dict com erro
        
        Raises:
            ValueError: Se phone ou message estão vazios
        """
        # Validações
        if not phone or not phone.strip():
            raise ValueError("phone não pode ser vazio")
        if not message or not message.strip():
            raise ValueError("message não pode ser vazio")
        
        # Normaliza telefone
        try:
            phone_normalized = self._normalize_phone(phone)
        except Exception as e:
            logger.error(
                f"Erro ao normalizar telefone {phone}: {e}",
                extra={
                    'instance_id': str(self.instance_id),
                    'instance_name': self.instance_name
                }
            )
            return False, {'error': f'Telefone inválido: {str(e)}', 'error_code': 'INVALID_PHONE'}
        
        # Prepara payload
        payload = self._prepare_payload(phone_normalized, message, quoted_message_id)
        
        # Endpoint
        endpoint = f"{self.base_url}/message/sendText/{self.instance_name}"
        headers = {
            'apikey': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # Configurações
        max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        timeout = timeout or self.DEFAULT_TIMEOUT
        
        # Retry com backoff exponencial
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(
                    f"Tentativa {attempt + 1}/{max_retries + 1} - "
                    f"Enviando para {phone_normalized} via {self.instance_name}",
                    extra={
                        'instance_id': str(self.instance_id),
                        'instance_name': self.instance_name,
                        'phone': phone_normalized,
                        'attempt': attempt + 1
                    }
                )
                
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                
                # Sucesso (200 ou 201)
                if response.status_code in [200, 201]:
                    response_data = response.json()
                    message_id = response_data.get('key', {}).get('id', 'N/A')
                    logger.info(
                        f"✅ Mensagem enviada com sucesso",
                        extra={
                            'instance_id': str(self.instance_id),
                            'instance_name': self.instance_name,
                            'phone': phone_normalized,
                            'message_id': message_id,
                            'status_code': response.status_code
                        }
                    )
                    return True, response_data
                
                # Erro 4xx (bad request) - não retenta
                if 400 <= response.status_code < 500:
                    error_msg = f"Bad request: {response.status_code} - {response.text}"
                    logger.error(
                        f"❌ Erro 4xx ao enviar mensagem: {error_msg}",
                        extra={
                            'instance_id': str(self.instance_id),
                            'instance_name': self.instance_name,
                            'phone': phone_normalized,
                            'status_code': response.status_code,
                            'response': response.text[:200]
                        }
                    )
                    return False, {
                        'error': error_msg,
                        'error_code': f'HTTP_{response.status_code}',
                        'status_code': response.status_code,
                        'response': response.text
                    }
                
                # Erro 5xx (server error) - retenta se configurado
                if response.status_code >= 500:
                    last_error = f"Server error: {response.status_code} - {response.text}"
                    logger.warning(
                        f"⚠️ Erro 5xx (tentativa {attempt + 1}/{max_retries + 1}): {last_error}",
                        extra={
                            'instance_id': str(self.instance_id),
                            'instance_name': self.instance_name,
                            'phone': phone_normalized,
                            'attempt': attempt + 1,
                            'status_code': response.status_code
                        }
                    )
                    # Continua para retry (se não for última tentativa)
                    if attempt < max_retries and retry:
                        delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                        logger.info(
                            f"⏳ Aguardando {delay}s antes de retry...",
                            extra={
                                'instance_id': str(self.instance_id),
                                'delay': delay,
                                'attempt': attempt + 1
                            }
                        )
                        time.sleep(delay)
                        continue
                    else:
                        return False, {
                            'error': last_error,
                            'error_code': f'HTTP_{response.status_code}',
                            'status_code': response.status_code,
                            'attempts': attempt + 1
                        }
            
            except requests.Timeout as e:
                last_error = f"Timeout após {timeout}s"
                logger.warning(
                    f"⏱️ Timeout (tentativa {attempt + 1}/{max_retries + 1}): {last_error}",
                    extra={
                        'instance_id': str(self.instance_id),
                        'instance_name': self.instance_name,
                        'phone': phone_normalized,
                        'attempt': attempt + 1,
                        'timeout': timeout
                    }
                )
                if attempt < max_retries and retry:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.info(
                        f"⏳ Aguardando {delay}s antes de retry...",
                        extra={
                            'instance_id': str(self.instance_id),
                            'delay': delay,
                            'attempt': attempt + 1
                        }
                    )
                    time.sleep(delay)
                    continue
                else:
                    return False, {
                        'error': last_error,
                        'error_code': 'TIMEOUT',
                        'attempts': attempt + 1
                    }
            
            except requests.ConnectionError as e:
                last_error = f"Connection error: {str(e)}"
                logger.warning(
                    f"🔌 Connection error (tentativa {attempt + 1}/{max_retries + 1}): {last_error}",
                    extra={
                        'instance_id': str(self.instance_id),
                        'instance_name': self.instance_name,
                        'phone': phone_normalized,
                        'attempt': attempt + 1
                    }
                )
                if attempt < max_retries and retry:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.info(
                        f"⏳ Aguardando {delay}s antes de retry...",
                        extra={
                            'instance_id': str(self.instance_id),
                            'delay': delay,
                            'attempt': attempt + 1
                        }
                    )
                    time.sleep(delay)
                    continue
                else:
                    return False, {
                        'error': last_error,
                        'error_code': 'CONNECTION_ERROR',
                        'attempts': attempt + 1
                    }
            
            except Exception as e:
                # Erro inesperado - não retenta
                logger.error(
                    f"❌ Erro inesperado ao enviar mensagem: {e}",
                    exc_info=True,
                    extra={
                        'instance_id': str(self.instance_id),
                        'instance_name': self.instance_name,
                        'phone': phone_normalized,
                        'attempt': attempt + 1
                    }
                )
                return False, {
                    'error': str(e),
                    'error_code': 'UNEXPECTED_ERROR',
                    'attempts': attempt + 1
                }
        
        # Se chegou aqui, todas as tentativas falharam
        logger.error(
            f"❌ Todas as tentativas falharam após {max_retries + 1} tentativas",
            extra={
                'instance_id': str(self.instance_id),
                'instance_name': self.instance_name,
                'phone': phone_normalized,
                'attempts': max_retries + 1,
                'last_error': last_error
            }
        )
        return False, {
            'error': last_error or 'Unknown error',
            'error_code': 'MAX_RETRIES_EXCEEDED',
            'attempts': max_retries + 1
        }
    
    def check_health(self) -> Tuple[bool, str]:
        """
        Verifica se instância está saudável e conectada
        
        Returns:
            Tuple[bool, str]:
            - is_healthy (bool): True se instância está OK
            - reason (str): Motivo se não estiver saudável, "OK" se saudável
        """
        try:
            endpoint = f"{self.base_url}/instance/connectionState/{self.instance_name}"
            headers = {'apikey': self.api_key}
            
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=self.HEALTH_CHECK_TIMEOUT
            )
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            data = response.json()
            state = data.get('state', '').lower()
            
            # Estados válidos: 'open', 'connecting' (temporário)
            if state == 'open':
                return True, "OK"
            elif state == 'connecting':
                return False, "Conectando (aguardando)"
            else:
                return False, f"State: {state}"
        
        except requests.Timeout:
            return False, "Timeout ao verificar health"
        except requests.ConnectionError:
            return False, "Erro de conexão"
        except Exception as e:
            logger.error(
                f"Erro ao verificar health: {e}",
                exc_info=True,
                extra={
                    'instance_id': str(self.instance_id),
                    'instance_name': self.instance_name
                }
            )
            return False, f"Erro inesperado: {str(e)}"
    
    def _normalize_phone(self, phone: str) -> str:
        """
        Normaliza telefone usando utils existente
        
        Args:
            phone: Telefone em qualquer formato
        
        Returns:
            Telefone no formato E.164 (ex: +5511999999999)
        
        Raises:
            ValueError: Se telefone inválido
        """
        from apps.contacts.utils import normalize_phone
        return normalize_phone(phone)
    
    def _prepare_payload(
        self,
        phone: str,
        message: str,
        quoted_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepara payload para Evolution API
        
        Args:
            phone: Telefone normalizado
            message: Texto da mensagem
            quoted_message_id: ID da mensagem para responder (opcional)
        
        Returns:
            Dict com payload formatado
        """
        # Remove + do telefone para Evolution API
        phone_clean = phone.replace('+', '')
        
        payload = {
            'number': phone_clean,
            'text': message
        }
        
        # Se é reply, adiciona quoted
        if quoted_message_id:
            payload['quoted'] = {
                'key': {
                    'id': quoted_message_id,
                    'remoteJid': f'{phone_clean}@s.whatsapp.net'
                }
            }
        
        return payload



