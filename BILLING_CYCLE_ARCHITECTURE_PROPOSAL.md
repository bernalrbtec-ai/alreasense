# 🔄 **PROPOSTA ARQUITETURAL - CICLO DE MENSAGENS DE BILLING**

> **Análise e Proposta de Arquitetura para Sistema de Ciclo de Mensagens**  
> **Data:** Janeiro 2025  
> **Status:** 📋 **PROPOSTA - SEM IMPLEMENTAÇÃO**

---

## 🎯 **REQUISITOS FUNCIONAIS**

### **1. Templates de Vencidos (Overdue)**
Ciclo de **3 mensagens automáticas**:
- ✅ **1 dia após vencimento** → Primeira mensagem
- ✅ **3 dias após vencimento** → Segunda mensagem  
- ✅ **5 dias após vencimento** → Terceira mensagem

### **2. Templates de A Vencer (Upcoming)**
Ciclo de **3 mensagens automáticas**:
- ✅ **5 dias antes do vencimento** → Primeira mensagem
- ✅ **3 dias antes do vencimento** → Segunda mensagem
- ✅ **1 dia antes do vencimento** → Terceira mensagem

### **3. Fluxo Simplificado**
- Receber **todos os vencimentos** de uma vez (batch)
- Marcar **opções de avisar antes e depois** de vencer
- Sistema gerencia automaticamente o ciclo completo

### **4. Cancelamento do Ciclo**
- Receber JSON informando **baixa da cobrança**
- Cancelar **todas as mensagens pendentes** do ciclo
- Marcar como **cancelado** no histórico

---

## 🏗️ **ANÁLISE DA ARQUITETURA ATUAL**

### **Modelos Existentes:**
1. **BillingCampaign** - Uma campanha por requisição
2. **BillingContact** - Um contato por cobrança
3. **BillingQueue** - Fila de processamento
4. **BillingTemplate** - Templates de mensagem

### **Limitações Atuais:**
- ❌ Sistema atual cria **1 campanha = 1 mensagem**
- ❌ Não há rastreamento de **ciclo de mensagens**
- ❌ Não há controle de **status da cobrança** (paga/cancelada)
- ❌ Não há **agendamento automático** de mensagens futuras
- ❌ Não há **relacionamento** entre mensagens do mesmo ciclo

---

## 💡 **PROPOSTA DE ARQUITETURA**

### **OPÇÃO 1: Modelo de Ciclo Explícito (Recomendado)**

#### **Novo Modelo: `BillingCycle`**
```
BillingCycle
├── id (UUID)
├── tenant (FK)
├── external_billing_id (String) - ID da cobrança no sistema externo
├── contact_phone (String)
├── contact_name (String)
├── billing_data (JSON) - Dados da cobrança (valor, vencimento, etc)
├── due_date (Date) - Data de vencimento
├── status (Enum) - active, cancelled, completed
├── notify_before_due (Boolean) - Enviar avisos antes?
├── notify_after_due (Boolean) - Enviar avisos depois?
├── created_at
├── updated_at
└── cancelled_at (DateTime, nullable)
```

#### **Novo Modelo: `BillingCycleMessage`**
```
BillingCycleMessage
├── id (UUID)
├── billing_cycle (FK) - Ciclo pai
├── message_type (Enum) - upcoming_5d, upcoming_3d, upcoming_1d, overdue_1d, overdue_3d, overdue_5d
├── scheduled_date (Date) - Quando deve ser enviada
├── status (Enum) - pending, sent, cancelled, failed
├── billing_contact (FK, nullable) - Link com BillingContact quando enviada
├── sent_at (DateTime, nullable)
├── created_at
└── updated_at
```

#### **Fluxo:**
1. **Cliente envia batch de cobranças** → Cria `BillingCycle` para cada uma
2. **Sistema cria `BillingCycleMessage`** para cada mensagem do ciclo (6 no total se ambos ativos)
3. **Scheduler verifica diariamente** quais mensagens devem ser enviadas hoje
4. **Quando chega a data** → Cria `BillingCampaign` + `BillingContact` e envia
5. **Cliente envia baixa** → Marca `BillingCycle.status = 'cancelled'` e cancela todas as `BillingCycleMessage` pendentes

