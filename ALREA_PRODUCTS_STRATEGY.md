# 💼 ALREA - Estratégia de Produtos e Pricing

> **Documento:** Arquitetura Multi-Produto e Sistema de Billing  
> **Versão:** 1.0.0  
> **Data:** 2025-10-08  
> **Confidencial:** Estratégia de negócio ALREA

---

## 🎯 VISÃO GERAL

A plataforma ALREA opera como **SaaS multi-produto** com arquitetura modular que permite:

- ✅ Venda de produtos individuais ou em bundle
- ✅ Add-ons que complementam planos base
- ✅ API como produto standalone ou complementar
- ✅ Pricing totalmente customizável
- ✅ Upsell e cross-sell facilitados

---

## 📦 PRODUTOS DA PLATAFORMA

### 1. ALREA Flow 📤 (Campanhas WhatsApp)

**Descrição:**  
Sistema completo de campanhas de disparo em massa via WhatsApp

**Funcionalidades:**
- Múltiplas campanhas simultâneas (1 por instância)
- Até 5 mensagens com rotação automática
- Agendamento inteligente (horários, dias úteis, feriados)
- Pausar/Retomar/Encerrar em tempo real
- Preview WhatsApp em tempo real
- Logs completos e auditoria
- Dashboard de acompanhamento

**Acesso:**
- UI Web (frontend React)
- API Interna (JWT)

**Incluído em:**
- ✅ Starter (limitado)
- ✅ Pro (avançado)
- ❌ API Only
- ✅ Enterprise (ilimitado)

---

### 2. ALREA Sense 🧠 (Análise de Sentimento)

**Descrição:**  
Monitoramento e análise de conversas WhatsApp com IA

**Funcionalidades:**
- Análise de sentimento (positivo/negativo/neutro)
- Detecção de emoções
- Score de satisfação
- Busca semântica com embeddings (pgvector)
- Alertas de insatisfação
- Relatórios de performance

**Acesso:**
- UI Web
- API Interna (JWT)

**Incluído em:**
- ❌ Starter
- ✅ Pro (5k análises/mês)
- ❌ API Only
- ✅ Enterprise (ilimitado)

---

### 3. ALREA API Pública 🔌 (Integração Externa)

**Descrição:**  
Endpoints REST documentados para integração com sistemas externos

**Funcionalidades:**
- Autenticação via API Key (sem login)
- Endpoints públicos documentados (Swagger)
- Webhooks de retorno
- Rate limiting configurável
- Suporte técnico para integração
- Exemplos de código (Python, PHP, Node.js)

**Endpoints Exemplo:**
```
POST /api/v1/public/send-campaign
POST /api/v1/public/send-message
GET  /api/v1/public/campaign-status
POST /api/v1/public/analyze-sentiment (se tem Sense)
```

**Acesso:**
- Apenas API (sem UI)
- Autenticação: API Key

**Disponibilidade:**
- ❌ Starter (add-on: +R$ 79/mês)
- ❌ Pro (add-on: +R$ 79/mês)
- ✅ API Only (incluído: R$ 99/mês)
- ✅ Enterprise (incluído)

**Casos de Uso:**
- Cliente tem CRM próprio e quer integrar disparos
- Revenda/White-label
- Automações com Zapier/Make
- Sistema legado que precisa enviar WhatsApp

---

## 💰 PLANOS E PRICING

### Tabela Comparativa

```
┌──────────────────┬─────────┬──────┬──────────┬────────────┐
│ Feature          │ Starter │ Pro  │ API Only │ Enterprise │
├──────────────────┼─────────┼──────┼──────────┼────────────┤
│ 💵 PREÇO BASE    │ R$ 49   │ R$149│ R$ 99    │ R$ 499     │
├──────────────────┼─────────┼──────┼──────────┼────────────┤
│ ALREA Flow       │         │      │          │            │
│ • Campanhas/mês  │ 5       │ 20   │ -        │ ∞          │
│ • Contatos/camp. │ 500     │ 5.000│ -        │ ∞          │
│ • Instâncias     │ 2       │ 10   │ -        │ ∞          │
├──────────────────┼─────────┼──────┼──────────┼────────────┤
│ ALREA Sense      │         │      │          │            │
│ • Análises/mês   │ -       │ 5.000│ -        │ ∞          │
│ • Retenção       │ -       │ 180d │ -        │ 730d       │
├──────────────────┼─────────┼──────┼──────────┼────────────┤
│ API Pública      │         │      │          │            │
│ • Incluída?      │ ❌      │ ❌   │ ✅       │ ✅         │
│ • Add-on         │ +R$ 79  │+R$ 79│ -        │ -          │
│ • Requests/dia   │ 10k*    │ 10k* │ 50k      │ ∞          │
│ • Webhooks       │ ❌*     │ ❌*  │ ✅       │ ✅         │
├──────────────────┼─────────┼──────┼──────────┼────────────┤
│ UI Web           │ ✅      │ ✅   │ ❌       │ ✅         │
├──────────────────┼─────────┼──────┼──────────┼────────────┤
│ Suporte          │ Email   │ Chat │ Técnico  │ Dedicado   │
├──────────────────┼─────────┼──────┼──────────┼────────────┤
│ 💵 TOTAL c/ API  │ R$ 128  │ R$228│ R$ 99    │ R$ 499     │
└──────────────────┴─────────┴──────┴──────────┴────────────┘

* Se contratar add-on API Pública
⚠️ VALORES CUSTOMIZÁVEIS - Exemplos apenas
```

