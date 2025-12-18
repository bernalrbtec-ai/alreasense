# 🔧 **EVOLUTION API SERVICE - ESPECIFICAÇÃO COMPLETA**

> **Serviço Centralizado para Evolution API**  
> **Versão:** 1.0  
> **Status:** Aprovado para implementação  
> **Primeiro uso:** Sistema de Billing

---

## 📋 **ÍNDICE**

1. [Visão Geral](#visão-geral)
2. [Decisão Arquitetural](#decisão-arquitetural)
3. [Estrutura do Serviço](#estrutura-do-serviço)
4. [API Detalhada](#api-detalhada)
5. [Implementação](#implementação)
6. [Testes](#testes)
7. [Migração Gradual](#migração-gradual)
8. [Roadmap Futuro](#roadmap-futuro)

---

## 🎯 **VISÃO GERAL**

### **O Que É?**

Serviço centralizado que encapsula toda a comunicação com a Evolution API, fornecendo uma interface limpa e consistente para envio de mensagens via WhatsApp.

### **Por Que Centralizar?**

**Problema atual:**
- ❌ Código duplicado em 3+ lugares (campanhas, chat, notificações, billing)
- ❌ Retry logic espalhado
- ❌ Difícil adicionar melhorias (health check, circuit breaker, métricas)
- ❌ Inconsistências entre implementações

**Solução:**
- ✅ Single source of truth
- ✅ Manutenção centralizada
- ✅ Facilita melhorias futuras
- ✅ Código mais testável
- ✅ Interface consistente

---

## 🏗️ **DECISÃO ARQUITETURAL**

### **✅ DECISÃO APROVADA:**

**Criar serviço centralizado AGORA e usar em:**
1. ✅ **Billing** (primeiro uso - sistema novo)
2. ⏳ **Campanhas** (migrar depois - PR separado)
3. ⏳ **Chat** (migrar depois - PR separado)
4. ⏳ **Notificações** (migrar depois - PR separado)

**Localização:**
```
apps/common/services/evolution_api_service.py
```

**Motivos:**
- ✅ Billing é novo → começar certo desde o início
- ✅ Investimento pequeno (1-2 dias) com retorno alto
- ✅ Migração gradual é segura
- ✅ Não quebra código existente

---

## 📦 **ESTRUTURA DO SERVIÇO**

### **Arquivo:** `apps/common/services/evolution_api_service.py`

```python
"""
Serviço centralizado para Evolution API

Features:
- Retry automático com backoff exponencial
- Health check de instância (opcional)
- Rate limiting por instância (futuro)
- Métricas Prometheus (futuro)
- Circuit breaker (futuro)
- Error handling robusto
- Logging estruturado
"""

from typing import Tuple, Dict, Any, Optional
from apps.whatsapp.models import Instance  # ou apps.notifications.models
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
    
    def __init__(self, instance: Instance):
        """
        Inicializa serviço com instância
        
        Args:
            instance: Instância da Evolution API (Instance model)
        """
        self.instance = instance
        self.base_url = instance.api_url  # ou instance.evolution_url
        self.api_key = instance.api_key  # ou instance.evolution_api_key
        self.instance_name = instance.instance_name  # ou instance.name
        self.instance_id = instance.id
    
    # ... métodos abaixo ...
```

---

## 🔌 **API DETALHADA**

### **1. send_text_message()**

```python
def send_text_message(
    self,
    phone: str,
    message: str,
    retry: bool = True,
    max_retries: int = 3,
    timeout: int = 10,
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
        
        Exemplo de sucesso:
            (True, {
                'key': {'id': '3EB0123456789ABCDEF', 'remoteJid': '5511999999999@s.whatsapp.net'},
                'message': {...},
                'status': 200
            })
        
        Exemplo de erro:
            (False, {
                'error': 'Connection timeout',
                'error_code': 'TIMEOUT',
                'attempts': 3
            })
    
    Raises:
        ValueError: Se phone ou message estão vazios
        ConnectionError: Se não consegue conectar (após todas as tentativas)
    
    Examples:
        >>> service = EvolutionAPIService(instance)
        >>> success, response = service.send_text_message(
        ...     phone='+5511999999999',
        ...     message='Olá!'
        ... )
        >>> if success:
        ...     message_id = response['key']['id']
        ...     print(f"Mensagem enviada: {message_id}")
    """
    pass
```

**Comportamento:**
1. Valida inputs (phone não vazio, message não vazia)
2. Normaliza telefone (usa `apps/contacts/utils.py::normalize_phone`)
3. Prepara payload (com quoted se fornecido)
4. Tenta enviar com retry e backoff exponencial
5. Retorna (success, response)

**Retry Strategy:**
- Backoff exponencial: 1s, 2s, 4s (se max_retries=3)
- Apenas para erros temporários (Timeout, ConnectionError)
- Erros 4xx (bad request) não retenta

---

### **2. send_media_message()** (Futuro)

```python
def send_media_message(
    self,
    phone: str,
    media_url: str,
    caption: Optional[str] = None,
    media_type: str = 'image',  # 'image', 'video', 'document', 'audio'
    retry: bool = True,
    max_retries: int = 3,
    timeout: int = 30
) -> Tuple[bool, Dict[str, Any]]:
    """
    Envia mídia via Evolution API (futuro - v1.1)
    
    Args:
        phone: Telefone no formato E.164
        media_url: URL da mídia (deve ser acessível pela Evolution API)
        caption: Legenda da mídia (opcional)
        media_type: Tipo de mídia ('image', 'video', 'document', 'audio')
        retry: Se True, tenta novamente
        max_retries: Máximo de tentativas
        timeout: Timeout em segundos (maior para mídia: 30s)
    
    Returns:
        Tuple[bool, Dict[str, Any]]
    """
    pass
```

---

### **3. check_health()**

```python
def check_health(self) -> Tuple[bool, str]:
    """
    Verifica se instância está saudável e conectada
    
    Returns:
        Tuple[bool, str]:
        - is_healthy (bool): True se instância está OK
        - reason (str): Motivo se não estiver saudável, "OK" se saudável
    
    Examples:
        >>> service = EvolutionAPIService(instance)
        >>> is_ok, reason = service.check_health()
        >>> if not is_ok:
        ...     print(f"Instância offline: {reason}")
        ...     # Pausar envios, aguardar recovery, etc.
    """
    pass
```

**Implementação:**
- Endpoint: `{base_url}/instance/connectionState/{instance_name}`
- Timeout: 5 segundos
- Cache: 30 segundos (evitar checks excessivos)

---

### **4. _normalize_phone()** (Privado)

```python
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
```

---

### **5. _prepare_payload()** (Privado)

```python
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
```

---

## 💻 **IMPLEMENTAÇÃO**

### **Código Completo:**

```python
# apps/common/services/evolution_api_service.py

"""
Serviço centralizado para Evolution API
"""
from typing import Tuple, Dict, Any, Optional
from apps.whatsapp.models import Instance  # Ajustar import conforme model
import requests
import time
import logging

logger = logging.getLogger(__name__)


class EvolutionAPIService:
    """Serviço centralizado para comunicação com Evolution API"""
    
    # Timeouts padrão
    DEFAULT_TIMEOUT = 10  # segundos
    DEFAULT_MEDIA_TIMEOUT = 30  # segundos
    HEALTH_CHECK_TIMEOUT = 5  # segundos
    
    # Retry padrão
    DEFAULT_MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1  # segundo
    
    def __init__(self, instance: Instance):
        """
        Inicializa serviço com instância
        
        Args:
            instance: Instância da Evolution API
        """
        self.instance = instance
        # Ajustar conforme campos do model Instance
        self.base_url = getattr(instance, 'api_url', None) or getattr(instance, 'evolution_url', '')
        self.api_key = getattr(instance, 'api_key', None) or getattr(instance, 'evolution_api_key', '')
        self.instance_name = getattr(instance, 'instance_name', None) or getattr(instance, 'name', '')
        self.instance_id = instance.id
        
        if not self.base_url or not self.api_key or not self.instance_name:
            raise ValueError(
                f"Instância {instance.id} não tem configuração completa. "
                f"Necessário: base_url, api_key, instance_name"
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
        
        Returns:
            (success: bool, response: dict)
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
            logger.error(f"Erro ao normalizar telefone {phone}: {e}")
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
                    f"Enviando para {phone_normalized} via {self.instance_name}"
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
                    logger.info(
                        f"✅ Mensagem enviada com sucesso - "
                        f"Phone: {phone_normalized}, Instance: {self.instance_name}, "
                        f"Message ID: {response_data.get('key', {}).get('id', 'N/A')}"
                    )
                    return True, response_data
                
                # Erro 4xx (bad request) - não retenta
                if 400 <= response.status_code < 500:
                    error_msg = f"Bad request: {response.status_code} - {response.text}"
                    logger.error(
                        f"❌ Erro 4xx ao enviar mensagem: {error_msg} - "
                        f"Phone: {phone_normalized}, Instance: {self.instance_name}"
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
                        f"⚠️ Erro 5xx (tentativa {attempt + 1}/{max_retries + 1}): {last_error}"
                    )
                    # Continua para retry (se não for última tentativa)
                    if attempt < max_retries and retry:
                        delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                        logger.info(f"⏳ Aguardando {delay}s antes de retry...")
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
                    f"⏱️ Timeout (tentativa {attempt + 1}/{max_retries + 1}): {last_error}"
                )
                if attempt < max_retries and retry:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.info(f"⏳ Aguardando {delay}s antes de retry...")
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
                    f"🔌 Connection error (tentativa {attempt + 1}/{max_retries + 1}): {last_error}"
                )
                if attempt < max_retries and retry:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.info(f"⏳ Aguardando {delay}s antes de retry...")
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
                        'phone': phone_normalized,
                        'instance_name': self.instance_name,
                        'instance_id': str(self.instance_id)
                    }
                )
                return False, {
                    'error': str(e),
                    'error_code': 'UNEXPECTED_ERROR',
                    'attempts': attempt + 1
                }
        
        # Se chegou aqui, todas as tentativas falharam
        logger.error(
            f"❌ Todas as tentativas falharam após {max_retries + 1} tentativas - "
            f"Phone: {phone_normalized}, Instance: {self.instance_name}, "
            f"Último erro: {last_error}"
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
            (is_healthy: bool, reason: str)
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
            logger.error(f"Erro ao verificar health: {e}", exc_info=True)
            return False, f"Erro inesperado: {str(e)}"
    
    def _normalize_phone(self, phone: str) -> str:
        """Normaliza telefone usando utils existente"""
        from apps.contacts.utils import normalize_phone
        return normalize_phone(phone)
    
    def _prepare_payload(
        self,
        phone: str,
        message: str,
        quoted_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Prepara payload para Evolution API"""
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
```

---

## 🧪 **TESTES**

### **Arquivo:** `apps/common/tests/test_evolution_api_service.py`

```python
"""
Testes para EvolutionAPIService
"""
from django.test import TestCase
from unittest.mock import patch, Mock
from apps.common.services.evolution_api_service import EvolutionAPIService
from apps.whatsapp.models import Instance  # Ajustar import


class EvolutionAPIServiceTest(TestCase):
    def setUp(self):
        """Cria instância de teste"""
        self.instance = Instance.objects.create(
            api_url='https://evolution-api.example.com',
            api_key='test-key-123',
            instance_name='test-instance',
            # ... outros campos necessários
        )
        self.service = EvolutionAPIService(self.instance)
    
    @patch('apps.common.services.evolution_api_service.requests.post')
    def test_send_text_message_success(self, mock_post):
        """Testa envio bem-sucedido"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'key': {'id': 'msg-123', 'remoteJid': '5511999999999@s.whatsapp.net'},
            'message': {}
        }
        mock_post.return_value = mock_response
        
        # Testa
        success, response = self.service.send_text_message(
            phone='+5511999999999',
            message='Olá!'
        )
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(response['key']['id'], 'msg-123')
        mock_post.assert_called_once()
    
    @patch('apps.common.services.evolution_api_service.requests.post')
    def test_send_text_message_retry_on_timeout(self, mock_post):
        """Testa retry em caso de timeout"""
        # Mock timeout na primeira tentativa, sucesso na segunda
        mock_post.side_effect = [
            requests.Timeout("Timeout"),
            Mock(status_code=200, json=lambda: {'key': {'id': 'msg-123'}})
        ]
        
        # Testa
        success, response = self.service.send_text_message(
            phone='+5511999999999',
            message='Olá!',
            max_retries=3
        )
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(mock_post.call_count, 2)  # Retentou uma vez
    
    def test_normalize_phone(self):
        """Testa normalização de telefone"""
        # Testa vários formatos
        test_cases = [
            ('11999999999', '+5511999999999'),
            ('(11) 99999-9999', '+5511999999999'),
            ('+5511999999999', '+5511999999999'),
            ('5511999999999', '+5511999999999'),
        ]
        
        for input_phone, expected in test_cases:
            with self.subTest(phone=input_phone):
                normalized = self.service._normalize_phone(input_phone)
                self.assertEqual(normalized, expected)
    
    @patch('apps.common.services.evolution_api_service.requests.get')
    def test_check_health_online(self, mock_get):
        """Testa health check quando instância está online"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'state': 'open'}
        mock_get.return_value = mock_response
        
        is_healthy, reason = self.service.check_health()
        
        self.assertTrue(is_healthy)
        self.assertEqual(reason, "OK")
    
    @patch('apps.common.services.evolution_api_service.requests.get')
    def test_check_health_offline(self, mock_get):
        """Testa health check quando instância está offline"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'state': 'close'}
        mock_get.return_value = mock_response
        
        is_healthy, reason = self.service.check_health()
        
        self.assertFalse(is_healthy)
        self.assertIn('State:', reason)
```

---

## 🔄 **MIGRAÇÃO GRADUAL**

### **Fase 1: Criar e Usar em Billing (AGORA)**

**Timeline:** Durante implementação de billing

**Ações:**
1. ✅ Criar `apps/common/services/evolution_api_service.py`
2. ✅ Implementar `send_text_message()` com retry
3. ✅ Implementar `check_health()` (opcional, mas recomendado)
4. ✅ Testes unitários
5. ✅ Usar em `BillingSendService` desde o início

**Resultado:**
- ✅ Billing usa serviço centralizado
- ✅ Código limpo desde o início
- ✅ Testado e estável

---

### **Fase 2: Migrar Campanhas (DEPOIS)**

**Critérios:**
- ✅ Billing funcionando bem em produção (1-2 semanas)
- ✅ Serviço testado e estável
- ✅ Tempo disponível para refatoração

**Ações:**
1. Criar PR separado
2. Refatorar `apps/campaigns/services.py::CampaignSender`
3. Substituir código direto por `EvolutionAPIService`
4. Testar bem (regressão)
5. Deploy gradual (feature flag opcional)

**Código Antes:**
```python
# apps/campaigns/services.py (linha 354-393)
url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
headers = {'apikey': instance.api_key, 'Content-Type': 'application/json'}
payload = {'number': phone, 'text': message_text}
# ... retry logic ...
response = requests.post(url, json=payload, headers=headers, timeout=10)
```

**Código Depois:**
```python
# apps/campaigns/services.py
from apps.common.services.evolution_api_service import EvolutionAPIService

evolution = EvolutionAPIService(instance)
success, response = evolution.send_text_message(
    phone=phone,
    message=message_text
)
if success:
    # Processa sucesso
else:
    # Processa erro
```

---

### **Fase 3: Migrar Chat (DEPOIS)**

**Critérios:**
- ✅ Campanhas migradas e funcionando
- ✅ Serviço consolidado

**Ações:**
1. Criar PR separado
2. Refatorar `apps/chat/tasks.py::send_message_to_evolution`
3. Testar bem (mais crítico - chat em tempo real)
4. Deploy cuidadoso

---

### **Fase 4: Migrar Notificações (DEPOIS)**

**Critérios:**
- ✅ Chat migrado e funcionando
- ✅ Todos os módulos principais migrados

**Ações:**
1. Criar PR separado
2. Refatorar `apps/notifications/services.py::send_whatsapp_notification`
3. Testar
4. Deploy

---

## 🚀 **ROADMAP FUTURO**

### **v1.1 (Próximas melhorias)**

- [ ] `send_media_message()` - Envio de mídia
- [ ] `send_template_message()` - Mensagens template (business)
- [ ] `get_instance_info()` - Informações da instância
- [ ] `restart_instance()` - Reiniciar instância
- [ ] Circuit breaker (pausa automática se muitas falhas)
- [ ] Rate limiting por instância (evitar sobrecarga)
- [ ] Métricas Prometheus detalhadas

### **v1.2 (Melhorias avançadas)**

- [ ] Pool de conexões HTTP (requests.Session reutilizado)
- [ ] Cache de health checks (Redis)
- [ ] Retry inteligente (exponential backoff + jitter)
- [ ] Suporte a múltiplas Evolution API URLs (load balancing)
- [ ] Webhook retry automático

### **v1.3 (Integração)**

- [ ] Suporte a outros provedores (Twilio, etc.)
- [ ] Abstração de provider (interface comum)
- [ ] Migração entre provedores transparente

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO**

### **Criar Serviço (1-2 dias)**

- [ ] Criar arquivo `apps/common/services/evolution_api_service.py`
- [ ] Implementar `__init__()` com validações
- [ ] Implementar `send_text_message()` com retry
- [ ] Implementar `check_health()` (opcional)
- [ ] Implementar `_normalize_phone()` (wrapper)
- [ ] Implementar `_prepare_payload()` (helper)
- [ ] Documentar todos os métodos
- [ ] Criar testes unitários (>90% coverage)
- [ ] Testar com instância real (dev)
- [ ] Atualizar `BILLING_SYSTEM_RULES.md` com referência

### **Integrar em Billing (durante Fase 3)**

- [ ] Importar em `BillingSendService`
- [ ] Substituir código direto por serviço
- [ ] Testar envio de mensagens
- [ ] Testar retry em falhas
- [ ] Testar health check (se implementado)
- [ ] Verificar logs
- [ ] Atualizar documentação

### **Preparar Migração Futura**

- [ ] Documentar padrão atual (campanhas, chat, notificações)
- [ ] Criar issue no GitHub: "Migrar campanhas para EvolutionAPIService"
- [ ] Criar issue: "Migrar chat para EvolutionAPIService"
- [ ] Criar issue: "Migrar notificações para EvolutionAPIService"

---

## 📝 **NOTAS IMPORTANTES**

### **⚠️ ATENÇÃO: Ajustar Imports Conforme Model**

O model `Instance` pode estar em:
- `apps.whatsapp.models.Instance`
- `apps.notifications.models.WhatsAppInstance`
- Outro local

**Ação:** Verificar localização real antes de implementar!

```python
# Verificar primeiro:
from apps.whatsapp.models import Instance  # Tentar primeiro
# OU
from apps.notifications.models import WhatsAppInstance as Instance

# Ajustar campos conforme model:
self.base_url = instance.api_url or instance.evolution_url
self.api_key = instance.api_key or instance.evolution_api_key
```

### **⚠️ ATENÇÃO: Endpoint da Evolution API**

Verificar endpoint exato usado no projeto:
- `/message/sendText/{instance_name}` (mais comum)
- `/v1/message/sendText/{instance_name}` (se versionado)
- Outro formato?

**Ação:** Verificar código existente em campanhas/chat para confirmar!

---

## 🎯 **CONCLUSÃO**

Este serviço será:
- ✅ **Base sólida** para comunicação com Evolution API
- ✅ **Reutilizável** por todos os módulos
- ✅ **Evolutivo** (fácil adicionar melhorias)
- ✅ **Testável** (interface limpa, mocks fáceis)
- ✅ **Manutenível** (single source of truth)

**Próximo passo:** Implementar durante Fase 3 do billing (Services)

---

**Última atualização:** Dezembro 2025  
**Status:** Aprovado para implementação