#### **Vantagens:**
- ✅ Visão completa do ciclo em um lugar
- ✅ Fácil cancelar todas as mensagens de uma vez
- ✅ Rastreamento claro de qual mensagem foi enviada
- ✅ Histórico completo do ciclo

#### **Desvantagens:**
- ⚠️ Mais complexo (novo modelo)
- ⚠️ Precisa de scheduler para verificar mensagens pendentes

---

### **OPÇÃO 2: Modelo Simplificado com Status na Cobrança**

#### **Modificar `BillingContact`:**
```
BillingContact (modificado)
├── ... campos existentes ...
├── billing_cycle_id (String) - ID externo da cobrança
├── cycle_message_number (Integer) - Qual mensagem do ciclo (1, 2, 3)
├── cycle_type (Enum) - upcoming_5d, upcoming_3d, upcoming_1d, overdue_1d, overdue_3d, overdue_5d
├── scheduled_date (Date) - Quando deve ser enviada
└── billing_status (Enum) - active, cancelled, paid
```

#### **Novo Modelo: `BillingCycleStatus` (Opcional)**
```
BillingCycleStatus
├── external_billing_id (String, PK) - ID da cobrança no sistema externo
├── tenant (FK)
├── status (Enum) - active, cancelled, paid
├── due_date (Date)
├── cancelled_at (DateTime, nullable)
└── updated_at
```

#### **Fluxo:**
1. **Cliente envia batch** → Cria múltiplos `BillingContact` com `scheduled_date` futuro
2. **Scheduler verifica diariamente** → Envia mensagens com `scheduled_date = hoje`
3. **Cliente envia baixa** → Atualiza `BillingCycleStatus` ou `BillingContact.billing_status = 'cancelled'`
4. **Scheduler ignora** mensagens com `billing_status = 'cancelled'`

#### **Vantagens:**
- ✅ Mais simples (reutiliza modelos existentes)
- ✅ Menos queries (tudo em BillingContact)

#### **Desvantagens:**
- ⚠️ Múltiplos `BillingContact` para mesma cobrança (pode confundir)
- ⚠️ Difícil ver "ciclo completo" de uma cobrança

---

### **OPÇÃO 3: Híbrida (Recomendada para MVP)**

#### **Modelo: `BillingCycle` (Simplificado)**
```
BillingCycle
├── id (UUID)
├── tenant (FK)
├── external_billing_id (String, unique) - ID da cobrança no sistema externo
├── contact_phone (String)
├── contact_name (String)
├── billing_data (JSON)
├── due_date (Date)
├── status (Enum) - active, cancelled, paid, completed
├── notify_before_due (Boolean)
├── notify_after_due (Boolean)
├── created_at
├── updated_at
└── cancelled_at (DateTime, nullable)
```

#### **Modificar `BillingContact`:**
```
BillingContact (modificado)
├── ... campos existentes ...
├── billing_cycle (FK, nullable) - Link com ciclo
├── cycle_message_type (String) - upcoming_5d, upcoming_3d, etc
└── scheduled_date (Date) - Quando deve ser enviada
```

#### **Fluxo:**
1. **Cliente envia batch** → Cria `BillingCycle` para cada cobrança
2. **Sistema cria `BillingContact`** com `scheduled_date` futuro para cada mensagem do ciclo
3. **Scheduler diário** → Busca `BillingContact` com `scheduled_date = hoje` e `billing_cycle.status = 'active'`
4. **Envia mensagem** → Atualiza `BillingContact.status = 'sent'`
5. **Cliente envia baixa** → `BillingCycle.status = 'cancelled'` → Scheduler ignora mensagens pendentes

#### **Vantagens:**
- ✅ Balanceia simplicidade e funcionalidade
- ✅ Reutiliza `BillingContact` existente
- ✅ Fácil cancelar ciclo inteiro
- ✅ Histórico completo

---

## 📊 **COMPARAÇÃO DAS OPÇÕES**

| Aspecto | Opção 1 (Ciclo Explícito) | Opção 2 (Simplificado) | Opção 3 (Híbrida) ⭐ |
|---------|---------------------------|------------------------|---------------------|
| **Complexidade** | Alta | Baixa | Média |
| **Rastreamento** | Excelente | Bom | Excelente |
| **Cancelamento** | Muito Fácil | Fácil | Muito Fácil |
| **Queries** | Médias | Simples | Médias |
| **Manutenção** | Média | Fácil | Fácil |
| **Escalabilidade** | Excelente | Boa | Excelente |