### Detalhamento por Plano

#### 🟦 Starter (R$ 49/mês)

```yaml
Público-Alvo: Pequenas empresas, MEI, autônomos
Objetivo: Entrada de baixo custo

Incluído:
  ✅ ALREA Flow
     - 5 campanhas/mês
     - 500 contatos/campanha
     - 1.000 mensagens/campanha
     - 2 instâncias WhatsApp
     - Rotação de até 5 mensagens
     - Agendamento (todos os tipos)
  
  ✅ API Interna (básica)
     - Acesso via UI
     - JWT authentication

Não Incluído:
  ❌ ALREA Sense
  ❌ API Pública (add-on: +R$ 79/mês)

Add-ons Disponíveis:
  🔌 API Pública: +R$ 79/mês
     → Total: R$ 128/mês

Upgrade Path:
  → Pro (R$ 149) - Adiciona Sense + mais limites
```

#### 🟪 Pro (R$ 149/mês)

```yaml
Público-Alvo: Empresas em crescimento, agências
Objetivo: Solução completa Flow + Sense

Incluído:
  ✅ ALREA Flow (Avançado)
     - 20 campanhas/mês
     - 5.000 contatos/campanha
     - 10 instâncias
     - Todas as features
  
  ✅ ALREA Sense
     - 5.000 análises/mês
     - Retenção 180 dias
     - Busca semântica
     - Alertas automáticos
  
  ✅ API Interna (completa)

Não Incluído:
  ❌ API Pública (add-on: +R$ 79/mês)

Add-ons Disponíveis:
  🔌 API Pública: +R$ 79/mês
     → Total: R$ 228/mês

Upgrade Path:
  → Enterprise (R$ 499) - Remove limites + API incluída
```

#### 🔌 API Only (R$ 99/mês)

```yaml
Público-Alvo: Desenvolvedores, integradores, revenda
Objetivo: API standalone sem necessidade de UI

Incluído:
  ✅ API Pública (Completa)
     - 50.000 requests/dia
     - 5.000 mensagens/dia
     - Rate limit: 100 req/min
     - Webhooks habilitados
     - Documentação Swagger
     - Exemplos de código
  
  ✅ Uso dos serviços via API:
     - Disparar campanhas programaticamente
     - Enviar mensagens avulsas
     - (Se habilitado: Análises de sentimento)

Não Incluído:
  ❌ Acesso à UI Web (ui_access=False)
  ❌ ALREA Flow standalone
  ❌ ALREA Sense standalone

Uso Típico:
  - Sistema do cliente dispara via API
  - Integração com CRM/ERP
  - Automações (Zapier, Make)
  - Revenda white-label

Upgrade Path:
  → Enterprise (UI + limites ilimitados)
```

#### 🟨 Enterprise (R$ 499/mês)

```yaml
Público-Alvo: Grandes empresas, corporações
Objetivo: Tudo incluído sem limites

Incluído:
  ✅ ALREA Flow (Ilimitado)
  ✅ ALREA Sense (Ilimitado)
  ✅ API Pública (Ilimitado)
  ✅ UI Web completa
  ✅ Suporte dedicado
  ✅ SLA garantido
  ✅ Features customizadas sob demanda
  ✅ White-label (opcional)
  ✅ Treinamento da equipe

Limites:
  ∞ Sem limites técnicos

Add-ons:
  Nenhum (já tem tudo)
```

---

## 🔧 IMPLEMENTAÇÃO TÉCNICA

### Estrutura de Dados

