# 💳 ALREA - Integração Asaas (Billing)

> **Documento:** Integração completa com Gateway de Pagamento Asaas  
> **Modelo:** Assinatura Mensal + Recursos Extras com Prorata  
> **Versão:** 1.0.0  
> **Data:** 2025-10-08  
> **Confidencial:** Documentação técnica interna

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Por que Asaas](#por-que-asaas)
3. [Modelo de Cobrança](#modelo-de-cobrança)
4. [Arquitetura de Integração](#arquitetura-de-integração)
5. [Modelagem de Dados](#modelagem-de-dados)
6. [Fluxos de Negócio](#fluxos-de-negócio)
7. [API Endpoints](#api-endpoints)
8. [Webhooks Asaas](#webhooks-asaas)
9. [Interface do Cliente](#interface-do-cliente)
10. [Cronograma de Implementação](#cronograma-de-implementação)

---

## 🎯 VISÃO GERAL

### Objetivo

Integrar sistema de billing completo com **Asaas** para permitir:

- ✅ Assinaturas mensais recorrentes
- ✅ Múltiplos métodos de pagamento (PIX, Boleto, Cartão)
- ✅ Recursos extras com prorata automática
- ✅ Upgrade/Downgrade de planos
- ✅ Suspensão automática por inadimplência
- ✅ Gerenciamento de faturas

### Modelo de Negócio

**"PAGUE E USE"** - Assinatura mensal com limites fixos:

```
Cliente paga R$ 49/mês (Plano Starter)
├─ Recebe: 2 instâncias, 5 campanhas, 500 contatos
├─ Usou tudo? Acabou o mês
├─ Usou pouco? Perdeu o resto
├─ Quer mais? Adiciona extras com prorata
└─ Próximo mês: Renova tudo
```

**SEM cobrança por uso**, **SEM cálculo de excedente**, **SEM surpresas**

---

## 🇧🇷 POR QUE ASAAS

### Comparação com Stripe

```
┌─────────────────────┬───────────┬──────────┐
│ Feature             │ Asaas     │ Stripe   │
├─────────────────────┼───────────┼──────────┤
│ PIX                 │ ✅ Nativo │ ❌ Complexo│
│ Boleto              │ ✅ Nativo │ ❌ Não tem│
│ Cartão BR           │ ✅ Ótimo  │ ✅ Bom   │
│ IOF                 │ ✅ Sem    │ ❌ 6,38% │
│ CPF/CNPJ            │ ✅ Nativo │ ⚠️ Manual│
│ Suporte PT-BR       │ ✅ Sim    │ ❌ EN    │
│ Preço (taxa)        │ ✅ 2,99%  │ ⚠️ 4,99% │
│ Documentação        │ ⚠️ Básica │ ✅ Excelente│
│ Webhooks            │ ✅ Sim    │ ✅ Sim   │
│ Prorata             │ ✅ Nativo │ ✅ Nativo│
└─────────────────────┴───────────┴──────────┘

Para SaaS Brasil: Asaas VENCE ✅
```

### Vantagens Específicas

- ✅ **PIX instantâneo** - Cliente paga e ativa na hora
- ✅ **Boleto** - Opção para quem não tem cartão
- ✅ **Sem IOF** - Nacional, sem imposto de câmbio
- ✅ **Taxas menores** - 2,99% vs 4,99% Stripe
- ✅ **Split de pagamento** - Útil para marketplace futuro

---

## 💰 MODELO DE COBRANÇA

### Assinatura Mensal Fixa

**Não há cobrança por uso.** Cliente paga valor fixo mensal.

```yaml
Plano Starter: R$ 49/mês (fixo)
  Recebe:
    - 2 instâncias WhatsApp
    - 5 campanhas/mês
    - 500 contatos/campanha
    - 1.000 mensagens/campanha
  
  Usou 100 mensagens? Paga R$ 49
  Usou 1.000 mensagens? Paga R$ 49
  Usou 0 mensagens? Paga R$ 49
  
  ✅ Valor SEMPRE fixo
  ❌ SEM surpresas na fatura
```

### Recursos Extras (Prorata)

Cliente pode **adicionar recursos** durante o mês:

```
Dia 8 do ciclo: Cliente quer mais 2 instâncias
  
  Custo mensal: 2 × R$ 20 = R$ 40/mês
  Dias restantes: 22 de 30
  
  Cobrança AGORA (prorata): R$ 40 × (22/30) = R$ 29,33
  Próxima fatura: R$ 49 + R$ 40 = R$ 89/mês
  
  ✅ Asaas calcula e cobra automaticamente
  ✅ Tudo vence junto (data unificada)
```

### Tabela de Preços (Customizável)

```python
# settings.py ou Admin Django

RESOURCE_PRICING = {
    # Instâncias WhatsApp
    'instance': {
        'price_per_unit': 20.00,  # ⭐ Customizável
        'name': 'Instância WhatsApp',
        'description': 'Conexão adicional de WhatsApp'
    },
    
    # Slots de campanha
    'campaign_slot': {
        'price_per_unit': 10.00,  # ⭐ Customizável
        'name': 'Pacote de Campanhas',
        'description': '+5 campanhas/mês'
    },
    
    # Limite de contatos
    'contact_limit': {
        'price_per_unit': 15.00,  # ⭐ Customizável
        'name': 'Pacote de Contatos',
        'description': '+1.000 contatos por campanha'
    }
}

# Todos os valores são CUSTOMIZÁVEIS via Admin
```

---

## 🏗️ ARQUITETURA DE INTEGRAÇÃO

### Diagrama de Fluxo

```
┌────────────────────────────────────────────────────┐
│              FRONTEND (React)                      │
│  - Escolher plano                                  │
│  - Adicionar recursos extras                       │
│  - Gerenciar assinatura                            │
└────────────────┬───────────────────────────────────┘
                 │ HTTP/REST
┌────────────────▼───────────────────────────────────┐
│           DJANGO BACKEND                           │
│  ┌──────────────────────────────────────────────┐ │
│  │ BillingService                               │ │
│  │ - create_subscription()                      │ │
│  │ - add_extra_resource()                       │ │
│  │ - upgrade_plan()                             │ │
│  │ - cancel_subscription()                      │ │
│  └──────────────────────────────────────────────┘ │
└────────────────┬───────────────────────────────────┘
                 │ API Asaas
┌────────────────▼───────────────────────────────────┐
│                  ASAAS API                         │
│  - Customers                                       │
│  - Subscriptions (assinaturas recorrentes)         │
│  - Payments (cobranças avulsas)                    │
│  - Webhooks (eventos)                              │
└────────────────┬───────────────────────────────────┘
                 │ Webhooks
┌────────────────▼───────────────────────────────────┐
│        DJANGO WEBHOOK HANDLER                      │
│  /webhooks/asaas/                                  │
│  - PAYMENT_RECEIVED → Ativar tenant                │
│  - PAYMENT_OVERDUE → Suspender tenant              │
│  - SUBSCRIPTION_UPDATED → Atualizar dados          │
└────────────────────────────────────────────────────┘
```

---

## 📊 MODELAGEM DE DADOS

### Models Principais

```python
# apps/billing/models.py

from django.db import models
from django.utils import timezone
import uuid


class AsaasCustomer(models.Model):
    """
    Cliente no Asaas (1:1 com Tenant)
    """
    
    tenant = models.OneToOneField(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='asaas_customer'
    )
    
    asaas_customer_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID do customer no Asaas (cus_xxxxx)"
    )
    
    cpf_cnpj = models.CharField(max_length=18)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_asaas_customer'
    
    def __str__(self):
        return f"{self.tenant.name} - {self.asaas_customer_id}"


class AsaasSubscription(models.Model):
    """
    Assinatura ativa do tenant
    """
    
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativa'
        OVERDUE = 'overdue', 'Em Atraso'
        CANCELED = 'canceled', 'Cancelada'
        EXPIRED = 'expired', 'Expirada'
    
    tenant = models.OneToOneField(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='asaas_subscription'
    )
    plan = models.ForeignKey(
        'billing.Plan',
        on_delete=models.PROTECT
    )
    
    asaas_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID da subscription no Asaas (sub_xxxxx)"
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    
    # Valores
    base_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valor base do plano"
    )
    current_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valor total (base + extras)"
    )
    
    # Datas
    current_period_start = models.DateField()
    current_period_end = models.DateField()
    next_due_date = models.DateField()
    
    # Método de pagamento
    billing_type = models.CharField(
        max_length=20,
        choices=[
            ('CREDIT_CARD', 'Cartão de Crédito'),
            ('PIX', 'PIX'),
            ('BOLETO', 'Boleto Bancário'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'billing_asaas_subscription'
    
    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name} ({self.get_status_display()})"
    
    @property
    def days_until_renewal(self):
        """Dias até próxima renovação"""
        delta = self.next_due_date - timezone.now().date()
        return delta.days
    
    @property
    def extras_total(self):
        """Total de recursos extras (mensal)"""
        return self.current_value - self.base_value


class SubscriptionExtra(models.Model):
    """
    Recursos extras adicionados à assinatura
    
    Exemplos:
    - Instâncias WhatsApp adicionais
    - Slots de campanha extras
    - Limite de contatos aumentado
    """
    
    class ResourceType(models.TextChoices):
        INSTANCE = 'instance', 'Instância WhatsApp'
        CAMPAIGN_SLOT = 'campaign_slot', 'Slot de Campanha'
        CONTACT_LIMIT = 'contact_limit', 'Limite de Contatos'
    
    subscription = models.ForeignKey(
        AsaasSubscription,
        on_delete=models.CASCADE,
        related_name='extras'
    )
    
    resource_type = models.CharField(
        max_length=50,
        choices=ResourceType.choices
    )
    
    quantity = models.IntegerField(
        default=1,
        help_text="Quantidade de recursos adicionados"
    )
    
    price_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Preço unitário mensal (customizável)"
    )
    
    monthly_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total mensal (quantity × price_per_unit)"
    )
    
    # Prorata da adição
    prorata_charged = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Valor cobrado imediatamente (prorata)"
    )
    prorata_payment_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID do pagamento de prorata no Asaas"
    )
    
    added_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'billing_subscription_extra'
    
    def __str__(self):
        return f"{self.get_resource_type_display()} × {self.quantity} - {self.subscription.tenant.name}"


class AsaasPayment(models.Model):
    """
    Registro de pagamentos/faturas Asaas
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        CONFIRMED = 'confirmed', 'Confirmado'
        RECEIVED = 'received', 'Recebido'
        OVERDUE = 'overdue', 'Vencido'
        REFUNDED = 'refunded', 'Reembolsado'
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='asaas_payments'
    )
    subscription = models.ForeignKey(
        AsaasSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    asaas_payment_id = models.CharField(max_length=255, unique=True)
    
    value = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    
    due_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    confirmed_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    billing_type = models.CharField(max_length=20)
    
    # PIX específico
    pix_qr_code = models.TextField(blank=True)
    pix_copy_paste = models.TextField(blank=True)
    
    # Boleto específico
    boleto_url = models.URLField(blank=True)
    boleto_barcode = models.CharField(max_length=255, blank=True)
    
    # Flags
    is_prorata = models.BooleanField(
        default=False,
        help_text="True se for cobrança de prorata de recurso extra"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_asaas_payment'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tenant.name} - R$ {self.value} ({self.get_status_display()})"


class AsaasWebhookEvent(models.Model):
    """
    Log de eventos de webhook do Asaas
    Para auditoria e debugging
    """
    
    event_type = models.CharField(max_length=100)
    event_id = models.CharField(max_length=255, unique=True)
    
    payload = models.JSONField()
    
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    error = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_asaas_webhook_event'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_type} - {self.event_id}"
```

---

## 🔄 FLUXOS DE NEGÓCIO

### FLUXO 1: Novo Cliente (Cadastro + Assinatura)

```
PASSO 1: Usuário se cadastra
──────────────────────────────────────────────
Frontend:
  POST /api/auth/register/
  {
    "email": "joao@empresa.com",
    "password": "***",
    "name": "João Silva",
    "company_name": "Empresa XYZ",
    "cpf_cnpj": "12345678901"
  }

Backend Django:
  1. Cria Tenant
  2. Cria User
  3. ⭐ Cria Customer no Asaas
     
     asaas.customers.create({
       'name': 'João Silva',
       'email': 'joao@empresa.com',
       'cpfCnpj': '12345678901'
     })
  
  4. Salva AsaasCustomer(tenant, asaas_customer_id)
  5. Retorna: tenant_id, token


PASSO 2: Usuário escolhe plano
──────────────────────────────────────────────
Frontend: Página de Planos
  
  ┌─────────────────────────────────────┐
  │ [ ] Starter - R$ 49/mês             │
  │ [x] Pro - R$ 149/mês                │
  │ [ ] Enterprise - R$ 499/mês         │
  │                                     │
  │ Método de pagamento:                │
  │ ( ) Cartão de Crédito               │
  │ (•) PIX                             │
  │ ( ) Boleto                          │
  │                                     │
  │ [Assinar Agora]                     │
  └─────────────────────────────────────┘

Backend:
  POST /api/billing/subscribe/
  {
    "plan_id": "uuid-pro",
    "billing_type": "PIX"
  }


PASSO 3: Criar assinatura no Asaas
──────────────────────────────────────────────
Django → Asaas API:
  
  asaas.subscriptions.create({
    'customer': tenant.asaas_customer.asaas_customer_id,
    'billingType': 'PIX',
    'value': 149.00,
    'cycle': 'MONTHLY',
    'description': 'Plano Pro - ALREA',
    'nextDueDate': (hoje + 30 dias).isoformat()
  })
  
  Response:
  {
    'id': 'sub_xxxxx',
    'status': 'ACTIVE',
    'value': 149.00,
    'nextDueDate': '2025-11-08',
    'payment': {  // Primeiro pagamento
      'id': 'pay_xxxxx',
      'pixQrCode': 'data:image...',
      'pixCopyPaste': '00020126....'
    }
  }

Django:
  1. Salva AsaasSubscription
  2. Salva AsaasPayment (primeiro pagamento)
  3. Retorna para frontend


PASSO 4: Mostrar pagamento
──────────────────────────────────────────────
Frontend:
  
  ┌─────────────────────────────────────┐
  │ ✅ Assinatura Criada!               │
  │                                     │
  │ Escaneie o QR Code PIX:             │
  │ [QR CODE IMAGE]                     │
  │                                     │
  │ Ou copie o código:                  │
  │ [00020126...] [Copiar]              │
  │                                     │
  │ Aguardando pagamento...             │
  │ (Atualiza automaticamente)          │
  └─────────────────────────────────────┘


PASSO 5: Cliente paga PIX
──────────────────────────────────────────────
Cliente escaneia QR Code no banco
  ↓ Paga R$ 149
  ↓ Asaas recebe confirmação (instantâneo)
  ↓ Asaas envia webhook


PASSO 6: Webhook ativa tenant
──────────────────────────────────────────────
Asaas → Django:
  POST /webhooks/asaas/
  {
    'event': 'PAYMENT_RECEIVED',
    'payment': {
      'id': 'pay_xxxxx',
      'subscription': 'sub_xxxxx',
      'value': 149.00,
      'status': 'RECEIVED'
    }
  }

Django:
  1. Valida webhook
  2. Busca subscription
  3. Atualiza status:
     
     subscription.status = 'ACTIVE'
     tenant.status = 'active'
     tenant.next_billing_date = subscription.next_due_date
  
  4. ✅ TENANT ATIVO!

Frontend:
  ↓ WebSocket ou polling detecta mudança
  ↓ Redireciona para dashboard
  ↓ "Bem-vindo ao ALREA! Sua assinatura está ativa"
```

---

### FLUXO 2: Adicionar Recurso Extra (Prorata)

```
Cliente ativo: Plano Starter (R$ 49/mês)
Vencimento: 15/11
Data atual: 08/11 (7 dias restantes)


PASSO 1: Cliente quer mais instâncias
──────────────────────────────────────────────
Frontend: Gerenciar Recursos
  
  ┌─────────────────────────────────────┐
  │ Instâncias: 2 incluídas, 0 extras   │
  │ [+ Adicionar Mais]                  │
  └─────────────────────────────────────┘
  
  ↓ Abre modal
  
  ┌─────────────────────────────────────┐
  │ Adicionar Instâncias                │
  │                                     │
  │ Quantidade: [▼ 2]                   │
  │                                     │
  │ Custo: R$ 20/mês cada               │
  │ Total: R$ 40/mês                    │
  │                                     │
  │ ⚡ Cobrança imediata (7 dias):      │
  │    R$ 9,33                          │
  │                                     │
  │ Próximas faturas: R$ 89/mês         │
  │                                     │
  │ [Cancelar] [Confirmar]              │
  └─────────────────────────────────────┘


PASSO 2: Backend calcula e cobra
──────────────────────────────────────────────
POST /api/billing/add-extra-instances/
{
  "quantity": 2,
  "price_per_unit": 20.00
}

Django:
  service = BillingService()
  result = service.add_extra_instances(
    tenant=tenant,
    quantity=2,
    price_per_unit=20.00
  )

BillingService.add_extra_instances():
  
  # 1. Calcular prorata
  days_remaining = 7
  days_in_cycle = 30
  monthly_cost = 2 × 20 = 40
  prorata = (40 / 30) × 7 = 9.33
  
  # 2. Cobrar prorata AGORA (Asaas)
  payment = asaas.payments.create({
    'customer': tenant.asaas_customer_id,
    'value': 9.33,
    'dueDate': today,
    'description': '2 instâncias extras (prorata 7 dias)',
    'billingType': 'CREDIT_CARD'  # Mesmo método da subscription
  })
  
  # 3. Atualizar subscription para próximas cobranças
  asaas.subscriptions.update(subscription_id, {
    'value': 49 + 40  # R$ 89 total
  })
  
  # 4. Salvar no banco
  SubscriptionExtra.create(
    subscription=subscription,
    resource_type='instance',
    quantity=2,
    price_per_unit=20,
    monthly_total=40,
    prorata_charged=9.33
  )
  
  subscription.current_value = 89
  subscription.save()
  
  return {'prorata': 9.33, 'new_total': 89}


PASSO 3: Asaas cobra prorata
──────────────────────────────────────────────
Se PIX:
  → Retorna QR Code
  → Cliente paga R$ 9,33
  → Webhook confirma

Se Cartão:
  → Cobra automaticamente
  → Webhook confirma

Webhook: PAYMENT_RECEIVED
  ↓ Django registra pagamento
  ↓ Ativa as 2 instâncias extras


PASSO 4: Próxima renovação (15/11)
──────────────────────────────────────────────
Asaas cobra automaticamente:
  
  Plano Starter: R$ 49,00
  + 2 Instâncias: R$ 40,00
  ━━━━━━━━━━━━━━━━━━━━━━
  Total: R$ 89,00
  
  ✅ Tudo vence junto (15/11)
  ✅ Valor fixo daqui pra frente
```

---

## 🔌 SERVICES (Django)

### BillingService

```python
# apps/billing/services.py

import requests
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class AsaasService:
    """
    Cliente Asaas API
    """
    
    def __init__(self):
        self.base_url = settings.ASAAS_BASE_URL  # https://api.asaas.com/v3
        self.api_key = settings.ASAAS_API_KEY
        self.headers = {
            'access_token': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def create_customer(self, data):
        """Cria customer no Asaas"""
        response = requests.post(
            f'{self.base_url}/customers',
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def create_subscription(self, data):
        """Cria assinatura recorrente"""
        response = requests.post(
            f'{self.base_url}/subscriptions',
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def update_subscription(self, subscription_id, data):
        """Atualiza assinatura (ex: mudar valor)"""
        response = requests.put(
            f'{self.base_url}/subscriptions/{subscription_id}',
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def create_payment(self, data):
        """Cria cobrança avulsa (ex: prorata)"""
        response = requests.post(
            f'{self.base_url}/payments',
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()


class BillingService:
    """
    Serviço de billing ALREA
    """
    
    def __init__(self):
        self.asaas = AsaasService()
    
    def create_customer(self, tenant):
        """Cria customer no Asaas para tenant"""
        
        # Verificar se já existe
        if hasattr(tenant, 'asaas_customer'):
            return tenant.asaas_customer
        
        # Criar no Asaas
        customer_data = self.asaas.create_customer({
            'name': tenant.name,
            'email': tenant.email,
            'cpfCnpj': tenant.cpf_cnpj,
            'mobilePhone': tenant.phone,
        })
        
        # Salvar no banco
        asaas_customer = AsaasCustomer.objects.create(
            tenant=tenant,
            asaas_customer_id=customer_data['id'],
            cpf_cnpj=tenant.cpf_cnpj
        )
        
        return asaas_customer
    
    def create_subscription(self, tenant, plan, billing_type='PIX'):
        """
        Cria assinatura para tenant
        
        Args:
            tenant: Tenant
            plan: Plan escolhido
            billing_type: PIX, BOLETO, CREDIT_CARD
        
        Returns:
            dict com subscription e payment data
        """
        
        # Garantir que tem customer
        customer = self.create_customer(tenant)
        
        # Calcular próximo vencimento (30 dias)
        next_due = timezone.now().date() + timezone.timedelta(days=30)
        
        # Criar subscription no Asaas
        sub_data = self.asaas.create_subscription({
            'customer': customer.asaas_customer_id,
            'billingType': billing_type,
            'value': float(plan.price),
            'cycle': 'MONTHLY',
            'description': f'Plano {plan.name} - ALREA',
            'nextDueDate': next_due.isoformat()
        })
        
        # Salvar no banco
        subscription = AsaasSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            asaas_subscription_id=sub_data['id'],
            status='ACTIVE',
            base_value=plan.price,
            current_value=plan.price,
            current_period_start=timezone.now().date(),
            current_period_end=next_due,
            next_due_date=next_due,
            billing_type=billing_type
        )
        
        # Primeiro pagamento
        first_payment = sub_data.get('payment', {})
        if first_payment:
            AsaasPayment.objects.create(
                tenant=tenant,
                subscription=subscription,
                asaas_payment_id=first_payment['id'],
                value=plan.price,
                description=f'Primeira mensalidade - {plan.name}',
                due_date=next_due,
                status='PENDING',
                billing_type=billing_type,
                pix_qr_code=first_payment.get('pixQrCode', ''),
                pix_copy_paste=first_payment.get('pixCopyPaste', ''),
                boleto_url=first_payment.get('bankSlipUrl', '')
            )
        
        return {
            'subscription': subscription,
            'payment': first_payment
        }
    
    def add_extra_instances(self, tenant, quantity, price_per_unit=20.00):
        """
        Adiciona instâncias extras com prorata
        
        Args:
            tenant: Tenant
            quantity: Quantidade de instâncias
            price_per_unit: Preço por instância/mês (customizável)
        
        Returns:
            dict com valores e payment_id
        """
        
        subscription = tenant.asaas_subscription
        
        # 1. Calcular dias restantes até próximo vencimento
        today = timezone.now().date()
        days_remaining = (subscription.next_due_date - today).days
        days_in_cycle = 30
        
        # 2. Calcular valores
        monthly_cost = Decimal(str(quantity)) * Decimal(str(price_per_unit))
        prorata_value = (monthly_cost / days_in_cycle) * days_remaining
        prorata_value = prorata_value.quantize(Decimal('0.01'))  # Arredondar
        
        # 3. Cobrar prorata AGORA (Asaas)
        prorata_payment = self.asaas.create_payment({
            'customer': subscription.tenant.asaas_customer.asaas_customer_id,
            'value': float(prorata_value),
            'dueDate': today.isoformat(),
            'description': f'{quantity} instâncias extras (prorata {days_remaining} dias)',
            'billingType': subscription.billing_type,
            'externalReference': f'prorata_instances_{subscription.id}_{today}'
        })
        
        # 4. Atualizar subscription para próximas cobranças
        new_total = subscription.current_value + monthly_cost
        
        self.asaas.update_subscription(subscription.asaas_subscription_id, {
            'value': float(new_total)
        })
        
        # 5. Salvar no banco
        extra = SubscriptionExtra.objects.create(
            subscription=subscription,
            resource_type='instance',
            quantity=quantity,
            price_per_unit=price_per_unit,
            monthly_total=monthly_cost,
            prorata_charged=prorata_value,
            prorata_payment_id=prorata_payment['id']
        )
        
        subscription.current_value = new_total
        subscription.save()
        
        # 6. Registrar pagamento
        AsaasPayment.objects.create(
            tenant=tenant,
            subscription=subscription,
            asaas_payment_id=prorata_payment['id'],
            value=prorata_value,
            description=prorata_payment['description'],
            due_date=today,
            status='PENDING',
            billing_type=subscription.billing_type,
            is_prorata=True,
            pix_qr_code=prorata_payment.get('pixQrCode', ''),
            pix_copy_paste=prorata_payment.get('pixCopyPaste', '')
        )
        
        return {
            'prorata_charged': float(prorata_value),
            'monthly_cost': float(monthly_cost),
            'new_monthly_total': float(new_total),
            'days_remaining': days_remaining,
            'payment_id': prorata_payment['id'],
            'pix_qr_code': prorata_payment.get('pixQrCode'),
            'pix_copy_paste': prorata_payment.get('pixCopyPaste')
        }
```

---

## 🔔 WEBHOOKS ASAAS

### Endpoint Principal

```python
# apps/billing/views.py

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import hashlib
import hmac

@csrf_exempt
def asaas_webhook(request):
    """
    POST /webhooks/asaas/
    
    Recebe eventos do Asaas
    """
    
    # 1. Validar assinatura (security)
    signature = request.headers.get('asaas-access-token')
    
    if signature != settings.ASAAS_WEBHOOK_TOKEN:
        return HttpResponse('Unauthorized', status=401)
    
    # 2. Parse payload
    payload = json.loads(request.body)
    event_type = payload.get('event')
    
    # 3. Registrar evento (auditoria)
    webhook_event = AsaasWebhookEvent.objects.create(
        event_type=event_type,
        event_id=payload.get('id', str(uuid.uuid4())),
        payload=payload
    )
    
    # 4. Processar evento
    try:
        if event_type == 'PAYMENT_RECEIVED':
            handle_payment_received(payload)
        
        elif event_type == 'PAYMENT_CONFIRMED':
            handle_payment_confirmed(payload)
        
        elif event_type == 'PAYMENT_OVERDUE':
            handle_payment_overdue(payload)
        
        elif event_type == 'SUBSCRIPTION_UPDATED':
            handle_subscription_updated(payload)
        
        elif event_type == 'SUBSCRIPTION_DELETED':
            handle_subscription_deleted(payload)
        
        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        
    except Exception as e:
        webhook_event.error = str(e)
        webhook_event.save()
        logger.exception(f"Erro ao processar webhook: {e}")
    
    return HttpResponse('OK', status=200)


def handle_payment_received(payload):
    """Pagamento recebido e confirmado"""
    
    payment_data = payload.get('payment', {})
    payment_id = payment_data.get('id')
    
    # Buscar pagamento
    try:
        payment = AsaasPayment.objects.get(asaas_payment_id=payment_id)
    except AsaasPayment.DoesNotExist:
        logger.warning(f"Payment {payment_id} not found in database")
        return
    
    # Atualizar status
    payment.status = 'RECEIVED'
    payment.payment_date = timezone.now().date()
    payment.confirmed_date = timezone.now().date()
    payment.save()
    
    # Ativar tenant (se estava suspenso)
    tenant = payment.tenant
    
    if tenant.status != 'active':
        tenant.status = 'active'
        tenant.save()
        
        logger.info(f"Tenant {tenant.name} ativado após pagamento")


def handle_payment_overdue(payload):
    """Pagamento vencido (atraso)"""
    
    payment_data = payload.get('payment', {})
    payment_id = payment_data.get('id')
    
    try:
        payment = AsaasPayment.objects.get(asaas_payment_id=payment_id)
    except AsaasPayment.DoesNotExist:
        return
    
    payment.status = 'OVERDUE'
    payment.save()
    
    # Suspender tenant
    tenant = payment.tenant
    tenant.status = 'suspended'
    tenant.save()
    
    # Notificar por email
    send_email(
        to=tenant.email,
        subject='Pagamento em Atraso - ALREA',
        message='Seu pagamento está em atraso. Regularize para continuar usando.'
    )
    
    logger.warning(f"Tenant {tenant.name} suspenso por inadimplência")
```

---

## 🎨 INTERFACE DO CLIENTE

### Página: Meu Plano e Faturamento

```tsx
// pages/BillingPage.tsx

┌─────────────────────────────────────────────────────┐
│ 💳 Plano e Faturamento                              │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─ Assinatura Ativa ────────────────────────────┐ │
│ │                                               │ │
│ │ Plano: Starter                                │ │
│ │ Status: 🟢 Ativa                              │ │
│ │ Próximo vencimento: 15/11/2025 (em 7 dias)   │ │
│ │                                               │ │
│ │ Valor base: R$ 49,00/mês                      │ │
│ │ Recursos extras: R$ 40,00/mês                 │ │
│ │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │ │
│ │ Total mensal: R$ 89,00                        │ │
│ │                                               │ │
│ │ [Alterar Plano] [Cancelar Assinatura]        │ │
│ └───────────────────────────────────────────────┘ │
│                                                     │
│ ┌─ Recursos Extras ──────────────────────────────┐│
│ │                                                ││
│ │ 📱 Instâncias WhatsApp                         ││
│ │    Incluídas: 2                                ││
│ │    Extras: +2 (R$ 40/mês)                      ││
│ │    Total: 4 instâncias                         ││
│ │    [Adicionar] [Remover]                       ││
│ │                                                ││
│ │ 📊 Slots de Campanha                           ││
│ │    Incluídos: 5/mês                            ││
│ │    Extras: 0                                   ││
│ │    [Adicionar Pacote] (R$ 10/mês = +5 slots)  ││
│ │                                                ││
│ └────────────────────────────────────────────────┘│
│                                                     │
│ ┌─ Histórico de Faturas ─────────────────────────┐│
│ │                                                ││
│ │ 15/10/2025  R$ 49,00  ✅ Pago (Plano)         ││
│ │ 08/11/2025  R$ 9,33   ✅ Pago (Prorata)       ││
│ │ 15/11/2025  R$ 89,00  ⏳ Aguardando           ││
│ │                                                ││
│ │ [Ver Todas as Faturas]                         ││
│ └────────────────────────────────────────────────┘│
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## ⏱️ CRONOGRAMA DE IMPLEMENTAÇÃO

### Timeline Detalhada (3-4 dias)

```
DIA 1: Setup Asaas + Customers (4h)
──────────────────────────────────────────────
✅ Criar conta Asaas (sandbox + produção)
✅ Obter API keys e webhook token
✅ Configurar settings.py
✅ Instalar dependências (requests)
✅ AsaasService (cliente API)
✅ Model: AsaasCustomer
✅ Migration
✅ create_customer() funcionando
✅ Testes: Criar customer via shell

DIA 2: Subscriptions + Primeiro Pagamento (5h)
──────────────────────────────────────────────
✅ Models: AsaasSubscription, AsaasPayment
✅ Migrations
✅ BillingService.create_subscription()
✅ API Endpoint: POST /billing/subscribe/
✅ Testar criação de subscription
✅ Testar PIX (QR Code)
✅ Testar Boleto
✅ Frontend: Página de planos
✅ Frontend: Mostrar QR Code PIX

DIA 3: Webhooks + Ativação (4h)
──────────────────────────────────────────────
✅ Endpoint: POST /webhooks/asaas/
✅ Validar assinatura webhook
✅ Model: AsaasWebhookEvent
✅ handle_payment_received() → Ativar tenant
✅ handle_payment_overdue() → Suspender tenant
✅ Configurar webhook no Asaas (admin)
✅ Testar com sandbox
✅ Logs de webhook

DIA 4: Recursos Extras com Prorata (5h)
──────────────────────────────────────────────
✅ Model: SubscriptionExtra
✅ Migration
✅ BillingService.add_extra_instances()
✅ Cálculo de prorata
✅ API: POST /billing/add-extra-instances/
✅ Cobrar prorata no Asaas
✅ Atualizar subscription value
✅ Frontend: Modal de adicionar recursos
✅ Frontend: Mostrar QR Code prorata
✅ Testes completos

TOTAL: 18 horas = 3-4 dias ✅
```

---

## 🎯 COMPLEXIDADE RESUMIDA

```
┌─────────────────────────────┬────────────┬──────────┐
│ Funcionalidade              │ Complexidade│ Tempo    │
├─────────────────────────────┼────────────┼──────────┤
│ Setup Asaas                 │ ⭐         │ 0.5 dia  │
│ Criar customers             │ ⭐         │ 0.5 dia  │
│ Assinaturas (criar/renovar) │ ⭐⭐       │ 1 dia    │
│ Webhooks (básicos)          │ ⭐⭐       │ 1 dia    │
│ Recursos extras + Prorata   │ ⭐⭐       │ 1 dia    │
│ UI de billing               │ ⭐⭐       │ 1 dia    │
├─────────────────────────────┼────────────┼──────────┤
│ TOTAL                       │ BAIXA-MÉDIA│ 3-4 DIAS │
└─────────────────────────────┴────────────┴──────────┘
```

### Por que é simples:

```
✅ Asaas calcula prorata automaticamente
✅ Sem tracking complexo de uso
✅ Sem agregações mensais
✅ Sem cálculos de excedente
✅ Webhook simples (4-5 eventos apenas)
✅ SDK direto com requests (não precisa lib externa)
✅ Documentação Asaas suficiente
```

---

## 💡 VANTAGENS DO MODELO

### Para o Cliente

```
✅ Previsibilidade total (valor fixo mensal)
✅ Sem surpresas na fatura
✅ Flexibilidade (adiciona recursos quando quiser)
✅ Prorata justo (paga só dias restantes)
✅ Múltiplas formas de pagamento (PIX, Boleto, Cartão)
✅ Tudo vence junto (data unificada)
```

### Para o Negócio

```
✅ Receita recorrente previsível (MRR)
✅ Upsell fácil (adicionar recursos)
✅ Churn controlado (sem cobranças surpresa)
✅ Implementação rápida (3-4 dias)
✅ Manutenção simples (poucos bugs)
✅ Escalável (Asaas aguenta volume)
```

---

## 🚀 ROADMAP FINAL COMPLETO

```
SEMANA 1 (Dia 1-3):
├─ Sistema de Campanhas MVP
├─ Backend + Celery + Frontend
├─ Disparos funcionando
└─ ⏱️ 2-3 dias

SEMANA 2 (Dia 4-7):
├─ Integração Asaas
├─ Assinaturas + Webhooks
├─ Recursos extras com prorata
├─ UI de billing completa
└─ ⏱️ 3-4 dias

TOTAL: 6-7 dias
✅ SISTEMA COMPLETO E VENDÁVEL! 🎉
```

---

## 📌 CHECKLIST DE IMPLEMENTAÇÃO

### Backend

- [ ] Models criados (AsaasCustomer, AsaasSubscription, AsaasPayment, SubscriptionExtra)
- [ ] Migrations rodando
- [ ] AsaasService (cliente API) funcionando
- [ ] BillingService implementado
- [ ] create_customer() testado
- [ ] create_subscription() testado (PIX, Boleto, Cartão)
- [ ] add_extra_instances() testado
- [ ] Webhook endpoint configurado
- [ ] Validação de webhook funcionando
- [ ] Handlers de eventos implementados

### Frontend

- [ ] Página de planos (pricing table)
- [ ] Fluxo de assinatura (escolher plano → pagar)
- [ ] Exibir QR Code PIX
- [ ] Exibir boleto
- [ ] Página "Meu Plano" (status, próximo vencimento)
- [ ] Modal "Adicionar Recursos"
- [ ] Cálculo de prorata visual
- [ ] Histórico de faturas
- [ ] Botão de upgrade/downgrade
- [ ] Botão de cancelamento

### Testes

- [ ] Criar subscription sandbox
- [ ] Pagar com PIX teste
- [ ] Pagar com Boleto teste
- [ ] Webhook ativa tenant
- [ ] Adicionar instância (prorata)
- [ ] Verificar valor próxima fatura
- [ ] Suspender por inadimplência
- [ ] Cancelar assinatura

### Produção

- [ ] Migrar para API keys de produção
- [ ] Configurar webhook URL produção
- [ ] SSL válido no webhook endpoint
- [ ] Logs estruturados
- [ ] Monitoramento de webhooks
- [ ] Alertas de falha

---

## ✅ RESUMO EXECUTIVO

### Modelo de Cobrança

```
Assinatura Mensal Fixa + Recursos Extras com Prorata

Exemplo:
  Plano Pro: R$ 149/mês (fixo)
  + 2 Instâncias extras: R$ 40/mês
  = R$ 189/mês
  
  Adicionar no meio do mês:
    → Cobra prorata dos dias restantes
    → Próximas faturas já vêm com novo valor
    → Tudo vence junto
```

### Complexidade

```
BAIXA-MÉDIA ⭐⭐

- Asaas faz cálculos automaticamente
- Webhooks simples
- Sem tracking complexo
```

### Tempo de Implementação

```
3-4 dias após sistema de campanhas pronto

Sistema completo: 6-7 dias
```

### Custo Asaas (Referência)

```
Taxas Asaas:
- Cartão de crédito: 2,99% + R$ 0,49
- PIX: R$ 0,99 (fixo)
- Boleto: R$ 2,99 (fixo)

Mensalidade Asaas: Grátis até R$ 2.000/mês
Acima: 1,5% do volume
```

---

**Última Atualização:** 2025-10-08  
**Versão:** 1.0.0  
**Autor:** ALREA Development Team