**Recomendação:** ⭐ **OPÇÃO 3 (Híbrida)**

---

## 🔄 **FLUXO DETALHADO (OPÇÃO 3)**

### **1. Recebimento de Batch de Cobranças**

**Endpoint:** `POST /api/billing/v1/billing/send/batch`

**Payload:**
```json
{
  "contacts": [
    {
      "external_billing_id": "BILL-001",
      "nome": "João Silva",
      "telefone": "+5511999999999",
      "valor": "100.00",
      "data_vencimento": "2025-01-15",
      "notify_before_due": true,  // Enviar avisos antes?
      "notify_after_due": true,   // Enviar avisos depois?
      "link_pagamento": "https://...",
      "codigo_pix": "..."
    },
    // ... mais cobranças
  ]
}
```

**Processamento:**
1. Para cada cobrança:
   - Cria `BillingCycle` com `status = 'active'`
   - Se `notify_before_due = true`:
     - Cria 3 `BillingContact` com `scheduled_date` = 5 dias antes, 3 dias antes, 1 dia antes
   - Se `notify_after_due = true`:
     - Cria 3 `BillingContact` com `scheduled_date` = 1 dia depois, 3 dias depois, 5 dias depois
   - Todos os `BillingContact` ficam com `status = 'pending'` e `scheduled_date` futuro

### **2. Scheduler Diário (Cron Job)**

**Executa:** Todo dia às 00:00 (ou horário configurável)

**Processo:**
```python
# Busca mensagens agendadas para hoje
today = timezone.now().date()
pending_messages = BillingContact.objects.filter(
    scheduled_date=today,
    status='pending',
    billing_cycle__status='active'  # Só ciclos ativos
)

# Para cada mensagem:
# 1. Cria BillingCampaign
# 2. Envia mensagem
# 3. Atualiza BillingContact.status = 'sent'
```

### **3. Cancelamento de Ciclo**

**Endpoint:** `POST /api/billing/v1/billing/cancel`

**Payload:**
```json
{
  "external_billing_id": "BILL-001",
  "reason": "paid" | "cancelled" | "refunded"
}
```

**Processamento:**
1. Busca `BillingCycle` por `external_billing_id` e `tenant_id`
2. Valida que ciclo existe e está ativo
3. Atualiza `BillingCycle.status = reason` ('cancelled' ou 'paid')
4. Atualiza `BillingCycle.cancelled_at = now()`
5. Cancela apenas `BillingContact` com `status = 'pending'` (não mexe nas enviadas)
6. Atualiza contadores (`sent_messages`, `failed_messages`)
7. Scheduler não processa mais mensagens deste ciclo

---

## 🗄️ **ESTRUTURA DE DADOS PROPOSTA**

### **Tabela: `billing_api_cycle`**
```sql
CREATE TABLE billing_api_cycle (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    external_billing_id VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(20) NOT NULL,
    contact_name VARCHAR(255),
    contact_id UUID, -- FK para Contact (cadastrado automaticamente)
    billing_data JSONB,
    due_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL, -- active, cancelled, paid, completed
    notify_before_due BOOLEAN DEFAULT false,
    notify_after_due BOOLEAN DEFAULT true,
    total_messages INTEGER DEFAULT 0, -- Total de mensagens do ciclo (6 se ambos ativos)
    sent_messages INTEGER DEFAULT 0,  -- Mensagens enviadas com sucesso
    failed_messages INTEGER DEFAULT 0, -- Mensagens falhadas
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    completed_at TIMESTAMP, -- Quando ciclo foi completado
    
    UNIQUE(tenant_id, external_billing_id),
    INDEX idx_cycle_tenant_status (tenant_id, status),
    INDEX idx_cycle_external_id (external_billing_id),
    INDEX idx_cycle_due_date (due_date),
    INDEX idx_cycle_status_created (status, created_at),
    FOREIGN KEY (contact_id) REFERENCES contacts_contact(id)
);
```