```
┌─────────────┐
│   Product   │ ←───┐
│ (3 produtos)│     │
└─────────────┘     │ N:N
                    │
       ┌────────────┴────────────┐
       │     PlanProduct         │
       │  (plan + product)       │
       │  + is_included          │
       │  + limits               │
       └─────────────────────────┘
                    │
                    │ N
       ┌────────────┴────────────┐
       │        Plan             │
       │    (4 planos)           │
       └─────────────────────────┘
                    │ 1
                    │
                    │ N
       ┌────────────┴────────────┐
       │       Tenant            │
       │   (current_plan)        │
       └─────────────────────────┘
                    │ 1
                    │
                    │ N
       ┌────────────┴────────────┐
       │    TenantProduct        │
       │  (produtos ativos)      │
       │  + is_addon             │
       │  + api_key              │
       └─────────────────────────┘
```

### Fluxo: Adicionar Add-on

```
1. Cliente no plano "Pro" quer API Pública

   ↓ Frontend: Página de Billing

┌─────────────────────────────────────────┐
│ Seu Plano: Pro (R$ 149/mês)            │
│                                         │
│ 🔌 Add-ons Disponíveis                 │
│                                         │
│ ┌─────────────────────────────────┐   │
│ │ ALREA API Pública               │   │
│ │ Integração programática         │   │
│ │ 💰 +R$ 79/mês                   │   │
│ │ [Adicionar ao Plano →]          │   │
│ └─────────────────────────────────┘   │
└─────────────────────────────────────────┘

2. Cliente clica "Adicionar ao Plano"
   
   ↓ Confirmação
   
┌─────────────────────────────────────────┐
│ Confirmar Add-on                        │
│                                         │
│ ALREA API Pública                       │
│ +R$ 79,00/mês                           │
│                                         │
│ Novo total: R$ 228,00/mês               │
│ (R$ 149 plano + R$ 79 add-on)           │
│                                         │
│ Próxima cobrança: 15/11/2025            │
│                                         │
│ [Cancelar] [Confirmar e Pagar]         │
└─────────────────────────────────────────┘

3. Backend: POST /api/billing/add-addon/
   
   with transaction.atomic():
       # Criar TenantProduct
       TenantProduct.objects.create(
           tenant=tenant,
           product=Product.objects.get(slug='api_public'),
           is_addon=True,
           addon_price=79.00
       )
       
       # Gerar API Key
       api_key = generate_api_key()
       
       # Atualizar Stripe (adicionar line item)
       stripe.SubscriptionItem.create(
           subscription=tenant.stripe_subscription_id,
           price=ADDON_PRICE_ID,
           quantity=1
       )

4. Tenant agora tem:
   - current_plan = "Pro"
   - tenant_products = ["api_public" (addon)]
   - active_products = ["flow", "sense", "api_public"]
   - monthly_total = R$ 228

5. Sistema gera API Key e mostra:

┌─────────────────────────────────────────┐
│ ✅ API Pública Ativada!                 │
│                                         │
│ Sua API Key:                            │
│ alr_xxxxxxxxxxxxxxxxxxxxxxxx            │
│ [Copiar] [Ver Documentação]            │
│                                         │
│ Endpoints disponíveis:                  │
│ https://api.alrea.com.br/v1/public/     │
└─────────────────────────────────────────┘
```

---

## 🎨 INTERFACE DO CLIENTE

### Dashboard Mostrando Produtos Ativos

