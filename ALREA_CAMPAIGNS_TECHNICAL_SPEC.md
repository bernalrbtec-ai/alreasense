# 🚀 ALREA CAMPAIGNS - Especificação Técnica Completa

> **Projeto:** ALREA - Plataforma Multi-Produto SaaS  
> **Módulo:** Sistema de Campanhas de Disparo WhatsApp  
> **Versão:** 2.0.0  
> **Data:** 2025-10-08  
> **Autor:** ALREA Development Team  
> **Confidencial:** Não mencionar infraestrutura específica externamente

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Arquitetura de Produtos e Planos](#arquitetura-de-produtos-e-planos)
3. [Arquitetura do Sistema](#arquitetura-do-sistema)
4. [Modelagem de Dados](#modelagem-de-dados)
5. [API REST Endpoints](#api-rest-endpoints)
6. [Celery Tasks](#celery-tasks)
7. [Frontend Components](#frontend-components)
8. [Fluxos de Negócio](#fluxos-de-negócio)
9. [Sistema de Métricas](#sistema-de-métricas)
10. [Segurança e Performance](#segurança-e-performance)
11. [Deploy e Infraestrutura](#deploy-e-infraestrutura)

---

## 🎯 VISÃO GERAL

### Objetivo do Sistema

O módulo **ALREA Campaigns** permite aos clientes criar e gerenciar campanhas de disparo em massa via WhatsApp, com:

- ✅ Múltiplas instâncias WhatsApp simultâneas
- ✅ Rotação inteligente de mensagens (até 5 por campanha)
- ✅ Controle granular de horários e períodos
- ✅ Delays randomizados entre envios
- ✅ Pausar/Retomar/Encerrar em tempo real
- ✅ Logs completos e métricas detalhadas
- ✅ Preview de mensagens com variáveis
- ✅ Multi-tenant com isolamento total

### Premissas de Negócio

1. **1 instância = 1 campanha ativa por vez**
2. **Campanhas são criadas como RASCUNHO** (draft)
3. **Usuário escolhe quando iniciar** após criação
4. **Cada instância tem configurações próprias** (horários, delays)
5. **Sistema respeita rigorosamente** pausas, horários e feriados
6. **Logs auditáveis** de todas as ações

---

## 🏢 ARQUITETURA DE PRODUTOS E PLANOS

### Visão Geral

A plataforma ALREA é **multi-produto** com sistema de billing flexível:

- **Produtos base** incluídos nos planos
- **Add-ons** que podem ser contratados separadamente
- **API Pública** como produto premium/add-on
- **Preços customizáveis** via admin/settings

### Produtos da Plataforma

```
ALREA (Plataforma SaaS)
│
├── 1. ALREA Flow 📤
│   ├── Descrição: Campanhas de disparo WhatsApp
│   ├── Features: Múltiplas mensagens, rotação, agendamento
│   ├── Acesso: UI Web + API Interna
│   └── Billing: Incluído em planos (Starter+)
│
├── 2. ALREA Sense 🧠
│   ├── Descrição: Análise de sentimento e satisfação
│   ├── Features: IA, embeddings, busca semântica
│   ├── Acesso: UI Web + API Interna
│   └── Billing: Incluído em planos (Pro+)
│
├── 3. ALREA API Pública 🔌 (Premium/Add-on)
│   ├── Descrição: Integração programática externa
│   ├── Features: REST endpoints, webhooks, docs Swagger
│   ├── Acesso: API Key (sem UI)
│   └── Billing: 
│       ├── Plano "API Only": R$ 99/mês
│       ├── Add-on para Starter/Pro: +R$ 79/mês
│       └── Enterprise: Incluído
│
└── 4. Futuros (Roadmap)
    ├── ALREA Reports 📊 (Relatórios avançados)
    ├── ALREA CRM 🤝 (Integração CRM)
    └── ALREA Automations ⚡ (Workflows)
```

### Diferença: API Interna vs API Pública

```
┌─────────────────────────────────────────────────────────┐
│ API INTERNA (Básica) - TODOS os planos têm             │
├─────────────────────────────────────────────────────────┤
│ Autenticação: JWT (usuário faz login)                  │
│ Uso: Frontend ALREA → Backend ALREA                    │
│ Endpoints: /api/campaigns/, /api/contacts/, etc        │
│ Propósito: Suportar interface web                      │
│ Documentação: Não exposta publicamente                 │
│ ✅ Incluído em TODOS os planos (sem custo adicional)   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ API PÚBLICA (Avançada) - Apenas planos específicos     │
├─────────────────────────────────────────────────────────┤
│ Autenticação: API Key (sem login)                      │
│ Uso: Sistema Externo do Cliente → ALREA                │
│ Endpoints: /api/v1/public/*                            │
│ Propósito: Integrações, revenda, white-label           │
│ Documentação: Swagger/OpenAPI público                  │
│ Rate Limiting: Por tenant                              │
│ Webhooks: Callbacks de eventos                         │
│ 💰 PAGO:                                               │
│   • Plano "API Only": R$ 99/mês                        │
│   • Enterprise: Incluído                               │
│   • Add-on para outros: +R$ 79/mês                     │
└─────────────────────────────────────────────────────────┘
```

### Modelagem de Produtos

```python
# apps/billing/models.py

class Product(models.Model):
    """
    Produtos/Módulos da plataforma ALREA
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    slug = models.SlugField(unique=True)  # 'flow', 'sense', 'api_public'
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Add-on configuration
    is_addon = models.BooleanField(
        default=False,
        help_text="Produto pode ser adicionado a qualquer plano como extra"
    )
    addon_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Preço mensal se contratado como add-on (customizável)"
    )
    
    # Apps Django relacionados
    django_apps = models.JSONField(
        default=list,
        help_text="Ex: ['apps.campaigns', 'apps.messages']"
    )
    
    # URL prefixes controlados
    url_prefixes = models.JSONField(
        default=list,
        help_text="Ex: ['/api/campaigns/', '/campaigns/']"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_product'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
    
    def __str__(self):
        return self.name


class Plan(models.Model):
    """
    Planos de assinatura
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Preço base mensal (customizável)"
    )
    
    # Relacionamento com produtos
    products = models.ManyToManyField(
        Product,
        through='PlanProduct',
        related_name='plans'
    )
    
    # Configurações especiais
    ui_access = models.BooleanField(
        default=True,
        help_text="Se False, tenant só acessa via API (ex: plano API Only)"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_plan'
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - R$ {self.price}"
    
    def has_product(self, product_slug):
        """Verifica se plano inclui produto"""
        return self.plan_products.filter(
            product__slug=product_slug,
            is_included=True
        ).exists()
    
    def get_product_limits(self, product_slug):
        """Retorna limites do produto neste plano"""
        try:
            pp = self.plan_products.get(product__slug=product_slug)
            return pp.limits
        except PlanProduct.DoesNotExist:
            return {}


class PlanProduct(models.Model):
    """
    Relacionamento N:N entre Plano e Produto
    Define se produto está incluído e seus limites
    """
    
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='plan_products'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )
    
    is_included = models.BooleanField(
        default=True,
        help_text="Produto incluído no plano base"
    )
    
    limits = models.JSONField(
        default=dict,
        help_text="Limites específicos deste produto neste plano (customizável)"
    )
    # Exemplos:
    # Flow: {"max_campaigns": 20, "max_contacts": 5000, "max_instances": 10}
    # Sense: {"max_analyses_per_month": 5000, "retention_days": 180}
    # API: {"requests_per_day": 10000, "rate_limit_per_minute": 100}
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_plan_product'
        unique_together = ['plan', 'product']
    
    def __str__(self):
        return f"{self.plan.name} → {self.product.name}"


class TenantProduct(models.Model):
    """
    Produtos ativos de um tenant específico
    
    Pode vir de:
    - Plano base (is_addon=False)
    - Add-on contratado (is_addon=True)
    """
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='tenant_products'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )
    
    is_addon = models.BooleanField(
        default=False,
        help_text="True se foi contratado separadamente (não do plano base)"
    )
    addon_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Valor adicional mensal (se add-on)"
    )
    
    # Limites customizados (sobrescreve do plano se necessário)
    custom_limits = models.JSONField(
        default=dict,
        blank=True
    )
    
    # API Key (gerada se produto = api_public)
    api_key = models.CharField(
        max_length=255,
        blank=True,
        unique=True,
        help_text="API Key para autenticação (se aplicável)"
    )
    
    is_active = models.BooleanField(default=True)
    activated_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'billing_tenant_product'
        unique_together = ['tenant', 'product']
    
    def __str__(self):
        addon_label = " (Add-on)" if self.is_addon else ""
        return f"{self.tenant.name} - {self.product.name}{addon_label}"
```

### Seed de Produtos e Planos

```python
# apps/billing/management/commands/seed_products.py

PRODUCTS = [
    {
        'slug': 'flow',
        'name': 'ALREA Flow',
        'description': 'Sistema de campanhas de disparo WhatsApp',
        'is_addon': False,
        'django_apps': ['apps.campaigns', 'apps.contacts', 'apps.connections'],
        'url_prefixes': ['/api/campaigns/', '/api/contacts/', '/campaigns/']
    },
    {
        'slug': 'sense',
        'name': 'ALREA Sense',
        'description': 'Análise de sentimento e satisfação com IA',
        'is_addon': False,
        'django_apps': ['apps.ai', 'apps.chat_messages'],
        'url_prefixes': ['/api/analyses/', '/api/messages/', '/analyses/']
    },
    {
        'slug': 'api_public',
        'name': 'ALREA API Pública',
        'description': 'Integração programática para sistemas externos',
        'is_addon': True,  # ⭐ Pode ser add-on
        'addon_price': 79.00,  # ⭐ Valor customizável
        'url_prefixes': ['/api/v1/public/']
    }
]

PLANS = [
    {
        'slug': 'starter',
        'name': 'Starter',
        'description': 'Ideal para pequenas empresas',
        'price': 49.90,  # ⭐ Valor customizável
        'ui_access': True,
        'products': {
            'flow': {
                'included': True,
                'limits': {
                    'max_campaigns': 5,
                    'max_contacts_per_campaign': 500,
                    'max_messages_per_campaign': 1000,
                    'max_instances': 2
                }
            },
            'sense': {'included': False},
            'api_public': {'included': False}  # Disponível como add-on
        }
    },
    {
        'slug': 'pro',
        'name': 'Pro',
        'description': 'Para empresas em crescimento',
        'price': 149.90,  # ⭐ Valor customizável
        'ui_access': True,
        'products': {
            'flow': {
                'included': True,
                'limits': {
                    'max_campaigns': 20,
                    'max_contacts_per_campaign': 5000,
                    'max_instances': 10
                }
            },
            'sense': {
                'included': True,
                'limits': {
                    'max_analyses_per_month': 5000,
                    'retention_days': 180
                }
            },
            'api_public': {'included': False}  # Disponível como add-on
        }
    },
    {
        'slug': 'api_only',
        'name': 'API Only',
        'description': 'Para desenvolvedores e integrações',
        'price': 99.00,  # ⭐ Valor customizável
        'ui_access': False,  # ⭐ Sem acesso ao frontend
        'products': {
            'flow': {'included': False},
            'sense': {'included': False},
            'api_public': {
                'included': True,
                'limits': {
                    'requests_per_day': 50000,
                    'messages_per_day': 5000,
                    'rate_limit_per_minute': 100,
                    'webhooks_enabled': True
                }
            }
        }
    },
    {
        'slug': 'enterprise',
        'name': 'Enterprise',
        'description': 'Solução completa para grandes empresas',
        'price': 499.00,  # ⭐ Valor customizável
        'ui_access': True,
        'products': {
            'flow': {
                'included': True,
                'limits': {'unlimited': True}
            },
            'sense': {
                'included': True,
                'limits': {'unlimited': True}
            },
            'api_public': {
                'included': True,  # ✅ Incluído (não é add-on)
                'limits': {'unlimited': True}
            }
        }
    }
]

# ⚠️ NOTA: Todos os valores de preços e limites são CUSTOMIZÁVEIS
# Ajuste via Admin Django ou settings.py conforme necessário
```

### Controle de Acesso aos Produtos

```python
# apps/tenancy/models.py

class Tenant(models.Model):
    # ... campos existentes ...
    
    current_plan = models.ForeignKey(
        'billing.Plan',
        on_delete=models.PROTECT,
        related_name='tenants'
    )
    
    @cached_property
    def active_products(self):
        """
        Lista de slugs de produtos ativos
        
        Inclui:
        - Produtos do plano base
        - Add-ons contratados
        """
        products = set()
        
        # Produtos do plano base
        base_products = self.current_plan.plan_products.filter(
            is_included=True
        ).values_list('product__slug', flat=True)
        products.update(base_products)
        
        # Add-ons contratados
        addon_products = self.tenant_products.filter(
            is_addon=True,
            is_active=True
        ).values_list('product__slug', flat=True)
        products.update(addon_products)
        
        return list(products)
    
    def has_product(self, product_slug):
        """
        Verifica se tenant tem acesso ao produto
        
        Usa cache Redis (5 min TTL) para performance
        """
        cache_key = f'tenant:{self.id}:product:{product_slug}'
        
        has_it = cache.get(cache_key)
        if has_it is not None:
            return has_it
        
        has_it = product_slug in self.active_products
        cache.set(cache_key, has_it, timeout=300)
        
        return has_it
    
    def get_product_limits(self, product_slug):
        """Retorna limites do produto para este tenant"""
        
        # Verificar se tem limit customizado (add-on ou override)
        try:
            tp = self.tenant_products.get(
                product__slug=product_slug,
                is_active=True
            )
            if tp.custom_limits:
                return tp.custom_limits
        except TenantProduct.DoesNotExist:
            pass
        
        # Usar limites do plano
        return self.current_plan.get_product_limits(product_slug)
    
    def has_public_api(self):
        """Verifica se tem acesso à API Pública"""
        return self.has_product('api_public')
    
    def get_public_api_key(self):
        """Retorna API Key para API Pública"""
        try:
            tp = self.tenant_products.get(
                product__slug='api_public',
                is_active=True
            )
            return tp.api_key or self.generate_api_key()
        except TenantProduct.DoesNotExist:
            return None
    
    def generate_api_key(self):
        """Gera API Key única para tenant"""
        import secrets
        api_key = f"alr_{secrets.token_urlsafe(32)}"
        
        # Salvar no TenantProduct
        tp = self.tenant_products.get(product__slug='api_public')
        tp.api_key = api_key
        tp.save(update_fields=['api_key'])
        
        return api_key
    
    @property
    def monthly_total(self):
        """Valor total mensal (plano + add-ons)"""
        total = self.current_plan.price
        
        # Somar add-ons ativos
        addons = self.tenant_products.filter(is_addon=True, is_active=True)
        for addon in addons:
            total += addon.addon_price
        
        return total
```

### Middleware de Controle de Acesso

```python
# apps/common/middleware.py

class ProductAccessMiddleware:
    """
    Middleware que valida acesso a produtos baseado em URL
    """
    
    PRODUCT_URL_MAP = {
        '/api/campaigns/': 'flow',
        '/api/contacts/': 'flow',
        '/campaigns/': 'flow',
        
        '/api/analyses/': 'sense',
        '/api/messages/': 'sense',
        '/analyses/': 'sense',
        
        '/api/v1/public/': 'api_public',
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Apenas para requests autenticados
        if not hasattr(request, 'tenant'):
            return self.get_response(request)
        
        # Verificar se URL requer produto específico
        for url_prefix, product_slug in self.PRODUCT_URL_MAP.items():
            if request.path.startswith(url_prefix):
                
                if not request.tenant.has_product(product_slug):
                    return JsonResponse({
                        'error': 'PRODUCT_NOT_AVAILABLE',
                        'product': product_slug,
                        'message': f'Produto {product_slug.upper()} não disponível no seu plano',
                        'current_plan': request.tenant.current_plan.name,
                        'upgrade_url': '/billing/upgrade',
                        'addon_available': Product.objects.get(slug=product_slug).is_addon,
                        'addon_price': Product.objects.get(slug=product_slug).addon_price
                    }, status=403)
        
        return self.get_response(request)
```

### Comparação de Planos (Tabela Visual)

```
┌────────────────┬─────────┬──────┬──────────┬────────────┐
│ Feature/Produto│ Starter │ Pro  │ API Only │ Enterprise │
├────────────────┼─────────┼──────┼──────────┼────────────┤
│ Preço Base     │ R$ 49   │ R$149│ R$ 99    │ R$ 499     │
├────────────────┼─────────┼──────┼──────────┼────────────┤
│ ALREA Flow     │ ✅ 5    │ ✅ 20│ ❌       │ ✅ ∞       │
│ (Campanhas)    │ camp.   │ camp.│          │            │
├────────────────┼─────────┼──────┼──────────┼────────────┤
│ ALREA Sense    │ ❌      │ ✅   │ ❌       │ ✅ ∞       │
│ (IA/Análises)  │         │ 5k/mês│         │            │
├────────────────┼─────────┼──────┼──────────┼────────────┤
│ API Pública    │ +R$ 79  │+R$ 79│ ✅ Inc.  │ ✅ Inc.    │
│ (Integração)   │ (add-on)│(add-on)│        │            │
├────────────────┼─────────┼──────┼──────────┼────────────┤
│ UI Web Access  │ ✅      │ ✅   │ ❌       │ ✅         │
├────────────────┼─────────┼──────┼──────────┼────────────┤
│ Total c/ API   │ R$ 128  │ R$228│ R$ 99    │ R$ 499     │
└────────────────┴─────────┴──────┴──────────┴────────────┘

⚠️ NOTA: Valores são EXEMPLOS e totalmente customizáveis
         Ajuste via Admin Django conforme estratégia de pricing
```

---

## 🏗️ ARQUITETURA DO SISTEMA

### Stack Tecnológico

```yaml
Backend:
  - Framework: Django 5.0+
  - API: Django REST Framework 3.14+
  - Tasks: Celery 5.3+ com Redis/RabbitMQ
  - Database: PostgreSQL 15+
  - Cache: Redis 7+
  - WebSocket: Django Channels 4+

Frontend:
  - Framework: React 18+
  - Language: TypeScript 5+
  - Build: Vite 5+
  - Styling: Tailwind CSS 3+
  - Components: shadcn/ui
  - State: Zustand
  - Forms: React Hook Form + Zod

Integrations:
  - WhatsApp: Gateway API Externo
  - Billing: Gateway de Pagamento
  - Auth: JWT
```

### Diagrama de Arquitetura

```
┌────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Dashboard │  │Campaigns │  │ Contacts │  │ Metrics  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└───────┼─────────────┼─────────────┼─────────────┼─────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │ HTTP/REST
        ┌─────────────▼─────────────────────────────────────┐
        │           DJANGO REST API                         │
        │  ┌─────────────────────────────────────────────┐ │
        │  │ ViewSets (Campaigns, Contacts, Instances)   │ │
        │  │ - Permissions (Multi-tenant)                │ │
        │  │ - Serializers (Validation)                  │ │
        │  │ - Services (Business Logic)                 │ │
        │  └─────────────────────────────────────────────┘ │
        └────────┬──────────────────────────┬───────────────┘
                 │                          │
                 ▼                          ▼
        ┌────────────────┐        ┌────────────────────────┐
        │   PostgreSQL   │        │  CELERY + Redis/RMQ    │
        │                │        │                        │
        │ - Campaigns    │        │ ┌──────────────────┐  │
        │ - Contacts     │        │ │ Scheduler Task   │  │
        │ - Messages     │◄───────┤ │ (cada 10s)       │  │
        │ - Logs         │        │ └──────────────────┘  │
        │ - Metrics      │        │                        │
        │                │        │ ┌──────────────────┐  │
        │                │◄───────┤ │ Dispatcher Tasks │  │
        │                │        │ │ (workers/inst.)  │  │
        │                │        │ └──────────────────┘  │
        └────────────────┘        │                        │
                                  │ ┌──────────────────┐  │
                                  │ │ Metrics Task     │  │
                                  │ │ (cada 1h)        │  │
                                  │ └──────────────────┘  │
                                  └────────┬───────────────┘
                                           │
                                           ▼
                                  ┌────────────────────────┐
                                  │   WhatsApp Gateway     │
                                  │   (API Externa)        │
                                  │                        │
                                  │ - Send Messages        │
                                  │ - WebSocket Events     │
                                  │ - Instance Status      │
                                  └────────────────────────┘
```

### Fluxo de Dados - Envio de Mensagem

```
1. Scheduler (Celery Beat - cada 10s)
   ↓
2. Busca campanhas ativas (status='active', is_paused=False)
   ↓
3. Para cada campanha:
   ├─ Verifica horário permitido
   ├─ Verifica instância conectada
   ├─ Pega próximo contato (status='pending')
   ├─ Seleciona mensagem (rotação)
   ├─ Renderiza variáveis
   └─ Enfileira task de envio
   ↓
4. Dispatcher Task (Celery Worker)
   ├─ Valida estado da campanha (dupla checagem)
   ├─ Envia via WhatsApp Gateway API
   ├─ Atualiza status do contato (sent/failed)
   ├─ Incrementa contadores
   └─ Cria log detalhado
   ↓
5. WhatsApp Gateway WebSocket
   ├─ Recebe eventos (delivered, read, responded)
   ├─ Atualiza status em tempo real
   └─ Alimenta métricas
```

---

## 📊 MODELAGEM DE DADOS

### Diagrama ER

```
┌────────────────┐
│    Tenant      │
└───────┬────────┘
        │ 1
        │
        │ N
┌───────▼────────┐         ┌─────────────────┐
│   Campaign     │ 1    N  │ CampaignMessage │
│                │◄────────┤                 │
│ - id (UUID)    │         │ - message_text  │
│ - name         │         │ - order (1-5)   │
│ - status       │         │ - times_sent    │
│ - is_paused    │         │ - response_rate │
│ - instance ───►│         └─────────────────┘
│   (FK)         │
│ - total_       │         ┌─────────────────┐
│   contacts     │ 1    N  │ CampaignContact │
│ - sent_        │◄────────┤                 │
│   messages     │         │ - campaign (FK) │
│                │         │ - contact (FK)  │
│                │         │ - status        │
│                │         │ - sent_at       │
└────────────────┘         │ - responded_at  │
        │                  └─────────────────┘
        │
        │ 1                ┌─────────────────┐
        ├──────────────────┤  CampaignLog    │
        │               N  │                 │
        │                  │ - level         │
        │                  │ - event_type    │
        │                  │ - message       │
        │                  │ - metadata      │
        │                  └─────────────────┘
        │
        │ 1                ┌─────────────────┐
        └──────────────────┤ CampaignMetrics │
                        N  │                 │
                           │ - metric_date   │
                           │ - hour_of_day   │
                           │ - messages_sent │
                           │ - response_rate │
                           └─────────────────┘

┌────────────────┐
│   Contact      │
│                │
│ - name         │
│ - phone        │
│ - tags         │
│ - quem_indicou │
│ - custom_vars  │
└────────────────┘

┌────────────────────┐
│ WhatsAppInstance   │
│                    │
│ - name             │
│ - is_connected     │
│ - morning_start    │
│ - morning_end      │
│ - afternoon_start  │
│ - afternoon_end    │
│ - delay_min_sec    │
│ - delay_max_sec    │
└────────────────────┘

┌────────────────┐
│    Holiday     │
│                │
│ - date         │
│ - name         │
│ - is_national  │
└────────────────┘
```

### Models Detalhados

#### 1. Campaign

```python
# apps/campaigns/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

class Campaign(models.Model):
    """
    Campanha de disparo em massa
    
    Regras:
    - Sempre criada como DRAFT
    - Precisa de pelo menos 1 mensagem e 1 contato para iniciar
    - Só pode ter 1 campanha ACTIVE por instância
    - Pode ser pausada/retomada/cancelada a qualquer momento
    """
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativa'
        PAUSED = 'paused', 'Pausada'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'
    
    class ScheduleType(models.TextChoices):
        IMMEDIATE = 'immediate', 'Imediato'
        BUSINESS_DAYS = 'business_days', 'Apenas Dias Úteis'
        BUSINESS_HOURS = 'business_hours', 'Horário Comercial'
        CUSTOM_PERIOD = 'custom_period', 'Período Personalizado'
    
    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='campaigns'
    )
    name = models.CharField(
        max_length=200,
        help_text="Nome descritivo da campanha"
    )
    description = models.TextField(
        blank=True,
        help_text="Descrição opcional da campanha"
    )
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    is_paused = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag de pausa. Valida antes de CADA envio."
    )
    
    # Relacionamentos
    instance = models.ForeignKey(
        'connections.WhatsAppInstance',
        on_delete=models.PROTECT,
        related_name='campaigns',
        help_text="Instância WhatsApp que executará a campanha"
    )
    
    # Configurações de agendamento
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.IMMEDIATE
    )
    
    # Usado apenas se schedule_type = CUSTOM_PERIOD
    morning_start = models.TimeField(null=True, blank=True, default='09:00')
    morning_end = models.TimeField(null=True, blank=True, default='12:00')
    afternoon_start = models.TimeField(null=True, blank=True, default='14:00')
    afternoon_end = models.TimeField(null=True, blank=True, default='17:00')
    skip_weekends = models.BooleanField(default=True)
    skip_holidays = models.BooleanField(default=True)
    
    # Contadores
    total_contacts = models.IntegerField(
        default=0,
        help_text="Total de contatos na campanha"
    )
    current_contact_index = models.IntegerField(
        default=0,
        help_text="Índice do próximo contato a processar"
    )
    sent_messages = models.IntegerField(
        default=0,
        help_text="Quantidade de mensagens enviadas com sucesso"
    )
    failed_messages = models.IntegerField(
        default=0,
        help_text="Quantidade de mensagens que falharam"
    )
    responded_count = models.IntegerField(
        default=0,
        help_text="Quantidade de contatos que responderam"
    )
    
    # Controle de processamento
    next_scheduled_send = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp do próximo envio agendado"
    )
    last_send_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp do último envio realizado"
    )
    last_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que o scheduler processou esta campanha"
    )
    is_processing = models.BooleanField(
        default=False,
        help_text="Lock para evitar processamento duplicado"
    )
    
    # Timestamps de lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    resumed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Auditoria
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='campaigns_created'
    )
    started_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns_started'
    )
    
    # Tracking de erros
    last_error = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    auto_pause_reason = models.TextField(
        blank=True,
        help_text="Motivo de pausa automática (ex: instância desconectada)"
    )
    
    class Meta:
        db_table = 'campaigns_campaign'
        verbose_name = 'Campanha'
        verbose_name_plural = 'Campanhas'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['tenant', 'status', 'created_at']),
            models.Index(fields=['status', 'is_paused', 'next_scheduled_send']),
            models.Index(fields=['instance', 'status']),
        ]
        
        constraints = [
            # Só 1 campanha ativa por instância
            models.UniqueConstraint(
                fields=['instance'],
                condition=models.Q(status=Status.ACTIVE),
                name='unique_active_campaign_per_instance'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) - {self.tenant.name}"
    
    # Properties
    
    @property
    def progress_percentage(self):
        """Percentual de progresso (0-100)"""
        if self.total_contacts == 0:
            return 0
        return round((self.sent_messages / self.total_contacts) * 100, 1)
    
    @property
    def response_rate(self):
        """Taxa de resposta (%)"""
        if self.sent_messages == 0:
            return 0
        return round((self.responded_count / self.sent_messages) * 100, 1)
    
    @property
    def can_be_started(self):
        """Verifica se campanha pode ser iniciada"""
        return (
            self.status == self.Status.DRAFT and
            self.total_contacts > 0 and
            self.messages.filter(is_active=True).exists() and
            self.instance.is_connected
        )
    
    @property
    def can_be_paused(self):
        """Verifica se campanha pode ser pausada"""
        return self.status == self.Status.ACTIVE and not self.is_paused
    
    @property
    def can_be_resumed(self):
        """Verifica se campanha pode ser retomada"""
        return self.status == self.Status.ACTIVE and self.is_paused
    
    @property
    def can_be_cancelled(self):
        """Verifica se campanha pode ser cancelada"""
        return self.status in [self.Status.DRAFT, self.Status.ACTIVE, self.Status.PAUSED]
    
    @property
    def remaining_contacts(self):
        """Quantidade de contatos restantes"""
        return self.total_contacts - self.sent_messages
    
    # Methods
    
    def start(self, user):
        """
        Inicia a campanha
        
        Raises:
            ValidationError: Se campanha não pode ser iniciada
        """
        from django.core.exceptions import ValidationError
        
        if not self.can_be_started:
            raise ValidationError("Campanha não pode ser iniciada no estado atual")
        
        self.status = self.Status.ACTIVE
        self.is_paused = False
        self.started_at = timezone.now()
        self.started_by = user
        self.next_scheduled_send = timezone.now() + timezone.timedelta(seconds=10)
        self.save(update_fields=[
            'status', 'is_paused', 'started_at', 'started_by', 'next_scheduled_send'
        ])
        
        # Log
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.INFO,
            event_type='campaign_started',
            message=f'Campanha iniciada por {user.email}',
            metadata={'total_contacts': self.total_contacts}
        )
    
    def pause(self, user, reason=''):
        """Pausa a campanha"""
        from django.core.exceptions import ValidationError
        
        if not self.can_be_paused:
            raise ValidationError("Campanha não pode ser pausada")
        
        self.is_paused = True
        self.paused_at = timezone.now()
        self.save(update_fields=['is_paused', 'paused_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.WARNING,
            event_type='campaign_paused',
            message=f'Campanha pausada por {user.email}',
            metadata={'reason': reason}
        )
    
    def resume(self, user):
        """Retoma a campanha"""
        from django.core.exceptions import ValidationError
        
        if not self.can_be_resumed:
            raise ValidationError("Campanha não pode ser retomada")
        
        self.is_paused = False
        self.resumed_at = timezone.now()
        self.next_scheduled_send = timezone.now() + timezone.timedelta(seconds=10)
        self.auto_pause_reason = ''
        self.save(update_fields=[
            'is_paused', 'resumed_at', 'next_scheduled_send', 'auto_pause_reason'
        ])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.INFO,
            event_type='campaign_resumed',
            message=f'Campanha retomada por {user.email}'
        )
    
    def cancel(self, user, reason=''):
        """Cancela a campanha"""
        from django.core.exceptions import ValidationError
        
        if not self.can_be_cancelled:
            raise ValidationError("Campanha não pode ser cancelada")
        
        self.status = self.Status.CANCELLED
        self.is_paused = True
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'is_paused', 'cancelled_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.ERROR,
            event_type='campaign_cancelled',
            message=f'Campanha cancelada por {user.email}',
            metadata={'reason': reason, 'sent_messages': self.sent_messages}
        )
    
    def complete(self):
        """Marca campanha como concluída"""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            level=CampaignLog.Level.SUCCESS,
            event_type='campaign_completed',
            message='Campanha concluída com sucesso',
            metadata={
                'total_contacts': self.total_contacts,
                'sent_messages': self.sent_messages,
                'failed_messages': self.failed_messages,
                'response_rate': self.response_rate
            }
        )
```

#### 2. CampaignMessage

```python
class CampaignMessage(models.Model):
    """
    Mensagem de uma campanha (até 5 por campanha)
    
    Sistema rotaciona entre as mensagens cadastradas.
    Permite medir qual mensagem performa melhor.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    message_text = models.TextField(
        help_text="Texto da mensagem. Use variáveis: {{nome}}, {{quem_indicou}}, {{saudacao}}"
    )
    order = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Ordem da mensagem (1-5)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Se False, não será enviada"
    )
    
    # Métricas
    times_sent = models.IntegerField(
        default=0,
        help_text="Quantas vezes esta mensagem foi enviada"
    )
    response_count = models.IntegerField(
        default=0,
        help_text="Quantas respostas esta mensagem gerou"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_message'
        verbose_name = 'Mensagem de Campanha'
        verbose_name_plural = 'Mensagens de Campanha'
        ordering = ['campaign', 'order']
        
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'order'],
                name='unique_message_order_per_campaign'
            )
        ]
    
    def __str__(self):
        return f"Mensagem {self.order} - {self.campaign.name}"
    
    @property
    def response_rate(self):
        """Taxa de resposta desta mensagem"""
        if self.times_sent == 0:
            return 0
        return round((self.response_count / self.times_sent) * 100, 1)
    
    def render_variables(self, contact, current_datetime=None):
        """
        Renderiza variáveis da mensagem
        
        Variáveis disponíveis:
        - {{nome}}: Nome do contato
        - {{quem_indicou}}: Quem indicou o contato
        - {{saudacao}}: Saudação baseada na hora (Bom dia/Boa tarde/Boa noite)
        - {{dia_semana}}: Dia da semana por extenso
        - Variáveis customizadas do contato
        """
        if current_datetime is None:
            current_datetime = timezone.now()
        
        # Saudação baseada na hora
        hour = current_datetime.hour
        if hour < 12:
            saudacao = "Bom dia"
        elif hour < 18:
            saudacao = "Boa tarde"
        else:
            saudacao = "Boa noite"
        
        # Dia da semana
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 
                'Sexta-feira', 'Sábado', 'Domingo']
        dia_semana = dias[current_datetime.weekday()]
        
        # Renderizar
        rendered = self.message_text
        rendered = rendered.replace('{{nome}}', contact.name or '')
        rendered = rendered.replace('{{quem_indicou}}', contact.quem_indicou or '')
        rendered = rendered.replace('{{saudacao}}', saudacao)
        rendered = rendered.replace('{{dia_semana}}', dia_semana)
        
        # Variáveis customizadas (JSONB)
        if contact.custom_vars:
            for key, value in contact.custom_vars.items():
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        
        return rendered
```

#### 3. CampaignContact

```python
class CampaignContact(models.Model):
    """
    Relacionamento N:N entre Campaign e Contact
    Controla status de envio individual
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        SENT = 'sent', 'Enviada'
        DELIVERED = 'delivered', 'Entregue'
        READ = 'read', 'Lida'
        RESPONDED = 'responded', 'Respondeu'
        FAILED = 'failed', 'Falhou'
        SKIPPED = 'skipped', 'Pulado'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='campaign_contacts'
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.CASCADE,
        related_name='campaigns_participated'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    
    # Qual mensagem foi enviada
    message_sent = models.ForeignKey(
        CampaignMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_to_contacts'
    )
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking Evolution API
    evolution_message_id = models.CharField(max_length=255, blank=True)
    
    # Erros
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_contact'
        verbose_name = 'Contato da Campanha'
        verbose_name_plural = 'Contatos da Campanha'
        
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['contact', 'campaign']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'contact'],
                name='unique_contact_per_campaign'
            )
        ]
    
    def __str__(self):
        return f"{self.contact.name} - {self.campaign.name} ({self.get_status_display()})"
    
    @property
    def response_time_minutes(self):
        """Tempo de resposta em minutos"""
        if not self.sent_at or not self.responded_at:
            return None
        delta = self.responded_at - self.sent_at
        return round(delta.total_seconds() / 60, 1)
```

#### 4. CampaignLog

```python
class CampaignLog(models.Model):
    """
    Log detalhado de eventos da campanha
    Para auditoria e debugging
    """
    
    class Level(models.TextChoices):
        DEBUG = 'debug', 'Debug'
        INFO = 'info', 'Info'
        SUCCESS = 'success', 'Sucesso'
        WARNING = 'warning', 'Aviso'
        ERROR = 'error', 'Erro'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_logs'
    )
    user = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.INFO,
        db_index=True
    )
    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Tipo do evento: campaign_started, message_sent, etc."
    )
    message = models.TextField()
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dados adicionais do evento"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'campaigns_log'
        verbose_name = 'Log de Campanha'
        verbose_name_plural = 'Logs de Campanha'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['campaign', '-created_at']),
            models.Index(fields=['level', '-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.level.upper()}] {self.campaign.name} - {self.message[:50]}"
```

#### 5. CampaignMetrics

```python
class CampaignMetrics(models.Model):
    """
    Métricas agregadas por campanha e hora do dia
    Permite análise de melhor horário de disparo
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    metric_date = models.DateField(db_index=True)
    hour_of_day = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)]
    )
    
    # Métricas
    messages_sent = models.IntegerField(default=0)
    messages_delivered = models.IntegerField(default=0)
    messages_read = models.IntegerField(default=0)
    messages_responded = models.IntegerField(default=0)
    messages_failed = models.IntegerField(default=0)
    
    avg_response_time_minutes = models.FloatField(
        null=True,
        blank=True,
        help_text="Tempo médio de resposta em minutos"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_metrics'
        verbose_name = 'Métrica de Campanha'
        verbose_name_plural = 'Métricas de Campanha'
        
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'metric_date', 'hour_of_day'],
                name='unique_metrics_per_campaign_date_hour'
            )
        ]
        
        indexes = [
            models.Index(fields=['campaign', 'metric_date', 'hour_of_day']),
        ]
    
    @property
    def response_rate(self):
        """Taxa de resposta nesta hora"""
        if self.messages_sent == 0:
            return 0
        return round((self.messages_responded / self.messages_sent) * 100, 1)
```

#### 6. Holiday

```python
class Holiday(models.Model):
    """
    Feriados nacionais/estaduais/municipais
    Sistema pula envios em feriados se configurado
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='holidays',
        null=True,
        blank=True,
        help_text="Se null, é feriado nacional válido para todos"
    )
    
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=200)
    is_national = models.BooleanField(
        default=False,
        help_text="Feriado nacional (vale para todos os tenants)"
    )
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'campaigns_holiday'
        verbose_name = 'Feriado'
        verbose_name_plural = 'Feriados'
        ordering = ['date']
        
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'tenant'],
                name='unique_holiday_per_date_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.date})"
    
    @classmethod
    def is_holiday(cls, date, tenant=None):
        """Verifica se uma data é feriado"""
        query = models.Q(date=date, is_active=True)
        
        if tenant:
            query &= (models.Q(tenant=tenant) | models.Q(is_national=True, tenant__isnull=True))
        else:
            query &= models.Q(is_national=True, tenant__isnull=True)
        
        return cls.objects.filter(query).exists()
```

---

## 🔌 API REST ENDPOINTS

### Base URL
```
/api/v1/campaigns/
```

### Endpoints Principais

#### 1. **Campanhas**

```yaml
GET /api/v1/campaigns/
  Descrição: Lista campanhas do tenant
  Query Params:
    - status: filter by status (draft, active, paused, completed, cancelled)
    - instance_id: filter by instance
    - search: busca por nome
    - ordering: -created_at, name, status
    - page: pagination
    - page_size: default 20
  Response: PaginatedResponse<Campaign[]>

GET /api/v1/campaigns/{id}/
  Descrição: Detalhes de uma campanha
  Response: Campaign (com nested messages, stats)

POST /api/v1/campaigns/
  Descrição: Cria nova campanha (status=draft)
  Body:
    {
      "name": "string",
      "description": "string?",
      "instance_id": "uuid",
      "schedule_type": "immediate|business_days|business_hours|custom_period",
      "morning_start": "09:00",  // se custom_period
      "morning_end": "12:00",
      "afternoon_start": "14:00",
      "afternoon_end": "17:00",
      "skip_weekends": boolean,
      "skip_holidays": boolean,
      "contact_ids": ["uuid"],  // OU contact_tag
      "contact_tag": "string?",
      "messages": [
        {
          "message_text": "string",
          "order": 1
        }
      ]
    }
  Response: 201 Created (Campaign)

PATCH /api/v1/campaigns/{id}/
  Descrição: Atualiza campanha (apenas se status=draft)
  Body: Partial<Campaign>
  Response: 200 OK (Campaign)

DELETE /api/v1/campaigns/{id}/
  Descrição: Deleta campanha (apenas se status=draft)
  Response: 204 No Content

POST /api/v1/campaigns/{id}/start/
  Descrição: Inicia campanha
  Validações:
    - status == draft
    - has messages
    - has contacts
    - instance is connected
    - instance has no other active campaign
  Response: 200 OK (Campaign)

POST /api/v1/campaigns/{id}/pause/
  Descrição: Pausa campanha
  Body: { "reason": "string?" }
  Response: 200 OK (Campaign)

POST /api/v1/campaigns/{id}/resume/
  Descrição: Retoma campanha pausada
  Response: 200 OK (Campaign)

POST /api/v1/campaigns/{id}/cancel/
  Descrição: Cancela campanha
  Body: { "reason": "string?" }
  Response: 200 OK (Campaign)

GET /api/v1/campaigns/{id}/logs/
  Descrição: Logs da campanha
  Query Params:
    - level: debug|info|success|warning|error
    - page, page_size
  Response: PaginatedResponse<CampaignLog[]>

GET /api/v1/campaigns/{id}/metrics/
  Descrição: Métricas agregadas da campanha
  Response:
    {
      "best_message": {
        "message_id": "uuid",
        "message_text": "string",
        "response_rate": 45.2
      },
      "best_hour": {
        "hour": 14,
        "response_rate": 38.5
      },
      "hourly_breakdown": [
        { "hour": 9, "sent": 120, "responded": 35, "rate": 29.2 },
        ...
      ],
      "daily_breakdown": [
        { "date": "2025-10-08", "sent": 450, "responded": 120, "rate": 26.7 },
        ...
      ]
    }

GET /api/v1/campaigns/{id}/contacts/
  Descrição: Lista contatos da campanha com status
  Query Params:
    - status: pending|sent|delivered|read|responded|failed
  Response: PaginatedResponse<CampaignContact[]>
```

#### 2. **Mensagens (até 5 por campanha)**

```yaml
GET /api/v1/campaigns/{campaign_id}/messages/
  Descrição: Lista mensagens da campanha
  Response: CampaignMessage[]

POST /api/v1/campaigns/{campaign_id}/messages/
  Descrição: Adiciona mensagem à campanha manualmente
  Body:
    {
      "message_text": "string",
      "order": 1-5
    }
  Response: 201 Created (CampaignMessage)

POST /api/v1/campaigns/{campaign_id}/messages/generate_variations/
  Descrição: Gera variações de mensagem via IA (N8N)
  Body:
    {
      "original_message": "Olá {{nome}}! Vi que {{quem_indicou}}..."
    }
  Response:
    {
      "original": "Olá {{nome}}!...",
      "variations": [
        "{{saudacao}}, {{nome}}! Como vai?...",
        "Oi {{nome}}! Espero que esteja bem...",
        "Olá! Tudo certo, {{nome}}?...",
        "E aí, {{nome}}! Tudo tranquilo?..."
      ],
      "generated_count": 4
    }
  Nota: Variações NÃO são salvas ainda, retornam para aprovação

POST /api/v1/campaigns/{campaign_id}/messages/save_messages/
  Descrição: Salva mensagens aprovadas pelo usuário
  Body:
    {
      "messages": [
        {
          "text": "Mensagem 1",
          "order": 1,
          "generated_by_ai": false
        },
        {
          "text": "Mensagem 2",
          "order": 2,
          "generated_by_ai": true
        }
      ]
    }
  Response: 201 Created (CampaignMessage[])

GET /api/v1/campaigns/{campaign_id}/messages/{id}/preview/
  Descrição: Preview com 3 contatos reais da campanha
  Query Params:
    - datetime: opcional (default: NOW)
  Response:
    {
      "original_message": "{{saudacao}}, {{nome}}!",
      "previews": [
        {
          "contact_name": "João Silva",
          "contact_phone": "+5511999999999",
          "rendered_message": "Bom dia, João Silva!"
        },
        {
          "contact_name": "Maria Santos",
          "rendered_message": "Bom dia, Maria Santos!"
        },
        {
          "contact_name": "Pedro Costa",
          "rendered_message": "Bom dia, Pedro Costa!"
        }
      ]
    }

GET /api/v1/campaigns/{id}/message_performance/
  Descrição: Análise de performance das mensagens (após campanha rodar)
  Response:
    {
      "performance": [
        {
          "rank": 1,
          "emoji": "🥇",
          "order": 3,
          "message_preview": "Oi {{nome}}! Espero que...",
          "times_sent": 100,
          "response_count": 42,
          "response_rate": 42.0,
          "generated_by_ai": true
        }
      ],
      "best_message": { ... },
      "recommendation": "A Mensagem 3 teve excelente performance (42% de resposta)..."
    }

GET /api/v1/campaigns/suggested_messages/
  Descrição: Mensagens de campanhas anteriores com boa performance
  Response:
    {
      "suggestions": [
        {
          "id": "uuid",
          "campaign_name": "Black Friday 2024",
          "message_text": "Olá {{nome}}!...",
          "times_sent": 250,
          "response_rate": 38.5,
          "response_count": 96
        }
      ]
    }

PATCH /api/v1/campaigns/{campaign_id}/messages/{id}/
  Descrição: Atualiza mensagem (apenas se campanha=draft)
  Body: Partial<CampaignMessage>
  Response: 200 OK (CampaignMessage)

DELETE /api/v1/campaigns/{campaign_id}/messages/{id}/
  Descrição: Remove mensagem (apenas se campanha=draft)
  Response: 204 No Content
```

#### 3. **Instâncias**

```yaml
GET /api/v1/instances/
  Descrição: Lista instâncias do tenant
  Response: WhatsAppInstance[]

GET /api/v1/instances/{id}/availability/
  Descrição: Verifica disponibilidade da instância
  Response:
    {
      "is_connected": true,
      "has_active_campaign": false,
      "available": true,
      "current_campaign": null | {
        "id": "uuid",
        "name": "string",
        "progress": 45.2
      }
    }
```

---

---

## 🔄 WORKERS E PROCESSAMENTO ASSÍNCRONO

### Arquitetura de Processos

O backend Django é composto por **múltiplos processos** trabalhando em conjunto:

```
┌────────────────────────────────────────────────────────┐
│                    BACKEND (Django)                    │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Processo 1: Django Web (Gunicorn/Runserver)     │ │
│  │ - Recebe requests HTTP do frontend               │ │
│  │ - API REST (DRF ViewSets)                        │ │
│  │ - Autenticação, validação                        │ │
│  │ ❌ NÃO envia mensagens                           │ │
│  │ ✅ Apenas atualiza banco e retorna 200 OK        │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Processo 2: Celery Beat (Scheduler)             │ │
│  │ - Roda a cada 10 segundos                        │ │
│  │ - Busca campanhas prontas                        │ │
│  │ - Valida horários e condições                    │ │
│  │ ❌ NÃO envia mensagens                           │ │
│  │ ✅ Enfileira tasks no Redis                      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Processos 3-N: Celery Workers (Dispatchers)     │ │
│  │                                                  │ │
│  │  Worker 1 │ Worker 2 │ Worker 3 │ ... │ Worker N│ │
│  │     ↓     │    ↓     │    ↓     │     │    ↓    │ │
│  │  Task A   │  Task B  │  Task C  │     │  Task N │ │
│  │           │          │          │     │         │ │
│  │ ⭐ AQUI que mensagens são ENVIADAS ⭐           │ │
│  │ - Pega tasks da fila Redis                      │ │
│  │ - Valida estado da campanha                      │ │
│  │ - Envia via WhatsApp Gateway API                 │ │
│  │ - Atualiza banco de dados                        │ │
│  │ - Cria logs                                      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │ PostgreSQL + Redis            │
          └──────────────────────────────┘
```

### Comandos de Execução

```bash
# Desenvolvimento Local

# Terminal 1: Django API
python manage.py runserver

# Terminal 2: Celery Beat (Scheduler)
celery -A alrea_sense beat -l info

# Terminal 3: Celery Workers (Dispatchers)
celery -A alrea_sense worker -c 4 -l info
#                                ↑
#                                └─ 4 workers simultâneos
```

```bash
# Produção

# Processo 1: Django com Gunicorn
gunicorn alrea_sense.wsgi:application --workers 4 --bind 0.0.0.0:8000

# Processo 2: Celery Beat (APENAS 1 instância)
celery -A alrea_sense beat -l info

# Processo 3+: Celery Workers (escalável)
celery -A alrea_sense worker -c 10 -l info
```

### Escalabilidade

**Throughput por número de workers:**

```
 1 worker  → ~20 mensagens/minuto
 3 workers → ~60 mensagens/minuto
 5 workers → ~100 mensagens/minuto
10 workers → ~200 mensagens/minuto
20 workers → ~400 mensagens/minuto

⭐ "Adicionar workers" = aumentar o parâmetro -c (concurrency)
```

**Limitações:**
- Gateway API externa (rate limits)
- Conexões PostgreSQL (max_connections)
- Throughput Redis

---

## 🔄 MÚLTIPLAS CAMPANHAS SIMULTÂNEAS

### Separação e Isolamento

Cada campanha é **completamente isolada** no banco de dados:

```sql
-- Campanha A: Black Friday
campaigns_campaign:
  id: uuid-A
  name: 'Black Friday'
  instance_id: inst-1
  status: 'active'
  is_paused: FALSE

campaigns_campaigncontact:
  campaign_id: uuid-A, contact_id: joao, status: 'pending'
  campaign_id: uuid-A, contact_id: maria, status: 'sent'

-- Campanha B: Natal (pode ter os mesmos contatos)
campaigns_campaign:
  id: uuid-B
  name: 'Natal'
  instance_id: inst-2
  status: 'active'
  is_paused: FALSE

campaigns_campaigncontact:
  campaign_id: uuid-B, contact_id: joao, status: 'pending' ✅
  campaign_id: uuid-B, contact_id: carlos, status: 'pending'

-- ✅ João pode estar em ambas (campanhas diferentes)
-- ❌ João não pode estar 2x na mesma campanha (constraint)
```

**Constraint importante:**

```python
class CampaignContact(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'contact'],
                name='unique_contact_per_campaign'
            )
        ]
```

### Processamento em Loop

O scheduler processa **TODAS** as campanhas prontas em um único loop:

```python
@shared_task
def campaign_scheduler():
    """Roda a cada 10 segundos"""
    now = timezone.now()
    
    # Busca TODAS as campanhas prontas
    ready_campaigns = Campaign.objects.filter(
        status=Campaign.Status.ACTIVE,
        is_paused=False,
        next_scheduled_send__lte=now
    ).select_related('instance', 'tenant')
    
    logger.info(f"📊 {ready_campaigns.count()} campanhas prontas")
    
    # Processa cada uma independentemente
    for campaign in ready_campaigns:
        try:
            # Valida horário
            can_send, reason = is_allowed_to_send(campaign, now)
            
            if not can_send:
                # Calcula próxima janela válida
                next_time = calculate_next_send_time(campaign, now)
                Campaign.objects.filter(id=campaign.id).update(
                    next_scheduled_send=next_time
                )
                continue
            
            # Pega próximo contato DESTA campanha
            contact = get_next_contact(campaign)
            
            # Enfileira task
            send_message_task.apply_async(
                kwargs={'campaign_id': campaign.id, ...}
            )
            
            # Atualiza next_scheduled_send DESTA campanha
            delay = random.randint(20, 50)
            Campaign.objects.filter(id=campaign.id).update(
                next_scheduled_send=now + timedelta(seconds=delay)
            )
            
        except Exception as e:
            # ⭐ Erro em 1 campanha NÃO afeta outras
            logger.exception(f"Erro em {campaign.name}")
            continue  # Pula para próxima
```

### Pausar Uma Campanha Específica

```python
# API Endpoint: POST /campaigns/{id}/pause/
Campaign.objects.filter(id='uuid-B').update(is_paused=True)

# Próxima execução do scheduler (10s):
ready = Campaign.objects.filter(
    status='active',
    is_paused=False,  # ⭐ Campanha B não aparece
    next_scheduled_send__lte=now
)

# Resultado: [Campanha A, Campanha C]
# ✅ Apenas Campanha B pausada
# ✅ Campanhas A e C continuam normalmente
```

---

## 🛡️ PROTEÇÃO ANTI-SPAM (Lock por Telefone)

### Problema

```
João Silva está em 3 campanhas ativas:
- Campanha A (Black Friday)
- Campanha B (Natal)  
- Campanha C (Ano Novo)

Sem proteção:
  T=0s → Recebe mensagem da Campanha A
  T=0s → Recebe mensagem da Campanha B
  T=0s → Recebe mensagem da Campanha C
  
❌ 3 mensagens ao mesmo tempo = SPAM!
```

### Solução: Redis Lock

```python
@shared_task
def send_message_task(self, campaign_id, contact_relation_id, message_id, rendered_message):
    
    contact = get_contact(contact_relation_id)
    
    # ⭐ Tentar adquirir lock exclusivo no número
    lock_key = f'phone_lock:{contact.phone}'
    lock_acquired = redis_client.set(
        lock_key,
        campaign_id,  # Qual campanha está usando
        nx=True,      # Só seta se NÃO existir (atômico)
        ex=60         # TTL: 60 segundos (segurança)
    )
    
    if not lock_acquired:
        # ⭐ Outro worker está usando este número AGORA
        other_campaign = redis_client.get(lock_key).decode()
        
        logger.warning(
            f"⏸ {contact.phone} em uso por {other_campaign}, "
            f"reagendando {campaign.name} para +20s"
        )
        
        # Reagendar esta task para 20s depois
        send_message_task.apply_async(
            kwargs={
                'campaign_id': campaign_id,
                'contact_relation_id': contact_relation_id,
                'message_id': message_id,
                'rendered_message': rendered_message
            },
            countdown=20  # Retry em 20 segundos
        )
        
        return {'status': 'deferred', 'reason': 'phone_in_use'}
    
    # ✅ Lock adquirido com sucesso, pode enviar
    try:
        # Enviar mensagem
        response = whatsapp_gateway.send_text_message(
            instance=campaign.instance,
            phone=contact.phone,
            message=rendered_message
        )
        
        # Atualizar status
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status='sent',
            sent_at=timezone.now()
        )
        
        return {'status': 'success'}
        
    finally:
        # ⭐ SEMPRE liberar o lock (mesmo em caso de erro)
        redis_client.delete(lock_key)
```

### Timeline com Lock

```
T=0s - Scheduler enfileira tasks

Campanha A → Task: Enviar para João (+5511999999999)
Campanha B → Task: Enviar para João (+5511999999999)

───────────────────────────────────────────────────────

T=0.5s - Workers processam (quase simultâneo)

Worker 1 (Campanha A):
  ↓ SET phone_lock:+5511999999999 = "camp-A" NX EX 60
  ↓ ✅ Sucesso! Lock adquirido
  ↓ Envia mensagem (demora ~3s)

Worker 2 (Campanha B) - 0.2s depois:
  ↓ SET phone_lock:+5511999999999 = "camp-B" NX EX 60
  ↓ ❌ Falhou! Chave já existe (Worker 1 tem o lock)
  ↓ GET phone_lock:+5511999999999 → "camp-A"
  ↓ Log: "Número em uso por camp-A"
  ↓ apply_async(..., countdown=20)  # Reagenda
  ↓ return 'deferred'

───────────────────────────────────────────────────────

T=3.5s - Worker 1 finaliza

Worker 1:
  ↓ Mensagem enviada com sucesso
  ↓ DELETE phone_lock:+5511999999999
  ↓ 🔓 Lock liberado

───────────────────────────────────────────────────────

T=20.5s - Task reagendada executa

Worker 2 (retry):
  ↓ SET phone_lock:+5511999999999 = "camp-B" NX EX 60
  ↓ ✅ Sucesso! Lock adquirido (Worker 1 já liberou)
  ↓ Envia mensagem
  ↓ DELETE lock
  ↓ ✅ Concluído

───────────────────────────────────────────────────────

RESULTADO:
João recebeu 2 mensagens com 20 segundos de intervalo ✅
```

---

## 🕐 SISTEMA DE JANELAS E HORÁRIOS

### Tipos de Agendamento

```python
class Campaign(models.Model):
    class ScheduleType(models.TextChoices):
        IMMEDIATE = 'immediate', 'Imediato'
        BUSINESS_DAYS = 'business_days', 'Apenas Dias Úteis (9h-18h)'
        BUSINESS_HOURS = 'business_hours', 'Horário Comercial (9h-18h)'
        CUSTOM_PERIOD = 'custom_period', 'Período Personalizado'
    
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices
    )
    
    # Campos para CUSTOM_PERIOD
    morning_start = models.TimeField(default='09:00')
    morning_end = models.TimeField(default='12:00')
    afternoon_start = models.TimeField(default='14:00')
    afternoon_end = models.TimeField(default='17:00')
    skip_weekends = models.BooleanField(default=True)
    skip_holidays = models.BooleanField(default=True)
```

### Validação com Múltiplas Condições

**Todas as condições ativas devem passar simultaneamente:**

```python
# campaigns/services.py

def is_allowed_to_send(campaign, current_datetime):
    """
    Valida se campanha pode enviar AGORA
    
    Valida MÚLTIPLAS condições:
    1. Dia da semana (útil ou não)
    2. Feriado
    3. Horário do dia (janelas)
    
    TODAS devem passar para retornar True
    """
    hour = current_datetime.hour
    weekday = current_datetime.weekday()  # 0=seg, 6=dom
    today = current_datetime.date()
    current_time = current_datetime.time()
    
    # ════════════════════════════════════════════════════════
    # TIPO 1: IMEDIATO
    # ════════════════════════════════════════════════════════
    if campaign.schedule_type == Campaign.ScheduleType.IMMEDIATE:
        return True, "OK"
    
    # ════════════════════════════════════════════════════════
    # TIPO 2: DIAS ÚTEIS (seg-sex 9h-18h)
    # ════════════════════════════════════════════════════════
    if campaign.schedule_type == Campaign.ScheduleType.BUSINESS_DAYS:
        
        # ⭐ CONDIÇÃO 1: Dia útil (seg-sex)
        if weekday >= 5:
            return False, "fim_de_semana"
        
        # ⭐ CONDIÇÃO 2: Não é feriado
        if Holiday.is_holiday(today, campaign.tenant):
            return False, "feriado"
        
        # ⭐ CONDIÇÃO 3: Horário comercial (9h-18h)
        if not (9 <= hour < 18):
            return False, "fora_horario_comercial"
        
        # ✅ Todas as 3 condições passaram
        return True, "OK"
    
    # ════════════════════════════════════════════════════════
    # TIPO 3: HORÁRIO COMERCIAL (9h-18h qualquer dia)
    # ════════════════════════════════════════════════════════
    if campaign.schedule_type == Campaign.ScheduleType.BUSINESS_HOURS:
        if not (9 <= hour < 18):
            return False, "fora_horario_comercial"
        return True, "OK"
    
    # ════════════════════════════════════════════════════════
    # TIPO 4: PERÍODO PERSONALIZADO
    # ════════════════════════════════════════════════════════
    if campaign.schedule_type == Campaign.ScheduleType.CUSTOM_PERIOD:
        
        # ⭐ CONDIÇÃO 1: Fim de semana (se configurado)
        if campaign.skip_weekends and weekday >= 5:
            return False, "fim_de_semana"
        
        # ⭐ CONDIÇÃO 2: Feriado (se configurado)
        if campaign.skip_holidays and Holiday.is_holiday(today, campaign.tenant):
            return False, "feriado"
        
        # ⭐ CONDIÇÃO 3: Janela manhã OU tarde
        in_morning = (
            campaign.morning_start <= current_time < campaign.morning_end
        )
        in_afternoon = (
            campaign.afternoon_start <= current_time < campaign.afternoon_end
        )
        
        if not (in_morning or in_afternoon):
            return False, "fora_janela_horario"
        
        # ✅ Todas as condições configuradas passaram
        return True, "OK"
    
    return False, "configuracao_invalida"
```

### Retomada Automática

```python
def calculate_next_send_time(campaign, current_datetime):
    """
    Calcula próxima janela válida considerando TODAS as restrições
    
    Exemplo: Sexta 18h com BUSINESS_DAYS
             → Próximo envio: Segunda 9h
    """
    
    can_send, reason = is_allowed_to_send(campaign, current_datetime)
    
    if can_send:
        # Pode enviar agora, delay normal
        delay = random.randint(
            campaign.instance.delay_min_seconds,
            campaign.instance.delay_max_seconds
        )
        return current_datetime + timedelta(seconds=delay)
    
    # ⭐ NÃO pode enviar, calcular próxima janela
    
    # 1. Buscar próximo DIA válido
    next_day = current_datetime.date() + timedelta(days=1)
    
    for attempt in range(30):  # Máximo 30 dias no futuro
        weekday = next_day.weekday()
        
        # Validar fim de semana (se requerido)
        if campaign.skip_weekends and weekday >= 5:
            next_day += timedelta(days=1)
            continue
        
        # Validar feriado (se requerido)
        if campaign.skip_holidays and Holiday.is_holiday(next_day, campaign.tenant):
            next_day += timedelta(days=1)
            continue
        
        # ✅ Dia válido encontrado
        break
    
    # 2. Determinar HORÁRIO de início
    if campaign.schedule_type == Campaign.ScheduleType.CUSTOM_PERIOD:
        start_hour = campaign.morning_start or time(9, 0)
    else:
        start_hour = time(9, 0)
    
    # 3. Combinar data + hora
    next_send = datetime.combine(next_day, start_hour)
    next_send = timezone.make_aware(next_send)
    
    logger.info(
        f"🌅 {campaign.name}: Próximo envio {next_send.strftime('%A %d/%m às %H:%M')}",
        extra={'campaign_id': str(campaign.id)}
    )
    
    return next_send
```

### Exemplo Prático: Sexta 18h → Segunda 9h

```
CENÁRIO:
Campanha: "Black Friday VIP"
Configuração: BUSINESS_DAYS (seg-sex 9h-18h, pula feriados)
Total: 500 contatos

═══════════════════════════════════════════════════════════

SEXTA-FEIRA 17:45
  ↓ is_allowed_to_send(sexta 17:45)
    ├─ weekday = 4 (sexta) ✅ < 5
    ├─ is_holiday = False ✅
    ├─ hour = 17 ✅ < 18
    └─ RETORNA: True, "OK"
  
  ✅ PODE ENVIAR
  → Enfileira contato #450
  → next_scheduled_send = 17:45:30

SEXTA-FEIRA 18:00
  ↓ is_allowed_to_send(sexta 18:00)
    ├─ weekday = 4 ✅
    ├─ is_holiday = False ✅
    ├─ hour = 18 ❌ (18 não é < 18)
    └─ RETORNA: False, "fora_horario_comercial"
  
  ❌ NÃO PODE ENVIAR
  
  ↓ calculate_next_send_time(sexta 18:00)
    ├─ Buscar próximo dia:
    │   Sábado 16/11:
    │   ├─ weekday = 5 ❌ >= 5 (fim de semana)
    │   └─ PULA
    │   
    │   Domingo 17/11:
    │   ├─ weekday = 6 ❌ >= 5 (fim de semana)
    │   └─ PULA
    │   
    │   Segunda 18/11:
    │   ├─ weekday = 0 ✅ < 5 (dia útil)
    │   ├─ is_holiday = False ✅
    │   └─ ✅ DIA VÁLIDO!
    │
    ├─ Horário: 09:00
    └─ RETORNA: Segunda 18/11 09:00
  
  → UPDATE next_scheduled_send = Segunda 09:00

SÁBADO/DOMINGO (Scheduler roda mas...)
  ↓ WHERE next_scheduled_send <= NOW()
  ❌ Campanha não aparece (next_send = Segunda 09:00)

SEGUNDA-FEIRA 09:00 ⭐ RETOMA
  ↓ WHERE next_scheduled_send <= NOW()
  ✅ Campanha aparece!
  
  ↓ is_allowed_to_send(segunda 09:00)
    ├─ weekday = 0 ✅ Dia útil
    ├─ is_holiday = False ✅
    ├─ hour = 9 ✅
    └─ RETORNA: True, "OK"
  
  ✅ RETOMA!
  → Contato #451 (continua de onde parou)
```

---

## ⚙️ CELERY TASKS

### Configuração

```python
# settings.py

CELERY_BROKER_URL = env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', 'redis://localhost:6379/0')

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'America/Sao_Paulo'

# Filas por instância
CELERY_TASK_ROUTES = {
    'campaigns.tasks.send_message_task': {
        'queue': 'default',  # Ou dinâmico baseado em instance_id
    },
}

# Beat schedule
CELERY_BEAT_SCHEDULE = {
    'campaign-scheduler': {
        'task': 'campaigns.tasks.campaign_scheduler',
        'schedule': 10.0,  # A cada 10 segundos
    },
    'aggregate-metrics': {
        'task': 'campaigns.tasks.aggregate_metrics_task',
        'schedule': crontab(minute='*/60'),  # A cada hora
    },
}
```

### Tasks

#### 1. **Scheduler Task**

```python
# campaigns/tasks.py

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db.models import F
import random

logger = get_task_logger(__name__)

@shared_task
def campaign_scheduler():
    """
    Task principal que agenda envios de mensagens
    Roda a cada 10 segundos (Celery Beat)
    
    Fluxo:
    1. Busca campanhas ativas e prontas
    2. Para cada campanha:
       - Valida horário
       - Valida estado
       - Pega próximo contato
       - Seleciona mensagem
       - Enfileira task de envio
       - Calcula próximo agendamento
    """
    from apps.campaigns.models import Campaign, CampaignContact
    from apps.campaigns.services import CampaignSchedulerService
    
    now = timezone.now()
    
    # Buscar campanhas prontas para processar
    ready_campaigns = Campaign.objects.filter(
        status=Campaign.Status.ACTIVE,
        is_paused=False,
        next_scheduled_send__lte=now
    ).select_related('instance', 'tenant')
    
    logger.info(f"📊 Scheduler: {ready_campaigns.count()} campanhas prontas")
    
    scheduler_service = CampaignSchedulerService()
    
    for campaign in ready_campaigns:
        try:
            # Heartbeat
            Campaign.objects.filter(id=campaign.id).update(
                last_heartbeat=now
            )
            
            # Processar campanha
            result = scheduler_service.process_campaign(campaign, now)
            
            if result['status'] == 'sent':
                logger.info(
                    f"📤 Enfileirado: {campaign.name} → {result['contact_name']}",
                    extra={'campaign_id': str(campaign.id)}
                )
            elif result['status'] == 'completed':
                logger.info(
                    f"✅ Campanha {campaign.name} concluída!",
                    extra={'campaign_id': str(campaign.id)}
                )
            elif result['status'] == 'skipped':
                logger.debug(
                    f"⏭ Campanha {campaign.name} pulada: {result['reason']}",
                    extra={'campaign_id': str(campaign.id), 'reason': result['reason']}
                )
                
        except Exception as e:
            logger.exception(
                f"❌ Erro ao processar campanha {campaign.id}: {str(e)}",
                extra={'campaign_id': str(campaign.id), 'error': str(e)}
            )
            
            # Auto-pause em caso de erro crítico
            Campaign.objects.filter(id=campaign.id).update(
                is_paused=True,
                auto_pause_reason=f"Erro no scheduler: {str(e)}"
            )
    
    return {
        'processed': ready_campaigns.count(),
        'timestamp': now.isoformat()
    }
```

#### 2. **Dispatcher Task**

```python
@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=90,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def send_message_task(self, campaign_id, contact_relation_id, message_id, rendered_message):
    """
    Envia uma mensagem via Evolution API
    
    Args:
        campaign_id: UUID da campanha
        contact_relation_id: UUID do CampaignContact
        message_id: UUID da CampaignMessage
        rendered_message: Mensagem já renderizada com variáveis
    
    Returns:
        dict com status do envio
    """
    from apps.campaigns.models import Campaign, CampaignContact, CampaignMessage, CampaignLog
    from apps.campaigns.services import EvolutionAPIService
    
    try:
        # Buscar objetos
        campaign = Campaign.objects.select_related('instance', 'tenant').get(id=campaign_id)
        contact_relation = CampaignContact.objects.select_related('contact').get(id=contact_relation_id)
        message = CampaignMessage.objects.get(id=message_id)
        contact = contact_relation.contact
        
        # ⭐ VALIDAÇÃO CRÍTICA antes de enviar
        if campaign.is_paused:
            logger.warning(
                f"🛑 Campanha {campaign.name} pausada, abortando envio",
                extra={'campaign_id': str(campaign_id)}
            )
            return {'status': 'aborted', 'reason': 'paused'}
        
        if campaign.status != Campaign.Status.ACTIVE:
            logger.warning(
                f"🛑 Campanha {campaign.name} não ativa (status={campaign.status})",
                extra={'campaign_id': str(campaign_id)}
            )
            return {'status': 'aborted', 'reason': 'not_active'}
        
        if not campaign.instance.is_connected:
            logger.error(
                f"🛑 Instância {campaign.instance.name} desconectada",
                extra={'campaign_id': str(campaign_id)}
            )
            
            # Auto-pause
            Campaign.objects.filter(id=campaign_id).update(
                is_paused=True,
                auto_pause_reason="Instância desconectada"
            )
            return {'status': 'aborted', 'reason': 'instance_disconnected'}
        
        # Enviar via WhatsApp Gateway
        logger.info(
            f"📱 Enviando para {contact.name} ({contact.phone}) via {campaign.instance.name}",
            extra={'campaign_id': str(campaign_id), 'contact_id': str(contact.id)}
        )
        
        gateway_service = WhatsAppGatewayService()
        response = gateway_service.send_text_message(
            instance=campaign.instance,
            phone=contact.phone,
            message=rendered_message
        )
        
        # Atualizar status
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status=CampaignContact.Status.SENT,
            sent_at=timezone.now(),
            evolution_message_id=response.get('message_id'),
            message_sent=message
        )
        
        # Incrementar contadores (atomic)
        Campaign.objects.filter(id=campaign_id).update(
            sent_messages=F('sent_messages') + 1,
            last_send_at=timezone.now()
        )
        
        CampaignMessage.objects.filter(id=message_id).update(
            times_sent=F('times_sent') + 1
        )
        
        # Log de sucesso
        CampaignLog.objects.create(
            campaign=campaign,
            contact=contact,
            level=CampaignLog.Level.SUCCESS,
            event_type='message_sent',
            message=f'Mensagem enviada para {contact.name}',
            metadata={
                'evolution_response': response,
                'message_length': len(rendered_message),
                'instance': campaign.instance.name
            }
        )
        
        logger.info(
            f"✅ Enviado com sucesso: {contact.name}",
            extra={'campaign_id': str(campaign_id), 'message_id': response.get('message_id')}
        )
        
        return {'status': 'success', 'message_id': response.get('message_id')}
        
    except Campaign.DoesNotExist:
        logger.error(f"❌ Campanha {campaign_id} não encontrada")
        return {'status': 'error', 'reason': 'campaign_not_found'}
    
    except Exception as e:
        logger.exception(
            f"❌ Erro ao enviar mensagem: {str(e)}",
            extra={'campaign_id': str(campaign_id), 'error': str(e)}
        )
        
        # Marcar como falha
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status=CampaignContact.Status.FAILED,
            error_message=str(e),
            retry_count=F('retry_count') + 1
        )
        
        Campaign.objects.filter(id=campaign_id).update(
            failed_messages=F('failed_messages') + 1,
            last_error=str(e),
            last_error_at=timezone.now()
        )
        
        CampaignLog.objects.create(
            campaign_id=campaign_id,
            contact_id=contact_relation.contact_id if 'contact_relation' in locals() else None,
            level=CampaignLog.Level.ERROR,
            event_type='message_failed',
            message=f'Falha ao enviar: {str(e)}',
            metadata={'error': str(e), 'retry_attempt': self.request.retries}
        )
        
        # Retry se for erro temporário
        if isinstance(e, (ConnectionError, TimeoutError)) and self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
        
        return {'status': 'error', 'reason': str(e)}
```

#### 3. **Metrics Aggregation Task**

```python
@shared_task
def aggregate_metrics_task():
    """
    Agrega métricas de campanhas ativas
    Roda a cada hora
    
    Calcula:
    - Mensagens enviadas/respondidas por hora
    - Taxa de resposta por hora
    - Tempo médio de resposta
    """
    from apps.campaigns.models import Campaign, CampaignMetrics, CampaignContact
    from django.db.models import Count, Avg, Q
    
    now = timezone.now()
    today = now.date()
    current_hour = now.hour
    
    # Campanhas ativas
    active_campaigns = Campaign.objects.filter(
        status__in=[Campaign.Status.ACTIVE, Campaign.Status.PAUSED]
    )
    
    for campaign in active_campaigns:
        # Buscar mensagens enviadas nesta hora
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timezone.timedelta(hours=1)
        
        stats = CampaignContact.objects.filter(
            campaign=campaign,
            sent_at__gte=hour_start,
            sent_at__lt=hour_end
        ).aggregate(
            total_sent=Count('id'),
            total_delivered=Count('id', filter=Q(status__in=['delivered', 'read', 'responded'])),
            total_read=Count('id', filter=Q(status__in=['read', 'responded'])),
            total_responded=Count('id', filter=Q(status='responded')),
            total_failed=Count('id', filter=Q(status='failed')),
            avg_response_time=Avg(
                F('responded_at') - F('sent_at'),
                filter=Q(responded_at__isnull=False)
            )
        )
        
        # Converter timedelta para minutos
        avg_response_minutes = None
        if stats['avg_response_time']:
            avg_response_minutes = stats['avg_response_time'].total_seconds() / 60
        
        # Criar ou atualizar métrica
        CampaignMetrics.objects.update_or_create(
            campaign=campaign,
            metric_date=today,
            hour_of_day=current_hour,
            defaults={
                'messages_sent': stats['total_sent'],
                'messages_delivered': stats['total_delivered'],
                'messages_read': stats['total_read'],
                'messages_responded': stats['total_responded'],
                'messages_failed': stats['total_failed'],
                'avg_response_time_minutes': avg_response_minutes
            }
        )
        
        logger.info(
            f"📊 Métricas agregadas: {campaign.name} ({today} {current_hour}h)",
            extra={'campaign_id': str(campaign.id), 'metrics': stats}
        )
    
    return {
        'campaigns_processed': active_campaigns.count(),
        'date': today.isoformat(),
        'hour': current_hour
    }
```

---

## 🎨 FRONTEND COMPONENTS

### Modal de Criação/Edição de Mensagens

**Layout Split: Editor à esquerda + Preview WhatsApp à direita**

```tsx
// components/campaigns/MessageEditorModal.tsx

interface MessageEditorModalProps {
  isOpen: boolean;
  messageText: string;
  onSave: (text: string) => void;
  onClose: () => void;
  sampleContacts: Contact[];  // 3 contatos para preview
}

export function MessageEditorModal({ 
  isOpen, 
  messageText, 
  onSave, 
  onClose, 
  sampleContacts 
}: MessageEditorModalProps) {
  
  const [text, setText] = useState(messageText);
  const [currentContactIndex, setCurrentContactIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Inserir variável na posição do cursor
  const insertVariable = (variable: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    
    const newText = text.substring(0, start) + variable + text.substring(end);
    setText(newText);
    
    // Reposicionar cursor após variável
    setTimeout(() => {
      textarea.selectionStart = start + variable.length;
      textarea.selectionEnd = start + variable.length;
      textarea.focus();
    }, 10);
  };
  
  return (
    <Dialog open={isOpen} onClose={onClose} maxWidth="5xl" fullWidth>
      <DialogTitle className="flex items-center gap-2">
        <PencilIcon className="w-5 h-5" />
        Criar/Editar Mensagem
      </DialogTitle>
      
      <DialogContent className="p-6">
        <div className="grid grid-cols-2 gap-6 h-[650px]">
          
          {/* ════════════════════════════════════════════ */}
          {/* LADO ESQUERDO: Editor                        */}
          {/* ════════════════════════════════════════════ */}
          <div className="flex flex-col space-y-4">
            
            {/* Textarea da mensagem */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Mensagem
              </label>
              
              <textarea
                ref={textareaRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="w-full h-full p-4 border-2 border-gray-300 rounded-lg font-sans text-base focus:border-green-500 focus:ring-2 focus:ring-green-200 resize-none transition-colors"
                placeholder="Digite sua mensagem aqui... Use variáveis para personalizar!"
              />
            </div>
            
            {/* Contador de caracteres */}
            <div className="flex justify-between items-center text-sm">
              <span className={text.length > 1000 ? 'text-red-600 font-semibold' : 'text-gray-600'}>
                {text.length} / 1000 caracteres
              </span>
              
              {text.includes('{{') && (
                <span className="text-green-600 flex items-center gap-1 animate-pulse">
                  <SparklesIcon className="w-4 h-4" />
                  Variáveis detectadas
                </span>
              )}
            </div>
            
            {/* Painel de variáveis */}
            <div className="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 rounded-lg p-4 border border-blue-200 shadow-sm">
              <h4 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
                <CodeBracketIcon className="w-4 h-4 text-blue-600" />
                Variáveis Disponíveis
              </h4>
              
              <div className="grid grid-cols-2 gap-2">
                {[
                  { key: 'nome', label: 'Nome do contato', example: 'João Silva', icon: UserIcon },
                  { key: 'saudacao', label: 'Saudação automática', example: 'Bom dia', icon: SunIcon },
                  { key: 'quem_indicou', label: 'Quem indicou', example: 'Maria Santos', icon: UserGroupIcon },
                  { key: 'dia_semana', label: 'Dia da semana', example: 'Segunda-feira', icon: CalendarIcon },
                ].map(({ key, label, example, icon: Icon }) => (
                  <button
                    key={key}
                    onClick={() => insertVariable(`{{${key}}}`)}
                    className="group bg-white hover:bg-blue-50 rounded-lg p-3 text-left transition-all hover:shadow-md hover:scale-105 border border-blue-100 hover:border-blue-300"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className="w-4 h-4 text-blue-500 group-hover:text-blue-700" />
                      <div className="font-mono text-sm text-blue-600 font-semibold group-hover:text-blue-800">
                        {`{{${key}}}`}
                      </div>
                    </div>
                    <div className="text-xs text-gray-600 mb-1">{label}</div>
                    <div className="text-xs text-gray-400 italic">ex: "{example}"</div>
                  </button>
                ))}
              </div>
              
              <div className="mt-3 text-xs text-blue-600 text-center font-medium">
                💡 Clique para inserir na posição do cursor
              </div>
            </div>
          </div>
          
          {/* ════════════════════════════════════════════ */}
          {/* LADO DIREITO: Preview WhatsApp               */}
          {/* ════════════════════════════════════════════ */}
          <div className="flex flex-col">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              📱 Preview em Tempo Real
            </label>
            
            <WhatsAppSimulator
              message={text}
              contact={sampleContacts[currentContactIndex]}
            />
            
            {/* Navegação entre contatos */}
            <div className="mt-4 flex justify-center gap-2">
              {sampleContacts.map((contact, index) => (
                <button
                  key={index}
                  onClick={() => setCurrentContactIndex(index)}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    index === currentContactIndex
                      ? 'bg-green-500 text-white shadow-lg scale-110'
                      : 'bg-gray-200 text-gray-600 hover:bg-gray-300 hover:scale-105'
                  }`}
                >
                  {contact.name.split(' ')[0]}
                </button>
              ))}
            </div>
            
            {/* Info do contato atual */}
            <div className="mt-3 bg-gray-50 rounded-lg p-3 text-xs text-gray-600">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="font-semibold">Nome:</span> {sampleContacts[currentContactIndex].name}
                </div>
                <div>
                  <span className="font-semibold">Tel:</span> {sampleContacts[currentContactIndex].phone}
                </div>
                {sampleContacts[currentContactIndex].quem_indicou && (
                  <div className="col-span-2">
                    <span className="font-semibold">Indicado por:</span> {sampleContacts[currentContactIndex].quem_indicou}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
      
      <DialogFooter className="bg-gray-50 px-6 py-4">
        <Button variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button 
          onClick={() => onSave(text)} 
          disabled={text.trim().length === 0}
          className="bg-green-600 hover:bg-green-700"
        >
          💾 Salvar Mensagem
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
```

### Componente: WhatsApp Simulator (Fiel ao Original)

```tsx
// components/campaigns/WhatsAppSimulator.tsx

export function WhatsAppSimulator({ message, contact }: WhatsAppSimulatorProps) {
  const now = new Date();
  const renderedMessage = renderVariables(message, contact, now);
  const timestamp = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  const dateLabel = now.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long' });
  
  return (
    <div className="flex flex-col h-full rounded-lg overflow-hidden shadow-2xl border-2 border-gray-400">
      
      {/* HEADER WHATSAPP */}
      <div className="bg-[#075e54] text-white px-4 py-3.5 flex items-center gap-3 shadow-md">
        <button className="text-white hover:opacity-80 transition-opacity">
          <ChevronLeftIcon className="w-6 h-6" />
        </button>
        
        {/* Avatar com indicador online */}
        <div className="relative">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
            {contact.name.charAt(0).toUpperCase()}
          </div>
          <div className="absolute bottom-0 right-0 w-3 h-3 bg-[#25d366] rounded-full border-2 border-[#075e54]"></div>
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-base truncate">{contact.name}</div>
          <div className="text-xs opacity-90">online</div>
        </div>
        
        <div className="flex gap-5 text-white/90">
          <VideoCameraIcon className="w-5 h-5 cursor-pointer hover:text-white transition-colors" />
          <PhoneIcon className="w-5 h-5 cursor-pointer hover:text-white transition-colors" />
          <EllipsisVerticalIcon className="w-5 h-5 cursor-pointer hover:text-white transition-colors" />
        </div>
      </div>
      
      {/* ÁREA DE CONVERSA */}
      <div 
        className="flex-1 p-4 overflow-y-auto"
        style={{
          backgroundColor: '#e5ddd5',
          backgroundImage: `repeating-linear-gradient(
            45deg, transparent, transparent 10px,
            rgba(255,255,255,.03) 10px, rgba(255,255,255,.03) 20px
          )`
        }}
      >
        {/* Badge de data */}
        <div className="flex justify-center mb-4">
          <div className="bg-white/90 backdrop-blur-sm rounded-md px-3 py-1 text-xs text-gray-600 shadow-sm">
            {dateLabel}
          </div>
        </div>
        
        {/* BALÃO DE MENSAGEM ENVIADA */}
        <div className="flex justify-end">
          <div className="max-w-[85%]">
            <div 
              className="bg-[#dcf8c6] rounded-lg px-3 py-2.5 shadow-md relative"
              style={{ borderTopRightRadius: '2px' }}
            >
              {/* Triângulo (tail do balão) */}
              <div 
                className="absolute -right-2 top-0"
                style={{
                  width: 0, height: 0,
                  borderLeft: '10px solid #dcf8c6',
                  borderTop: '10px solid transparent'
                }}
              />
              
              {/* Texto */}
              <p className="text-[15px] leading-[1.4] text-[#303030] whitespace-pre-wrap break-words">
                {renderedMessage || (
                  <span className="text-gray-400 italic text-sm">
                    Digite a mensagem no editor ao lado...
                  </span>
                )}
              </p>
              
              {/* Hora + Check marks */}
              <div className="flex items-end justify-end gap-1 mt-1.5 select-none">
                <span className="text-[11px] text-gray-600 font-normal">
                  {timestamp}
                </span>
                {/* Check marks azuis (lido) */}
                <svg className="w-4 h-4 text-[#53bdeb]" viewBox="0 0 16 15" fill="currentColor">
                  <path d="M15.01 3.316l-.478-.372a.365.365 0 0 0-.51.063L8.666 9.879a.32.32 0 0 1-.484.033l-.358-.325a.319.319 0 0 0-.484.032l-.378.483a.418.418 0 0 0 .036.541l1.32 1.266c.143.14.361.125.484-.033l6.272-8.048a.366.366 0 0 0-.064-.512zm-4.1 0l-.478-.372a.365.365 0 0 0-.51.063L4.566 9.879a.32.32 0 0 1-.484.033L1.891 7.769a.366.366 0 0 0-.515.006l-.423.433a.364.364 0 0 0 .006.514l3.258 3.185c.143.14.361.125.484-.033l6.272-8.048a.365.365 0 0 0-.063-.51z"/>
                </svg>
              </div>
            </div>
          </div>
        </div>
        
        {/* Info sobre variáveis */}
        {message.includes('{{') && renderedMessage && (
          <div className="flex justify-center mt-4 animate-fade-in">
            <div className="bg-yellow-50 border border-yellow-200 rounded-md px-3 py-1.5 text-xs text-yellow-800 shadow-sm">
              <SparklesIcon className="w-3 h-3 inline mr-1" />
              As variáveis serão substituídas para cada contato
            </div>
          </div>
        )}
      </div>
      
      {/* INPUT BAR (apenas visual) */}
      <div className="bg-[#f0f0f0] px-3 py-2.5 flex items-center gap-2.5 border-t border-gray-300">
        <button className="text-[#54656f] hover:opacity-70">
          <FaceSmileIcon className="w-6 h-6" />
        </button>
        
        <button className="text-[#54656f] hover:opacity-70">
          <PlusCircleIcon className="w-6 h-6" />
        </button>
        
        <div className="flex-1 bg-white rounded-full px-4 py-2.5 shadow-sm">
          <span className="text-sm text-gray-400">Mensagem</span>
        </div>
        
        <button className="text-[#54656f] hover:opacity-70">
          <PaperClipIcon className="w-6 h-6" />
        </button>
        
        <button className="bg-[#00a884] hover:bg-[#008f6f] text-white rounded-full p-2.5 shadow-md transition-colors">
          <MicrophoneIcon className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

// Visual ASCII do Modal:
┌──────────────────────────────────────────────────────────────────┐
│ 📝 Criar/Editar Mensagem                                 [X]     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ┌─────────────────────────┬──────────────────────────────────┐ │
│ │ EDITOR                  │ 📱 PREVIEW WHATSAPP              │ │
│ │                         │                                  │ │
│ │ Mensagem:               │ ┌────────────────────────────┐   │ │
│ │ ┌─────────────────────┐ │ │ ◄ 🟢 João Silva      ⋮    │   │ │
│ │ │{{saudacao}}, {{nome}}│ │ ├────────────────────────────┤   │ │
│ │ │                      │ │ │   8 de outubro             │   │ │
│ │ │Vi que {{quem_indicou │ │ │                            │   │ │
│ │ │}} te indicou para    │ │ │      ┌──────────────────┐  │   │ │
│ │ │conhecer nossa        │ │ │      │ Bom dia, João!   │  │   │ │
│ │ │solução...            │ │ │      │                  │  │   │ │
│ │ │                      │ │ │      │ Vi que Maria     │  │   │ │
│ │ │Podemos conversar?    │ │ │      │ Santos te indi-  │  │   │ │
│ │ └─────────────────────┘ │ │      │ cou para conhe-  │  │   │ │
│ │                         │ │      │ cer nossa solu-  │  │   │ │
│ │ 156 / 1000 caracteres   │ │      │ ção...           │  │   │ │
│ │                         │ │      │                  │  │   │ │
│ │ 📝 Variáveis:           │ │      │ Podemos conver-  │  │   │ │
│ │ ┌──────────┬─────────┐  │ │      │ sar?             │  │   │ │
│ │ │👤 {{nome}}│Inserir  │  │ │      │                  │  │   │ │
│ │ │Nome       │         │  │ │      │   14:23      ✓✓  │  │   │ │
│ │ └──────────┴─────────┘  │ │      └──────────────────┘  │   │ │
│ │ ┌──────────┬─────────┐  │ │                            │   │ │
│ │ │☀️ {{saudacao}}│Inserir│ │ │ ┌──────────────────────┐  │   │ │
│ │ │Bom dia... │         │  │ │ │ 😊 Mensagem       🎤│  │   │ │
│ │ └──────────┴─────────┘  │ │ └──────────────────────┘  │   │ │
│ │                         │ └────────────────────────────┘   │ │
│ │ [✨ Gerar com IA]       │                                  │ │
│ │                         │ Testar preview com:              │ │
│ │                         │ [João] [Maria] [Pedro]           │ │
│ └─────────────────────────┴──────────────────────────────────┘ │
│                                                                │
│                           [Cancelar] [💾 Salvar Mensagem]      │
└──────────────────────────────────────────────────────────────────┘
```

### Tailwind Config para WhatsApp

```javascript
// tailwind.config.js

module.exports = {
  theme: {
    extend: {
      colors: {
        whatsapp: {
          green: '#075e54',        // Header
          greenDark: '#064e47',    // Header hover
          greenLight: '#dcf8c6',   // Balão enviado
          greenOnline: '#25d366',  // Indicador online
          bg: '#e5ddd5',           // Background chat
          blue: '#53bdeb',         // Check marks
          gray: '#54656f',         // Ícones input
          inputBg: '#f0f0f0',      // Background input
        }
      },
      fontFamily: {
        whatsapp: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif'
        ],
      }
    }
  }
}
```

---

## 🎨 FRONTEND COMPONENTS

### Estrutura de Pastas

```
frontend/src/
├── pages/
│   ├── campaigns/
│   │   ├── CampaignsListPage.tsx
│   │   ├── CampaignCreatePage.tsx
│   │   ├── CampaignEditPage.tsx
│   │   └── CampaignDetailsPage.tsx
│   └── ...
│
├── components/
│   ├── campaigns/
│   │   ├── CampaignCard.tsx
│   │   ├── CampaignForm.tsx
│   │   ├── MessageEditor.tsx
│   │   ├── MessagePreview.tsx
│   │   ├── ContactSelector.tsx
│   │   ├── ScheduleConfig.tsx
│   │   ├── CampaignStats.tsx
│   │   ├── CampaignLogs.tsx
│   │   └── CampaignMetrics.tsx
│   └── ui/
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Input.tsx
│       ├── Select.tsx
│       ├── ProgressBar.tsx
│       ├── Badge.tsx
│       └── ...
│
├── services/
│   ├── api/
│   │   ├── campaigns.ts
│   │   ├── messages.ts
│   │   ├── contacts.ts
│   │   └── instances.ts
│   └── websocket.ts
│
├── hooks/
│   ├── useCampaigns.ts
│   ├── useCampaignDetails.ts
│   ├── useCampaignLogs.ts
│   ├── useCampaignMetrics.ts
│   └── useRealTimeUpdates.ts
│
├── stores/
│   ├── campaignStore.ts
│   ├── contactStore.ts
│   └── instanceStore.ts
│
└── types/
    ├── campaign.ts
    ├── message.ts
    └── contact.ts
```

### Componente Principal: CampaignForm

```typescript
// components/campaigns/CampaignForm.tsx

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { MessageEditor } from './MessageEditor';
import { MessagePreview } from './MessagePreview';
import { ContactSelector } from './ContactSelector';
import { ScheduleConfig } from './ScheduleConfig';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Tabs';

const campaignSchema = z.object({
  name: z.string().min(3, 'Nome muito curto').max(200, 'Nome muito longo'),
  description: z.string().optional(),
  instance_id: z.string().uuid('Selecione uma instância'),
  schedule_type: z.enum(['immediate', 'business_days', 'business_hours', 'custom_period']),
  morning_start: z.string().optional(),
  morning_end: z.string().optional(),
  afternoon_start: z.string().optional(),
  afternoon_end: z.string().optional(),
  skip_weekends: z.boolean(),
  skip_holidays: z.boolean(),
  contact_ids: z.array(z.string().uuid()).min(1, 'Selecione pelo menos 1 contato'),
  messages: z.array(z.object({
    message_text: z.string().min(1, 'Mensagem não pode estar vazia'),
    order: z.number().min(1).max(5)
  })).min(1, 'Adicione pelo menos 1 mensagem').max(5, 'Máximo 5 mensagens')
});

type CampaignFormData = z.infer<typeof campaignSchema>;

interface CampaignFormProps {
  onSubmit: (data: CampaignFormData) => Promise<void>;
  initialData?: Partial<CampaignFormData>;
  mode: 'create' | 'edit';
}

export function CampaignForm({ onSubmit, initialData, mode }: CampaignFormProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const form = useForm<CampaignFormData>({
    resolver: zodResolver(campaignSchema),
    defaultValues: initialData || {
      messages: [{ message_text: '', order: 1 }],
      skip_weekends: true,
      skip_holidays: true,
      schedule_type: 'immediate'
    }
  });
  
  const handleSubmit = async (data: CampaignFormData) => {
    setIsSubmitting(true);
    try {
      await onSubmit(data);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const steps = [
    {
      title: 'Informações Básicas',
      component: <BasicInfoStep form={form} />
    },
    {
      title: 'Mensagens',
      component: <MessagesStep form={form} />
    },
    {
      title: 'Contatos',
      component: <ContactsStep form={form} />
    },
    {
      title: 'Agendamento',
      component: <ScheduleStep form={form} />
    },
    {
      title: 'Revisão',
      component: <ReviewStep form={form} />
    }
  ];
  
  return (
    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
      {/* Stepper */}
      <div className="flex items-center justify-between mb-8">
        {steps.map((step, index) => (
          <div
            key={index}
            className={cn(
              "flex items-center",
              index <= currentStep && "text-primary font-semibold",
              index > currentStep && "text-gray-400"
            )}
          >
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center",
                index < currentStep && "bg-green-500 text-white",
                index === currentStep && "bg-primary text-white",
                index > currentStep && "bg-gray-200 text-gray-500"
              )}
            >
              {index < currentStep ? <CheckIcon /> : index + 1}
            </div>
            <span className="ml-2">{step.title}</span>
            {index < steps.length - 1 && (
              <div className="w-20 h-0.5 mx-4 bg-gray-200" />
            )}
          </div>
        ))}
      </div>
      
      {/* Step Content */}
      <Card className="p-6">
        {steps[currentStep].component}
      </Card>
      
      {/* Navigation */}
      <div className="flex justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => setCurrentStep(prev => Math.max(0, prev - 1))}
          disabled={currentStep === 0}
        >
          Voltar
        </Button>
        
        {currentStep < steps.length - 1 ? (
          <Button
            type="button"
            onClick={() => setCurrentStep(prev => Math.min(steps.length - 1, prev + 1))}
          >
            Próximo
          </Button>
        ) : (
          <Button type="submit" loading={isSubmitting}>
            {mode === 'create' ? 'Criar Campanha' : 'Salvar Alterações'}
          </Button>
        )}
      </div>
    </form>
  );
}
```

---

## 🔐 SEGURANÇA E PERFORMANCE

### Multi-Tenant Security

```python
# Sempre filtrar por tenant em TODAS as queries

class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """SEMPRE filtrar por tenant do usuário"""
        return Campaign.objects.filter(
            tenant=self.request.tenant
        ).select_related('instance', 'created_by')
    
    def perform_create(self, serializer):
        """SEMPRE injetar tenant na criação"""
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user
        )
```

### Rate Limiting

```python
# settings.py

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'campaign_start': '10/hour',  # Custom
    }
}

# views.py

from rest_framework.throttling import UserRateThrottle

class CampaignStartThrottle(UserRateThrottle):
    rate = '10/hour'

class CampaignViewSet(viewsets.ModelViewSet):
    
    @action(detail=True, methods=['post'], throttle_classes=[CampaignStartThrottle])
    def start(self, request, pk=None):
        # ...
```

### Database Optimization

```python
# Use connection pooling
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 600,  # 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Índices importantes
class Campaign(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'status', '-created_at']),
            models.Index(fields=['status', 'is_paused', 'next_scheduled_send']),
            models.Index(fields=['instance', 'status']),
        ]
```

---

**Última Atualização:** 2025-10-08  
**Versão:** 2.0.0  
**Autor:** ALREA Development Team