### **Modificação: `billing_api_contact`**
```sql
ALTER TABLE billing_api_contact
ADD COLUMN billing_cycle_id UUID REFERENCES billing_api_cycle(id),
ADD COLUMN cycle_message_type VARCHAR(20), -- upcoming_5d, upcoming_3d, overdue_1d, etc
ADD COLUMN cycle_index INTEGER, -- 1, 2, 3, 4, 5, 6 (posição no ciclo)
ADD COLUMN scheduled_date DATE, -- Data agendada (já recalculada para dia útil)
ADD COLUMN billing_status VARCHAR(20) DEFAULT 'active', -- active, cancelled, paid
ADD COLUMN template_variation_index INTEGER, -- Índice da variação usada (para rotação)
ADD COLUMN retry_count INTEGER DEFAULT 0, -- Contador de tentativas
ADD COLUMN last_retry_at TIMESTAMP; -- Última tentativa de retry

CREATE INDEX idx_contact_cycle (billing_cycle_id);
CREATE INDEX idx_contact_scheduled (scheduled_date, status) WHERE status = 'pending';
CREATE INDEX idx_contact_cycle_type (billing_cycle_id, cycle_message_type);
CREATE INDEX idx_contact_scheduled_status_cycle (scheduled_date, status, billing_cycle_id) WHERE status = 'pending';
```

---

## 🔧 **COMPONENTES NECESSÁRIOS**

### **1. Novo Endpoint: Batch de Cobranças**
- `POST /api/billing/v1/billing/send/batch`
- Recebe múltiplas cobranças de uma vez
- Cria `BillingCycle` + `BillingContact` agendados

### **2. Novo Endpoint: Cancelamento**
- `POST /api/billing/v1/billing/cancel`
- Cancela ciclo completo

### **3. Novo Scheduler: Verificação Diária**
- Executa diariamente (cron job ou Celery Beat)
- Busca mensagens com `scheduled_date = hoje`
- Cria campanhas e envia mensagens

### **4. Modificação: BillingCampaignService**
- Suportar criação de `BillingContact` com `scheduled_date` futuro
- Não publicar no RabbitMQ imediatamente (aguardar scheduler)

### **5. Novo Service: BillingCycleService**
- Gerenciar criação de ciclos
- Gerenciar cancelamento de ciclos
- Calcular `scheduled_date` baseado em `due_date`

---

## 📅 **CÁLCULO DE DATAS**

### **Para "A Vencer" (Upcoming):**
```python
due_date = "2025-01-15"

# 5 dias antes
scheduled_date_5d = due_date - timedelta(days=5)  # 2025-01-10

# 3 dias antes
scheduled_date_3d = due_date - timedelta(days=3)  # 2025-01-12

# 1 dia antes
scheduled_date_1d = due_date - timedelta(days=1)  # 2025-01-14
```

### **Para "Vencidos" (Overdue):**
```python
due_date = "2025-01-15"
today = "2025-01-16"  # Assumindo que já venceu

# 1 dia depois
scheduled_date_1d = due_date + timedelta(days=1)  # 2025-01-16

# 3 dias depois
scheduled_date_3d = due_date + timedelta(days=3)  # 2025-01-18

# 5 dias depois
scheduled_date_5d = due_date + timedelta(days=5)  # 2025-01-20
```

**⚠️ IMPORTANTE:** 
- Para "vencidos", só criar mensagens se `due_date < hoje`. Se `due_date >= hoje`, não criar mensagens de "vencido" ainda.
- **Regra de Antecipação/Postergação:**
  - **Upcoming (A Vencer):** Se `scheduled_date` cair em fim de semana → **ANTECIPAR** para último dia útil ANTES
  - **Overdue (Vencido):** Se `scheduled_date` cair em fim de semana → **POSTERGAR** para próximo dia útil DEPOIS

---

## 🎯 **CENÁRIOS DE USO**

### **Cenário 1: Cobrança Normal**
1. Cliente envia cobrança com `due_date = 2025-01-15`
2. Sistema cria:
   - `BillingCycle` (status: active)
   - 3 mensagens "a vencer" (5d, 3d, 1d antes)
   - 3 mensagens "vencido" (1d, 3d, 5d depois) - aguardando vencimento
3. Scheduler envia mensagens conforme datas chegam
4. Cliente paga → Envia cancelamento → Ciclo marcado como 'paid'