```tsx
// Página principal após login

┌─────────────────────────────────────────────────────┐
│ Bem-vindo, Paulo! 👋                                │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Seu Plano: Pro (R$ 149/mês)                        │
│ + Add-on: API Pública (+R$ 79/mês)                 │
│ Total: R$ 228/mês                                   │
│                                                     │
│ ─────────────────────────────────────────────       │
│                                                     │
│ 📦 Seus Produtos                                    │
│                                                     │
│ ┌───────────────────────────────────────────────┐ │
│ │ 📤 ALREA Flow                                 │ │
│ │ Campanhas de Disparo WhatsApp                 │ │
│ │                                               │ │
│ │ 📊 8 / 20 campanhas ativas este mês           │ │
│ │ 📤 2.340 / 50.000 mensagens enviadas          │ │
│ │                                               │ │
│ │ [Acessar Campanhas →]                         │ │
│ └───────────────────────────────────────────────┘ │
│                                                     │
│ ┌───────────────────────────────────────────────┐ │
│ │ 🧠 ALREA Sense                                │ │
│ │ Análise de Sentimento                         │ │
│ │                                               │ │
│ │ 📊 1.240 / 5.000 análises este mês            │ │
│ │ ✅ 87% satisfação média                       │ │
│ │                                               │ │
│ │ [Acessar Análises →]                          │ │
│ └───────────────────────────────────────────────┘ │
│                                                     │
│ ┌───────────────────────────────────────────────┐ │
│ │ 🔌 API Pública (Add-on)                       │ │
│ │ Integração Externa                            │ │
│ │                                               │ │
│ │ 🔑 API Key: alr_xxxxxxxxxxxx [Copiar]        │ │
│ │ 📈 340 / 10.000 requests hoje                 │ │
│ │                                               │ │
│ │ [Ver Documentação →] [Exemplos de Código →]   │ │
│ └───────────────────────────────────────────────┘ │
│                                                     │
│ ─────────────────────────────────────────────       │
│                                                     │
│ 💡 Produtos Adicionais Disponíveis                 │
│                                                     │
│ 🔒 ALREA Reports (Em desenvolvimento)              │
│    Relatórios avançados e dashboards customizados   │
│    [Aguarde lançamento]                            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Página de Billing/Upgrade

```tsx
┌─────────────────────────────────────────────────────┐
│ Planos e Billing                                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Plano Atual: Pro (R$ 149/mês)                      │
│ Próxima cobrança: 15/11/2025                        │
│                                                     │
│ ┌─ Add-ons Ativos ────────────────────────────┐   │
│ │ ✅ API Pública         +R$ 79/mês           │   │
│ │    Ativado em: 08/10/2025                   │   │
│ │    [Gerenciar] [Cancelar]                   │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│ Total Mensal: R$ 228,00                             │
│                                                     │
│ ─────────────────────────────────────────────       │
│                                                     │
│ 🚀 Fazer Upgrade                                    │
│                                                     │
│ ┌─────────────────────────────────────────────┐   │
│ │ 🟨 Enterprise (R$ 499/mês)                  │   │
│ │                                             │   │
│ │ Tudo ilimitado + Suporte dedicado           │   │
│ │ ✅ API Pública incluída (economia R$ 79)    │   │
│ │                                             │   │
│ │ [Fazer Upgrade →]                           │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│ ─────────────────────────────────────────────       │
│                                                     │
│ 📋 Histórico de Faturas                             │
│ [Ver Todas →]                                       │
└─────────────────────────────────────────────────────┘
```

---

## 🔐 CONTROLE DE ACESSO NO CÓDIGO

### Decorator para ViewSets

```python
# apps/common/decorators.py

from functools import wraps
from django.core.exceptions import PermissionDenied

def require_product(product_slug):
    """
    Decorator que valida acesso ao produto
    
    Uso:
    @require_product('flow')
    class CampaignViewSet(viewsets.ModelViewSet):
        ...
    """
    def decorator(cls):
        original_dispatch = cls.dispatch
        
        @wraps(original_dispatch)
        def new_dispatch(self, request, *args, **kwargs):
            if not request.tenant.has_product(product_slug):
                raise PermissionDenied(
                    f'Produto {product_slug} não disponível no seu plano'
                )
            return original_dispatch(self, request, *args, **kwargs)
        
        cls.dispatch = new_dispatch
        return cls
    
    return decorator

# Uso
@require_product('flow')
class CampaignViewSet(viewsets.ModelViewSet):
    # Só acessa se tenant.has_product('flow')
    pass

@require_product('sense')
class SentimentAnalysisViewSet(viewsets.ModelViewSet):
    # Só acessa se tenant.has_product('sense')
    pass

@require_product('api_public')
class PublicAPIViewSet(viewsets.ViewSet):
    # Só acessa se tenant.has_product('api_public')
    pass
```

### Menu Dinâmico (Frontend)

```typescript
// Sidebar.tsx

function Sidebar() {
  const { tenant } = useAuth();
  
  // Buscar produtos ativos do tenant
  const activeProducts = tenant.active_products; // ['flow', 'sense', 'api_public']
  
  const menuItems = [
    {
      label: 'Dashboard',
      icon: HomeIcon,
      path: '/dashboard',
      visible: true  // Sempre visível
    },
    {
      label: 'Campanhas',
      icon: MegaphoneIcon,
      path: '/campaigns',
      requiredProduct: 'flow',
      visible: activeProducts.includes('flow')
    },
    {
      label: 'Análises',
      icon: ChartBarIcon,
      path: '/analyses',
      requiredProduct: 'sense',
      visible: activeProducts.includes('sense')
    },
    {
      label: 'API',
      icon: CodeBracketIcon,
      path: '/api-docs',
      requiredProduct: 'api_public',
      visible: activeProducts.includes('api_public')
    },
    {
      label: 'Billing',
      icon: CreditCardIcon,
      path: '/billing',
      visible: true
    }
  ];
  
  return (
    <nav>
      {menuItems
        .filter(item => item.visible)
        .map(item => <MenuItem key={item.path} {...item} />)
      }
    </nav>
  );
}
```

---

## 💡 ESTRATÉGIAS DE MONETIZAÇÃO

### 1. Upsell de Add-ons

```
Cliente Starter (R$ 49) precisa API para integrar com CRM

