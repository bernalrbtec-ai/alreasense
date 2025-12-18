# 🚀 **GUIA DE IMPLEMENTAÇÃO - BILLING SYSTEM (PARTE 2)**

> **Complemento do BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md**  
> Esta parte contém: APIs, Serializers, Services, Frontend, Observabilidade, Troubleshooting e FAQ

---

## 📋 **ÍNDICE PARTE 2**

1. [Services Completos](#services-completos)
2. [APIs e Endpoints](#apis-e-endpoints)
3. [Serializers](#serializers)
4. [Frontend Dashboard](#frontend-dashboard)
5. [Observabilidade](#observabilidade)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)
8. [Exemplos de Uso](#exemplos-de-uso)

---

## 🔧 **SERVICES COMPLETOS**

### **1. Business Hours Scheduler** (`schedulers/business_hours_scheduler.py`)

```python
"""
Scheduler de horário comercial
"""
from datetime import datetime, timedelta, time
from django.utils import timezone
from apps.chat.models import BusinessHours
from apps.tenancy.models import Tenant
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BillingBusinessHoursScheduler:
    """Gerencia agendamento baseado em horário comercial"""
    
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
        if not check_time:
            check_time = timezone.now()
        
        day_of_week = check_time.weekday()
        current_time = check_time.time()
        
        business_hours = BusinessHours.objects.filter(
            tenant=tenant,
            is_active=True,
            day_of_week=day_of_week
        )
        
        for bh in business_hours:
            if bh.start_time <= current_time <= bh.end_time:
                return True
        
        return False
    
    @staticmethod
    def get_next_valid_datetime(tenant: Tenant) -> datetime:
        """
        Retorna próximo horário válido (dentro do horário comercial)
        
        Returns:
            datetime do próximo horário comercial disponível
        """
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        
        # Busca próximos 7 dias
        for days_ahead in range(8):  # Hoje + 7 dias
            check_date = current_date + timedelta(days=days_ahead)
            day_of_week = check_date.weekday()
            
            business_hours = BusinessHours.objects.filter(
                tenant=tenant,
                is_active=True,
                day_of_week=day_of_week
            ).order_by('start_time')
            
            for bh in business_hours:
                # Se é hoje, precisa ser no futuro
                if days_ahead == 0:
                    if bh.start_time > current_time:
                        return timezone.make_aware(
                            datetime.combine(check_date, bh.start_time)
                        )
                else:
                    # Próximos dias, usa o primeiro horário
                    return timezone.make_aware(
                        datetime.combine(check_date, bh.start_time)
                    )
        
        # Fallback: amanhã às 9h
        tomorrow = current_date + timedelta(days=1)
        return timezone.make_aware(
            datetime.combine(tomorrow, time(9, 0))
        )
    
    @staticmethod
    def calculate_delay_until_next_hours(tenant: Tenant) -> int:
        """
        Calcula delay em segundos até próximo horário comercial
        
        Returns:
            Segundos até próximo horário válido
        """
        now = timezone.now()
        next_valid = BillingBusinessHoursScheduler.get_next_valid_datetime(tenant)
        delay = (next_valid - now).total_seconds()
        
        return max(int(delay), 0)
```

---

### **2. Billing Campaign Service** (`services/billing_campaign_service.py`)

```python
"""
Orchestrator de campanhas de billing
"""
from django.db import transaction
from django.utils import timezone
from apps.billing.models import (
    BillingCampaign, BillingQueue, BillingContact, BillingTemplate,
    QueueStatus
)
from apps.billing.utils.date_calculator import BillingDateCalculator
from apps.billing.utils.phone_validator import PhoneValidator
from apps.campaigns.models import Campaign, CampaignContact, CampaignType
from apps.contacts.models import Contact
from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class BillingCampaignService:
    """
    Serviço orquestrador de campanhas de billing
    
    Responsabilidades:
    - Validar dados recebidos
    - Enriquecer variáveis (calcular dias, etc)
    - Criar Campaign + BillingCampaign
    - Criar contatos
    - Selecionar variações de template
    - Criar BillingQueue
    - Publicar no RabbitMQ
    """
    
    def __init__(self, tenant, api_key=None):
        self.tenant = tenant
        self.api_key = api_key
        self.config = tenant.billing_config
    
    @transaction.atomic
    def create_billing_campaign(
        self,
        template_type: str,
        contacts_data: List[Dict[str, Any]],
        external_id: str,
        callback_url: str = '',
        metadata: Dict[str, Any] = None
    ) -> Tuple[bool, BillingCampaign, str]:
        """
        Cria campanha de billing completa
        
        Args:
            template_type: 'overdue' | 'upcoming' | 'notification'
            contacts_data: [{"nome": "João", "telefone": "+5511999999999", ...}, ...]
            external_id: ID no sistema do cliente
            callback_url: URL para notificar eventos
            metadata: Dados extras
        
        Returns:
            (sucesso, billing_campaign, mensagem_erro)
        """
        try:
            # 1. Validações iniciais
            valid, error = self._validate_request(
                template_type,
                contacts_data,
                external_id
            )
            if not valid:
                return False, None, error
            
            # 2. Busca template
            template = self._get_template(template_type)
            if not template:
                return False, None, f"Template '{template_type}' não encontrado"
            
            # 3. Valida limite de mensagens
            if len(contacts_data) > self.config.max_batch_size:
                return False, None, (
                    f"Limite de {self.config.max_batch_size} mensagens "
                    f"excedido ({len(contacts_data)} enviadas)"
                )
            
            # 4. Valida limite diário
            if not self._check_daily_limit(len(contacts_data)):
                return False, None, "Limite diário de mensagens atingido"
            
            # 5. Cria Campaign base
            campaign = self._create_base_campaign(
                template,
                len(contacts_data),
                metadata or {}
            )
            
            # 6. Cria BillingCampaign
            billing_campaign = BillingCampaign.objects.create(
                tenant=self.tenant,
                template=template,
                campaign=campaign,
                external_id=external_id,
                external_data={'contacts': contacts_data},
                callback_url=callback_url,
                callback_events=['sent', 'delivered', 'failed', 'replied']
            )
            
            # 7. Cria BillingQueue
            queue = BillingQueue.objects.create(
                billing_campaign=billing_campaign,
                status=QueueStatus.PENDING,
                total_contacts=len(contacts_data)
            )
            
            # 8. Cria contatos (em batch)
            contacts = self._create_contacts(
                billing_campaign,
                campaign,
                template,
                contacts_data
            )
            
            logger.info(
                f"✅ Billing campaign criada: {billing_campaign.id} "
                f"({len(contacts)} contatos)"
            )
            
            # 9. Publica no RabbitMQ para processamento
            from apps.billing.rabbitmq.billing_publisher import BillingQueuePublisher
            import asyncio
            
            asyncio.run(
                BillingQueuePublisher.publish_queue(
                    str(queue.id),
                    template_type
                )
            )
            
            return True, billing_campaign, "Campanha criada com sucesso"
        
        except Exception as e:
            logger.error(f"❌ Erro ao criar billing campaign: {e}", exc_info=True)
            return False, None, f"Erro interno: {str(e)}"
    
    def _validate_request(
        self,
        template_type: str,
        contacts_data: List[Dict],
        external_id: str
    ) -> Tuple[bool, str]:
        """Validações gerais"""
        
        # Verifica se API está habilitada
        if not self.config.api_enabled:
            return False, "API de Billing não habilitada para este tenant"
        
        # Verifica template_type
        valid_types = ['overdue', 'upcoming', 'notification']
        if template_type not in valid_types:
            return False, f"template_type inválido. Use: {', '.join(valid_types)}"
        
        # Verifica contatos
        if not contacts_data or len(contacts_data) == 0:
            return False, "Lista de contatos vazia"
        
        # Verifica external_id
        if not external_id or external_id.strip() == '':
            return False, "external_id obrigatório"
        
        # Verifica duplicidade de external_id
        if BillingCampaign.objects.filter(
            tenant=self.tenant,
            external_id=external_id
        ).exists():
            return False, f"external_id '{external_id}' já existe"
        
        return True, ""
    
    def _get_template(self, template_type: str) -> BillingTemplate:
        """Busca template ativo"""
        return BillingTemplate.objects.filter(
            tenant=self.tenant,
            template_type=template_type,
            is_active=True
        ).first()
    
    def _check_daily_limit(self, count: int) -> bool:
        """Verifica limite diário"""
        if self.config.daily_message_limit == 0:
            return True  # Ilimitado
        
        # Conta mensagens enviadas hoje
        today = timezone.now().date()
        sent_today = BillingContact.objects.filter(
            billing_campaign__tenant=self.tenant,
            created_at__date=today
        ).count()
        
        return (sent_today + count) <= self.config.daily_message_limit
    
    def _create_base_campaign(
        self,
        template: BillingTemplate,
        total_contacts: int,
        metadata: Dict
    ) -> Campaign:
        """Cria Campaign base"""
        return Campaign.objects.create(
            tenant=self.tenant,
            name=f"Billing: {template.get_template_type_display()} - {timezone.now().strftime('%d/%m/%Y %H:%M')}",
            campaign_type=CampaignType.INSTANT,
            status='running',
            total_contacts=total_contacts,
            metadata=metadata
        )
    
    def _create_contacts(
        self,
        billing_campaign: BillingCampaign,
        campaign: Campaign,
        template: BillingTemplate,
        contacts_data: List[Dict]
    ) -> List[BillingContact]:
        """
        Cria todos os contatos em batch
        
        Para cada contato:
        1. Valida telefone
        2. Enriquece variáveis (calcula dias, etc)
        3. Valida variáveis obrigatórias
        4. Seleciona variação de template
        5. Renderiza mensagem
        6. Cria Contact/CampaignContact/BillingContact
        """
        billing_contacts = []
        campaign_contacts = []
        contacts_to_create = []
        
        for contact_data in contacts_data:
            try:
                # 1. Valida telefone
                valid, phone, error = PhoneValidator.validate(
                    contact_data.get('telefone', '')
                )
                
                if not valid:
                    logger.warning(f"❌ Telefone inválido: {error}")
                    continue
                
                # 2. Enriquece variáveis
                enriched_vars = BillingDateCalculator.enrich_variables(contact_data)
                
                # 3. Valida variáveis obrigatórias
                valid, error = template.validate_variables(enriched_vars)
                if not valid:
                    logger.warning(f"❌ Variáveis inválidas: {error}")
                    continue
                
                # 4. Seleciona variação
                variation = self._select_variation(template)
                
                # 5. Renderiza mensagem
                from apps.billing.utils.template_engine import BillingTemplateEngine
                rendered = BillingTemplateEngine.render_message(
                    variation.message_template,
                    enriched_vars
                )
                
                # 6. Cria Contact (se não existir)
                contact, _ = Contact.objects.get_or_create(
                    tenant=self.tenant,
                    phone_number=phone,
                    defaults={
                        'name': contact_data.get('nome_cliente', 'Cliente'),
                        'metadata': contact_data
                    }
                )
                
                # 7. Cria CampaignContact
                campaign_contact = CampaignContact(
                    campaign=campaign,
                    contact=contact,
                    phone_number=phone,
                    status='pending',
                    metadata=enriched_vars
                )
                campaign_contacts.append(campaign_contact)
                
                # 8. Cria BillingContact
                billing_contact = BillingContact(
                    billing_campaign=billing_campaign,
                    template_variation=variation,
                    rendered_message=rendered,
                    template_variables=enriched_vars,
                    calculated_variables={
                        k: v for k, v in enriched_vars.items()
                        if k.startswith('dias_') or k == 'status_vencimento'
                    }
                )
                
                billing_contacts.append((billing_contact, campaign_contact))
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar contato: {e}")
                continue
        
        # Bulk create (performance!)
        CampaignContact.objects.bulk_create(
            [bc[1] for bc in billing_contacts],
            batch_size=500
        )
        
        # Associa campaign_contact a billing_contact
        for i, (billing_contact, campaign_contact) in enumerate(billing_contacts):
            billing_contact.campaign_contact = campaign_contacts[i]
        
        BillingContact.objects.bulk_create(
            [bc[0] for bc in billing_contacts],
            batch_size=500
        )
        
        logger.info(f"✅ {len(billing_contacts)} contatos criados")
        
        return [bc[0] for bc in billing_contacts]
    
    def _select_variation(self, template: BillingTemplate):
        """
        Seleciona variação baseado na estratégia
        """
        from apps.billing.models import RotationStrategy
        import random
        
        variations = list(template.variations.filter(is_active=True))
        
        if not variations:
            raise ValueError(f"Template {template.id} não tem variações ativas")
        
        if template.rotation_strategy == RotationStrategy.RANDOM:
            return random.choice(variations)
        
        elif template.rotation_strategy == RotationStrategy.SEQUENTIAL:
            # Usa a menos usada
            return min(variations, key=lambda v: v.times_used)
        
        elif template.rotation_strategy == RotationStrategy.WEIGHTED:
            # Equilibrado (weighted random inverso)
            total_uses = sum(v.times_used for v in variations)
            
            if total_uses == 0:
                return random.choice(variations)
            
            # Calcula pesos (inverso do uso)
            weights = [1 / (v.times_used + 1) for v in variations]
            return random.choices(variations, weights=weights)[0]
        
        return variations[0]
```

---

### **3. Billing Send Service** (`services/billing_send_service.py`)

```python
"""
Serviço de envio de mensagens de billing
"""
from django.utils import timezone
from apps.billing.models import BillingContact
from apps.whatsapp.models import Instance
from apps.chat.models import Conversation, Message
from apps.evolution.services import EvolutionAPIService
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class BillingSendService:
    """
    Envia mensagem de billing via Evolution API
    
    Responsabilidades:
    - Enviar mensagem via Evolution API
    - Salvar no histórico do chat
    - Criar/atualizar Conversation
    - Fechar conversa automaticamente
    - Atualizar status do contato
    - Retry em falhas
    """
    
    def send_billing_message(
        self,
        billing_contact: BillingContact,
        instance: Instance
    ) -> bool:
        """
        Envia mensagem de billing
        
        Returns:
            True se enviou com sucesso, False se falhou
        """
        try:
            campaign_contact = billing_contact.campaign_contact
            phone = campaign_contact.phone_number
            message = billing_contact.rendered_message
            
            logger.info(
                f"📤 Enviando billing para {phone} "
                f"(campanha: {billing_contact.billing_campaign.id})"
            )
            
            # 1. Envia via Evolution API
            evolution = EvolutionAPIService(instance)
            success, response = evolution.send_text_message(
                phone_number=phone,
                message=message
            )
            
            if not success:
                logger.error(f"❌ Falha ao enviar: {response}")
                campaign_contact.status = 'failed'
                campaign_contact.save()
                
                billing_contact.last_error = str(response)
                billing_contact.last_error_at = timezone.now()
                billing_contact.save()
                
                return False
            
            # 2. Cria/atualiza Conversation
            conversation = self._get_or_create_conversation(
                billing_contact,
                instance
            )
            
            # 3. Salva Message no histórico
            message_obj = Message.objects.create(
                conversation=conversation,
                tenant=billing_contact.billing_campaign.tenant,
                sender='agent',
                content=message,
                message_type='text',
                status='sent',
                metadata={
                    'billing_campaign_id': str(billing_contact.billing_campaign.id),
                    'billing_contact_id': str(billing_contact.id),
                    'external_id': billing_contact.billing_campaign.external_id,
                    'template_type': billing_contact.billing_campaign.template.template_type,
                    'evolution_response': response
                }
            )
            
            # 4. Fecha conversa automaticamente
            conversation.status = 'closed'
            conversation.closed_at = timezone.now()
            conversation.closed_by = 'system'
            conversation.save()
            
            logger.info(f"✅ Conversa fechada automaticamente: {conversation.id}")
            
            # 5. Atualiza status do contato
            campaign_contact.status = 'sent'
            campaign_contact.sent_at = timezone.now()
            campaign_contact.save()
            
            logger.info(f"✅ Mensagem enviada para {phone}")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Erro ao enviar billing: {e}", exc_info=True)
            
            campaign_contact.status = 'failed'
            campaign_contact.save()
            
            billing_contact.last_error = str(e)
            billing_contact.last_error_at = timezone.now()
            billing_contact.save()
            
            return False
    
    def _get_or_create_conversation(
        self,
        billing_contact: BillingContact,
        instance: Instance
    ) -> Conversation:
        """
        Cria ou reabre conversa existente
        """
        tenant = billing_contact.billing_campaign.tenant
        phone = billing_contact.campaign_contact.phone_number
        contact = billing_contact.campaign_contact.contact
        
        # Busca conversa existente (fechada recentemente)
        existing = Conversation.objects.filter(
            tenant=tenant,
            contact=contact,
            status='closed'
        ).order_by('-closed_at').first()
        
        # Se tem conversa fechada recente (< 24h), reabre
        if existing:
            hours_since_closed = (
                timezone.now() - existing.closed_at
            ).total_seconds() / 3600
            
            if hours_since_closed < 24:
                logger.info(f"♻️ Reabrindo conversa existente: {existing.id}")
                existing.status = 'open'
                existing.reopened_at = timezone.now()
                existing.reopened_by = 'billing_system'
                existing.save()
                return existing
        
        # Cria nova conversa
        conversation = Conversation.objects.create(
            tenant=tenant,
            contact=contact,
            phone_number=phone,
            instance=instance,
            status='open',
            source='billing',
            metadata={
                'billing_campaign_id': str(billing_contact.billing_campaign.id),
                'external_id': billing_contact.billing_campaign.external_id,
                'auto_created': True
            }
        )
        
        logger.info(f"✨ Nova conversa criada: {conversation.id}")
        
        return conversation
```

---

## 🌐 **APIS E ENDPOINTS**

### **Authentication** (`authentication.py`)

```python
"""
Autenticação por API Key para Billing
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from apps.billing.models import BillingAPIKey
from django.utils import timezone


class BillingAPIKeyAuthentication(BaseAuthentication):
    """Autenticação via API Key"""
    
    def authenticate(self, request):
        api_key = request.headers.get('X-Billing-API-Key')
        
        if not api_key:
            return None  # Deixa outros authenticators tentarem
        
        try:
            key_obj = BillingAPIKey.objects.select_related(
                'tenant',
                'tenant__billing_config'
            ).get(key=api_key)
            
            # Valida key
            ip_address = self._get_client_ip(request)
            is_valid, reason = key_obj.is_valid(ip_address)
            
            if not is_valid:
                raise AuthenticationFailed(reason)
            
            # Incrementa uso
            key_obj.increment_usage(ip_address)
            
            # Retorna (None, key_obj) - user é None, auth é key_obj
            return (None, key_obj)
        
        except BillingAPIKey.DoesNotExist:
            raise AuthenticationFailed('API Key inválida')
    
    def _get_client_ip(self, request):
        """Extrai IP do cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
```

---

### **Rate Limiting** (`throttling.py`)

```python
"""
Rate limiting para API de Billing
"""
from rest_framework.throttling import BaseThrottle
from django.core.cache import cache
from django.utils import timezone
from apps.billing.constants import BillingConstants


class BillingAPIRateThrottle(BaseThrottle):
    """
    Rate limit por API Key
    
    Usa config do tenant (api_rate_limit_per_hour)
    """
    
    def allow_request(self, request, view):
        # Pega API Key do auth
        api_key = getattr(request, 'auth', None)
        if not api_key:
            return True  # Sem API key, não limita
        
        # Cache key
        cache_key = f"{BillingConstants.RATE_LIMIT_CACHE_PREFIX}_{api_key.id}"
        
        # Busca contador
        now = timezone.now()
        hour_key = now.strftime('%Y%m%d%H')
        full_cache_key = f"{cache_key}_{hour_key}"
        
        count = cache.get(full_cache_key, 0)
        limit = api_key.tenant.billing_config.api_rate_limit_per_hour
        
        if count >= limit:
            return False
        
        # Incrementa
        cache.set(
            full_cache_key,
            count + 1,
            timeout=BillingConstants.RATE_LIMIT_CACHE_TIMEOUT
        )
        
        return True
    
    def wait(self):
        """Tempo de espera (em segundos)"""
        return 3600  # 1 hora
```

---

### **Serializers** (`serializers.py`)

```python
"""
Serializers da API de Billing
"""
from rest_framework import serializers
from apps.billing.models import BillingCampaign, BillingQueue, QueueStatus


class BillingContactSerializer(serializers.Serializer):
    """Serializer de contato individual"""
    
    nome_cliente = serializers.CharField(max_length=255)
    telefone = serializers.CharField(max_length=20)
    
    # Campos para overdue/upcoming
    valor = serializers.CharField(max_length=50, required=False)
    data_vencimento = serializers.CharField(max_length=10, required=False)
    valor_total = serializers.CharField(max_length=50, required=False)
    
    # Campos opcionais
    codigo_pix = serializers.CharField(max_length=500, required=False, allow_blank=True)
    link_pagamento = serializers.URLField(required=False, allow_blank=True)
    numero_fatura = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Campos para notificações
    titulo = serializers.CharField(max_length=200, required=False)
    mensagem = serializers.CharField(max_length=1000, required=False)


class SendBillingRequestSerializer(serializers.Serializer):
    """Request de envio de billing"""
    
    external_id = serializers.CharField(
        max_length=255,
        help_text="ID único no sistema do cliente"
    )
    
    contacts = serializers.ListField(
        child=BillingContactSerializer(),
        min_length=1,
        max_length=1000,
        help_text="Lista de contatos (max 1000)"
    )
    
    callback_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="URL para receber callbacks de eventos"
    )
    
    metadata = serializers.DictField(
        required=False,
        help_text="Dados extras (JSON)"
    )


class SendBillingResponseSerializer(serializers.Serializer):
    """Response de envio"""
    
    success = serializers.BooleanField()
    message = serializers.CharField()
    
    billing_campaign_id = serializers.UUIDField(required=False)
    queue_id = serializers.UUIDField(required=False)
    
    total_contacts = serializers.IntegerField(required=False)
    estimated_duration_minutes = serializers.IntegerField(required=False)


class QueueStatusResponseSerializer(serializers.ModelSerializer):
    """Status da fila"""
    
    progress_percent = serializers.SerializerMethodField()
    eta = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display')
    
    class Meta:
        model = BillingQueue
        fields = [
            'id',
            'status',
            'status_display',
            'total_contacts',
            'contacts_sent',
            'contacts_delivered',
            'contacts_failed',
            'contacts_pending_retry',
            'progress_percent',
            'current_rate',
            'eta',
            'started_at',
            'completed_at',
            'pause_reason'
        ]
    
    def get_progress_percent(self, obj):
        return round(obj.calculate_progress(), 2)
    
    def get_eta(self, obj):
        eta = obj.calculate_eta()
        return eta.isoformat() if eta else None
```

---

### **Views** (`views.py`)

```python
"""
Views da API de Billing
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.billing.authentication import BillingAPIKeyAuthentication
from apps.billing.throttling import BillingAPIRateThrottle
from apps.billing.serializers import (
    SendBillingRequestSerializer,
    SendBillingResponseSerializer,
    QueueStatusResponseSerializer
)
from apps.billing.services.billing_campaign_service import BillingCampaignService
from apps.billing.models import BillingQueue, BillingCampaign
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

logger = logging.getLogger(__name__)


class SendOverdueView(APIView):
    """
    Envia cobrança atrasada
    
    POST /api/v1/billing/send/overdue
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    
    @swagger_auto_schema(
        operation_description="Envia cobrança atrasada",
        request_body=SendBillingRequestSerializer,
        responses={
            200: SendBillingResponseSerializer,
            400: "Erro de validação",
            401: "API Key inválida",
            429: "Rate limit excedido"
        }
    )
    def post(self, request):
        # Valida request
        serializer = SendBillingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Dados inválidos', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Pega tenant da API Key
        api_key = request.auth
        tenant = api_key.tenant
        
        # Verifica se API Key pode usar este tipo
        if not api_key.can_use_template_type('overdue'):
            return Response(
                {'success': False, 'message': 'API Key não autorizada para este tipo de template'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cria campanha
        service = BillingCampaignService(tenant, api_key)
        success, billing_campaign, message = service.create_billing_campaign(
            template_type='overdue',
            contacts_data=serializer.validated_data['contacts'],
            external_id=serializer.validated_data['external_id'],
            callback_url=serializer.validated_data.get('callback_url', ''),
            metadata=serializer.validated_data.get('metadata')
        )
        
        if not success:
            return Response(
                {'success': False, 'message': message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Resposta
        queue = billing_campaign.queue
        estimated_minutes = queue.calculate_eta()
        
        response_data = {
            'success': True,
            'message': message,
            'billing_campaign_id': str(billing_campaign.id),
            'queue_id': str(queue.id),
            'total_contacts': queue.total_contacts,
            'estimated_duration_minutes': int(estimated_minutes.total_seconds() / 60) if estimated_minutes else None
        }
        
        return Response(
            SendBillingResponseSerializer(response_data).data,
            status=status.HTTP_200_OK
        )


class SendUpcomingView(APIView):
    """
    Envia cobrança a vencer
    
    POST /api/v1/billing/send/upcoming
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    
    @swagger_auto_schema(
        operation_description="Envia cobrança a vencer",
        request_body=SendBillingRequestSerializer,
        responses={200: SendBillingResponseSerializer}
    )
    def post(self, request):
        serializer = SendBillingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Dados inválidos', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api_key = request.auth
        tenant = api_key.tenant
        
        if not api_key.can_use_template_type('upcoming'):
            return Response(
                {'success': False, 'message': 'API Key não autorizada'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        service = BillingCampaignService(tenant, api_key)
        success, billing_campaign, message = service.create_billing_campaign(
            template_type='upcoming',
            contacts_data=serializer.validated_data['contacts'],
            external_id=serializer.validated_data['external_id'],
            callback_url=serializer.validated_data.get('callback_url', ''),
            metadata=serializer.validated_data.get('metadata')
        )
        
        if not success:
            return Response(
                {'success': False, 'message': message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queue = billing_campaign.queue
        response_data = {
            'success': True,
            'message': message,
            'billing_campaign_id': str(billing_campaign.id),
            'queue_id': str(queue.id),
            'total_contacts': queue.total_contacts
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


class SendNotificationView(APIView):
    """
    Envia notificação/aviso
    
    POST /api/v1/billing/send/notification
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    
    @swagger_auto_schema(
        operation_description="Envia notificação/aviso (24/7, sem respeitar horário comercial)",
        request_body=SendBillingRequestSerializer,
        responses={200: SendBillingResponseSerializer}
    )
    def post(self, request):
        serializer = SendBillingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Dados inválidos', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api_key = request.auth
        tenant = api_key.tenant
        
        if not api_key.can_use_template_type('notification'):
            return Response(
                {'success': False, 'message': 'API Key não autorizada'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        service = BillingCampaignService(tenant, api_key)
        success, billing_campaign, message = service.create_billing_campaign(
            template_type='notification',
            contacts_data=serializer.validated_data['contacts'],
            external_id=serializer.validated_data['external_id'],
            callback_url=serializer.validated_data.get('callback_url', ''),
            metadata=serializer.validated_data.get('metadata')
        )
        
        if not success:
            return Response(
                {'success': False, 'message': message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queue = billing_campaign.queue
        response_data = {
            'success': True,
            'message': message,
            'billing_campaign_id': str(billing_campaign.id),
            'queue_id': str(queue.id),
            'total_contacts': queue.total_contacts
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


class QueueStatusView(APIView):
    """
    Consulta status da fila
    
    GET /api/v1/billing/queue/{queue_id}/status
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    
    @swagger_auto_schema(
        operation_description="Consulta status de uma fila de envio",
        responses={
            200: QueueStatusResponseSerializer,
            404: "Fila não encontrada"
        }
    )
    def get(self, request, queue_id):
        api_key = request.auth
        tenant = api_key.tenant
        
        try:
            queue = BillingQueue.objects.select_related(
                'billing_campaign'
            ).get(
                id=queue_id,
                billing_campaign__tenant=tenant
            )
            
            serializer = QueueStatusResponseSerializer(queue)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except BillingQueue.DoesNotExist:
            return Response(
                {'error': 'Fila não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )


class QueueControlView(APIView):
    """
    Controla fila (pause/resume/cancel)
    
    POST /api/v1/billing/queue/{queue_id}/control
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    
    @swagger_auto_schema(
        operation_description="Controla fila (pause/resume/cancel)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'action': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['pause', 'resume', 'cancel'],
                    description="Ação a executar"
                )
            },
            required=['action']
        ),
        responses={
            200: "Ação executada com sucesso",
            400: "Ação inválida",
            404: "Fila não encontrada"
        }
    )
    def post(self, request, queue_id):
        api_key = request.auth
        tenant = api_key.tenant
        action = request.data.get('action')
        
        if action not in ['pause', 'resume', 'cancel']:
            return Response(
                {'error': 'Ação inválida. Use: pause, resume ou cancel'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            queue = BillingQueue.objects.get(
                id=queue_id,
                billing_campaign__tenant=tenant
            )
            
            if action == 'pause':
                if queue.status == QueueStatus.RUNNING:
                    queue.status = QueueStatus.PAUSED
                    queue.paused_at = timezone.now()
                    queue.pause_reason = 'Pausado via API'
                    queue.save()
                    return Response({'message': 'Fila pausada'})
                else:
                    return Response(
                        {'error': 'Fila não está rodando'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif action == 'resume':
                if queue.status in [QueueStatus.PAUSED, QueueStatus.INSTANCE_DOWN]:
                    from apps.billing.rabbitmq.billing_publisher import BillingQueuePublisher
                    import asyncio
                    
                    asyncio.run(
                        BillingQueuePublisher.publish_queue(
                            str(queue.id),
                            queue.billing_campaign.template.template_type
                        )
                    )
                    
                    return Response({'message': 'Fila retomada'})
                else:
                    return Response(
                        {'error': 'Fila não está pausada'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif action == 'cancel':
                if queue.status not in [QueueStatus.COMPLETED, QueueStatus.CANCELLED]:
                    queue.status = QueueStatus.CANCELLED
                    queue.completed_at = timezone.now()
                    queue.save()
                    return Response({'message': 'Fila cancelada'})
                else:
                    return Response(
                        {'error': 'Fila já finalizada'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        except BillingQueue.DoesNotExist:
            return Response(
                {'error': 'Fila não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
```

---

### **URLs** (`urls.py`)

```python
"""
URLs da API de Billing
"""
from django.urls import path
from apps.billing.views import (
    SendOverdueView,
    SendUpcomingView,
    SendNotificationView,
    QueueStatusView,
    QueueControlView
)

app_name = 'billing'

urlpatterns = [
    # Envio
    path('send/overdue/', SendOverdueView.as_view(), name='send_overdue'),
    path('send/upcoming/', SendUpcomingView.as_view(), name='send_upcoming'),
    path('send/notification/', SendNotificationView.as_view(), name='send_notification'),
    
    # Queue
    path('queue/<uuid:queue_id>/status/', QueueStatusView.as_view(), name='queue_status'),
    path('queue/<uuid:queue_id>/control/', QueueControlView.as_view(), name='queue_control'),
]
```

---

## 📊 **OBSERVABILIDADE**

### **Prometheus Metrics** (`metrics.py`)

```python
"""
Métricas Prometheus para Billing
"""
from prometheus_client import Counter, Histogram, Gauge, Summary

# Contador de mensagens
billing_messages_sent_total = Counter(
    'billing_messages_sent_total',
    'Total de mensagens de billing enviadas',
    ['tenant_id', 'template_type', 'status']
)

# Histograma de duração de envio
billing_send_duration_seconds = Histogram(
    'billing_send_duration_seconds',
    'Duração do envio de mensagem (segundos)',
    ['tenant_id', 'template_type']
)

# Gauge de queues ativas
billing_active_queues = Gauge(
    'billing_active_queues',
    'Número de queues ativas',
    ['tenant_id', 'status']
)

# Taxa de envio (msgs/min)
billing_send_rate = Gauge(
    'billing_send_rate',
    'Taxa de envio (mensagens por minuto)',
    ['tenant_id', 'queue_id']
)

# Taxa de falhas
billing_failure_rate = Gauge(
    'billing_failure_rate',
    'Taxa de falhas (%)',
    ['tenant_id', 'template_type']
)
```

---

## 🐛 **TROUBLESHOOTING**

### **Problema 1: Mensagens não estão sendo enviadas**

**Sintomas:**
- Queue fica em `PENDING` ou `RUNNING` mas não progride
- Nenhuma mensagem aparece no chat

**Causas Possíveis:**
1. Consumer não está rodando
2. RabbitMQ offline
3. Instância Evolution API offline
4. Horário fora do comercial (se configurado)

**Solução:**
```bash
# 1. Verificar se consumer está rodando
ps aux | grep run_billing_consumer

# 2. Verificar logs
tail -f logs/billing_consumer.log

# 3. Verificar RabbitMQ
python manage.py shell
>>> from django.conf import settings
>>> print(settings.RABBITMQ_URL)

# 4. Verificar instância
python manage.py shell
>>> from apps.whatsapp.models import Instance
>>> Instance.objects.filter(is_active=True, status='open')

# 5. Forçar retomada
python manage.py shell
>>> from apps.billing.models import BillingQueue
>>> queue = BillingQueue.objects.get(id='uuid-aqui')
>>> from apps.billing.rabbitmq.billing_publisher import BillingQueuePublisher
>>> import asyncio
>>> asyncio.run(BillingQueuePublisher.publish_queue(str(queue.id), 'overdue'))
```

---

### **Problema 2: Rate limit muito lento**

**Sintomas:**
- Enviando muito devagar (ex: 1 msg/min quando configurado para 20)

**Solução:**
```python
# 1. Verificar config do tenant
python manage.py shell
>>> from apps.billing.models import BillingConfig
>>> config = BillingConfig.objects.get(tenant__name='Nome do Tenant')
>>> print(f"Messages per minute: {config.messages_per_minute}")
>>> print(f"Min interval: {config.min_interval_seconds}")

# 2. Ajustar se necessário
>>> config.messages_per_minute = 20  # 20 msgs/min = 1 msg a cada 3 seg
>>> config.min_interval_seconds = 3
>>> config.save()

# 3. Forçar retomada da queue (para pegar nova config)
>>> from apps.billing.models import BillingQueue
>>> queue = BillingQueue.objects.filter(status='running').first()
>>> # Pausa e retoma
```

---

## ❓ **FAQ**

### **1. Como criar uma API Key?**

```python
python manage.py shell
>>> from apps.billing.models import BillingAPIKey
>>> from apps.tenancy.models import Tenant
>>> tenant = Tenant.objects.get(name='Meu Tenant')
>>> key = BillingAPIKey.objects.create(
...     tenant=tenant,
...     name='Produção',
...     description='API Key para sistema ERP',
...     allowed_template_types=['overdue', 'upcoming']
... )
>>> print(f"API Key criada: {key.key}")
```

### **2. Como testar localmente?**

```bash
# 1. Rodar consumer
python manage.py run_billing_consumer

# 2. Em outro terminal, fazer request
curl -X POST http://localhost:8000/api/v1/billing/send/overdue \
  -H "X-Billing-API-Key: billing_..." \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "fatura-12345",
    "contacts": [
      {
        "nome_cliente": "João Silva",
        "telefone": "+5511999999999",
        "valor": "R$ 150,00",
        "data_vencimento": "15/12/2025"
      }
    ]
  }'
```

### **3. Como monitorar em produção?**

```bash
# Logs do consumer
railway logs --service billing_consumer --tail

# Status das queues
python manage.py shell
>>> from apps.billing.models import BillingQueue
>>> BillingQueue.objects.filter(status='running').count()

# Métricas (se Prometheus configurado)
curl http://localhost:8000/metrics | grep billing_
```

---

## 📚 **EXEMPLOS DE USO**

### **Exemplo 1: Cobrança Atrasada**

```bash
curl -X POST https://api.alreasense.com/api/v1/billing/send/overdue \
  -H "X-Billing-API-Key: billing_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "fatura-67890",
    "callback_url": "https://meu-erp.com/webhooks/billing",
    "contacts": [
      {
        "nome_cliente": "João Silva",
        "telefone": "+5511999999999",
        "valor": "R$ 150,00",
        "data_vencimento": "10/12/2025",
        "valor_total": "R$ 165,00",
        "codigo_pix": "00020126580014br.gov.bcb.pix...",
        "link_pagamento": "https://pay.meu-erp.com/invoice/67890",
        "numero_fatura": "2025-67890"
      }
    ],
    "metadata": {
      "cliente_id": "12345",
      "empresa": "Empresa XYZ"
    }
  }'
```

**Resposta:**
```json
{
  "success": true,
  "message": "Campanha criada com sucesso",
  "billing_campaign_id": "550e8400-e29b-41d4-a716-446655440000",
  "queue_id": "660e8400-e29b-41d4-a716-446655440000",
  "total_contacts": 1,
  "estimated_duration_minutes": 1
}
```

---

### **Exemplo 2: Consultar Status**

```bash
curl -X GET https://api.alreasense.com/api/v1/billing/queue/660e8400-e29b-41d4-a716-446655440000/status \
  -H "X-Billing-API-Key: billing_abc123..."
```

**Resposta:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "status_display": "Concluído",
  "total_contacts": 1,
  "contacts_sent": 1,
  "contacts_delivered": 1,
  "contacts_failed": 0,
  "contacts_pending_retry": 0,
  "progress_percent": 100.0,
  "current_rate": 20.0,
  "eta": null,
  "started_at": "2025-12-17T10:00:00Z",
  "completed_at": "2025-12-17T10:00:05Z",
  "pause_reason": ""
}
```

---

## 🎯 **CONCLUSÃO PARTE 2**

Esta parte complementou o guia principal com:

✅ **Services completos** (BillingCampaignService, BillingSendService, BusinessHoursScheduler)  
✅ **APIs REST** completas com autenticação, rate limiting e validação  
✅ **Serializers** para todos os endpoints  
✅ **Observabilidade** com Prometheus metrics  
✅ **Troubleshooting** detalhado  
✅ **FAQ** com dúvidas comuns  
✅ **Exemplos práticos** de uso da API

**Agora você tem TUDO para implementar o sistema completo!** 🚀