### **Cenário 2: Cobrança Já Vencida**
1. Cliente envia cobrança com `due_date = 2025-01-10` (já passou)
2. Sistema cria:
   - `BillingCycle` (status: active)
   - 0 mensagens "a vencer" (já passou)
   - 3 mensagens "vencido" (1d, 3d, 5d depois) - algumas podem ser enviadas imediatamente
3. Scheduler verifica: se `scheduled_date <= hoje`, envia imediatamente

### **Cenário 3: Cancelamento Antecipado**
1. Cliente envia cobrança
2. Sistema cria ciclo completo
3. Cliente envia cancelamento ANTES de qualquer mensagem ser enviada
4. Sistema marca ciclo como 'cancelled'
5. Scheduler ignora todas as mensagens pendentes

---

## 🔍 **QUESTÕES A RESOLVER**

### **1. Template Selection**
- Como escolher qual template usar para cada mensagem do ciclo?
  - **Opção A:** Um template por tipo (upcoming_5d, upcoming_3d, etc)
  - **Opção B:** Um template genérico que recebe `{{dias_vencimento}}` ou `{{dias_atraso}}`
  - **Recomendação:** Opção B (mais flexível)

### **2. Variações de Template**
- Cada mensagem do ciclo deve usar variação diferente?
  - **Recomendação:** Sim, rotacionar variações para reduzir bloqueio

### **3. Dias Úteis**
- Mensagens devem respeitar dias úteis?
  - **Recomendação:** Sim, usar `BusinessHoursService` existente

### **4. Horário Comercial**
- Mensagens agendadas devem respeitar horário comercial?
  - **Recomendação:** Sim, mas se `scheduled_date` cair em fim de semana, enviar no próximo dia útil

### **5. Retry em Falhas**
- Se mensagem do ciclo falhar, deve tentar novamente?
  - **Recomendação:** Sim, mas limitado (ex: 2 tentativas)

### **6. Status do Ciclo**
- Quando marcar ciclo como 'completed'?
  - **Recomendação:** Quando todas as mensagens do ciclo foram enviadas (sent ou failed)

---

## 📋 **CHECKLIST DE IMPLEMENTAÇÃO**

### **Fase 1: Modelos e Estrutura**
- [ ] Criar modelo `BillingCycle`
- [ ] Modificar `BillingContact` (adicionar campos de ciclo)
- [ ] Criar migrations SQL
- [ ] Criar serializers

### **Fase 2: Services**
- [ ] Criar `BillingCycleService`
- [ ] Modificar `BillingCampaignService` para suportar ciclos
- [ ] Criar `BillingCycleScheduler` (verificação diária)

### **Fase 3: APIs**
- [ ] Criar endpoint `POST /billing/v1/billing/send/batch`
- [ ] Criar endpoint `POST /billing/v1/billing/cancel`
- [ ] Modificar endpoints existentes (opcional)

### **Fase 4: Scheduler**
- [ ] Implementar verificação diária (cron ou Celery Beat)
- [ ] Integrar com RabbitMQ para envio
- [ ] Tratamento de erros

### **Fase 5: Frontend**
- [ ] Página de visualização de ciclos
- [ ] Dashboard com estatísticas de ciclos
- [ ] Filtros e busca

---

## 🎓 **LIÇÕES E CONSIDERAÇÕES**

### **Performance:**
- Scheduler deve processar em batches (ex: 100 ciclos por vez)
- Índices em `scheduled_date` e `status` são críticos
- Considerar particionamento por data se volume for alto

### **Segurança:**
- Validar `external_billing_id` único por tenant
- Rate limiting no endpoint de batch
- Logs de auditoria para cancelamentos

### **Resiliência:**
- Scheduler deve ser idempotente (não enviar mensagem duplicada)
- Tratamento de falhas no scheduler
- Alertas se scheduler não executar

---

## ✅ **PRÓXIMOS PASSOS**

1. **Validar proposta** com stakeholders
2. **Definir template de mensagem** (como será a estrutura)
3. **Decidir sobre scheduler** (cron, Celery Beat, ou outro)
4. **Criar protótipo** de um ciclo simples
5. **Testar fluxo completo** antes de implementar tudo

---

**Status:** 📋 **AGUARDANDO APROVAÇÃO PARA IMPLEMENTAÇÃO**