Opção A: Adicionar Add-on
  R$ 49 + R$ 79 = R$ 128/mês
  
Opção B: Upgrade para Enterprise
  R$ 499/mês (inclui API + remove limites)

Sistema sugere:
  "API disponível por +R$ 79/mês ou upgrade para Enterprise"
```

### 2. Plano API Only (Revenda/Parceiros)

```
Parceiro/Integrador não precisa de UI

Contrata: API Only (R$ 99/mês)
  → 50k requests/dia
  → 5k mensagens/dia
  → Webhooks

Usa para:
  - Revender disparos WhatsApp
  - Integrar com plataforma própria
  - White-label
```

### 3. Path de Crescimento

```
Cliente começa:
  Starter (R$ 49)
  → Adiciona API (+R$ 79) = R$ 128
  → Upgrade Pro (R$ 149) = Sense incluído
  → Adiciona API novamente (+R$ 79) = R$ 228
  → Cresce e vai para Enterprise (R$ 499)
```

---

## ⚙️ CUSTOMIZAÇÃO DE VALORES

### Onde Customizar

```python
# 1. Via Admin Django
Admin → Billing → Products → Editar "ALREA API Pública"
  → addon_price = 79.00  # Mude aqui

Admin → Billing → Plans → Editar "Starter"
  → price = 49.90  # Mude aqui

# 2. Via Settings
# settings.py
PRODUCT_PRICING = {
    'api_public_addon': 79.00,  # Customizável
    'starter_plan': 49.90,
    'pro_plan': 149.90,
    'api_only_plan': 99.00,
    'enterprise_plan': 499.00,
}

# 3. Via Seed (initial data)
# seed_products.py
PLANS = [
    {
        'slug': 'starter',
        'price': env('STARTER_PRICE', default=49.90),  # De .env
        # ...
    }
]
```

### Exemplos de Ajuste

```python
# Promoção: API add-on de R$ 79 → R$ 49
Product.objects.filter(slug='api_public').update(addon_price=49.00)

# Reajuste: Plano Pro de R$ 149 → R$ 179
Plan.objects.filter(slug='pro').update(price=179.00)

# Criar plano personalizado
Plan.objects.create(
    slug='custom_agency',
    name='Agência Plus',
    price=299.00,
    description='Plano especial para agências'
)
```

---

## 📊 MÉTRICAS E ANALYTICS

### KPIs por Produto

```python
# Dashboard Admin: Métricas de produto

Product: ALREA Flow
  - Tenants ativos: 247
  - Campanhas criadas (mês): 1.240
  - Mensagens enviadas (mês): 450.000
  - MRR: R$ 247 × R$ 49 = R$ 12.103

Product: ALREA Sense
  - Tenants ativos: 89 (apenas Pro/Enterprise)
  - Análises (mês): 234.000
  - MRR: Incluído em planos

Product: ALREA API Pública
  - Tenants com API: 34
    ├─ API Only: 12 (R$ 99) = R$ 1.188
    ├─ Add-ons: 15 (R$ 79) = R$ 1.185
    └─ Enterprise: 7 (incluído)
  - MRR: R$ 2.373
```

---

## ✅ RESUMO EXECUTIVO

### Estrutura de Produtos

```
3 Produtos Principais:
├── ALREA Flow (Campanhas)
├── ALREA Sense (IA/Análises)
└── ALREA API Pública (Integração) ⭐ Pode ser add-on

4 Planos:
├── Starter (R$ 49) - Flow básico
├── Pro (R$ 149) - Flow + Sense
├── API Only (R$ 99) - Só API (sem UI)
└── Enterprise (R$ 499) - Tudo ilimitado
```

### API Pública

```
Disponível em:
✅ API Only (incluído)
✅ Enterprise (incluído)
✅ Starter/Pro (+R$ 79/mês add-on)

Valor add-on: R$ 79/mês (customizável)
```

### Vantagens da Arquitetura

```
✅ Modular (fácil adicionar produtos)
✅ Flexível (add-ons customizáveis)
✅ Escalável (novos produtos = novos registros)
✅ Upsell facilitado (API como add-on)
✅ Valores customizáveis (via Admin)
✅ Multi-tenant nativo
```

---

**Última Atualização:** 2025-10-08  
**Versão:** 1.0.0  
**Confidencial:** Documento interno ALREA

