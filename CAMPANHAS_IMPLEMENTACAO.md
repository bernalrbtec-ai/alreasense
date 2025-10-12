# 📤 Sistema de Campanhas - Implementação Completa

## ✅ **O que foi implementado:**

### **1. Modelos (Backend - Django)**

#### **Campaign** - Campanha Principal
- ✅ Nome, descrição, tenant
- ✅ **3 Modos de Rotação:**
  - `round_robin`: Rotação sequencial
  - `balanced`: Balanceamento por uso
  - `intelligent`: Inteligente (padrão) - baseado em health
- ✅ Seleção de múltiplas instâncias WhatsApp
- ✅ Configurações de envio (intervalo, limites)
- ✅ Status (draft, scheduled, running, paused, completed, cancelled)
- ✅ Contadores (enviadas, entregues, lidas, falhadas)
- ✅ Métricas calculadas (taxa de sucesso, progresso, etc)

#### **CampaignMessage** - Variações de Mensagem
- ✅ Múltiplas mensagens por campanha
- ✅ Ordem de uso
- ✅ Contador de uso
- ✅ Suporte a mídia (imagem, vídeo, áudio, documento)

#### **CampaignContact** - Relacionamento Campanha-Contato
- ✅ Status individual (pending, sending, sent, delivered, read, failed)
- ✅ Instância usada para envio
- ✅ Mensagem usada
- ✅ Timestamps de todas as etapas
- ✅ Erro detalhado (se houver)
- ✅ ID da mensagem no WhatsApp
- ✅ Contador de tentativas

#### **CampaignLog** 🆕 - Sistema Completo de Logs
- ✅ **18 tipos de eventos:**
  - created, started, paused, resumed, completed, cancelled
  - instance_selected, instance_paused, instance_resumed
  - message_sent, message_delivered, message_read, message_failed
  - rotation_changed, contact_added, contact_removed
  - limit_reached, health_issue, error

- ✅ **4 níveis de severidade:**
  - info, warning, error, critical

- ✅ **Dados capturados:**
  - Mensagem descritiva
  - Detalhes estruturados (JSON)
  - Relacionamentos (campanha, instância, contato)
  - Performance (duração em ms)
  - Request/Response (para debug)
  - HTTP status
  - Snapshot de métricas (progresso, health score)
  - Usuário que executou a ação

- ✅ **Métodos estáticos para facilitar logging:**
  - `log_campaign_created()`
  - `log_campaign_started()`
  - `log_message_sent()`
  - `log_message_delivered()`
  - `log_message_read()`
  - `log_message_failed()`
  - `log_instance_selected()`
  - `log_instance_paused()`
  - `log_limit_reached()`
  - `log_health_issue()`
  - `log_error()`

- ✅ **Índices otimizados:**
  - Por campanha + data
  - Por tipo de log + data
  - Por severidade + data
  - Por instância + data

### **2. Health Tracking em WhatsAppInstance**

#### **Novos campos:**
- ✅ `health_score` (0-100)
- ✅ `msgs_sent_today`
- ✅ `msgs_delivered_today`
- ✅ `msgs_read_today`
- ✅ `msgs_failed_today`
- ✅ `consecutive_errors`
- ✅ `last_success_at`
- ✅ `last_health_update`
- ✅ `health_last_reset` (para reset diário)

#### **Novos métodos:**
- ✅ `reset_daily_counters_if_needed()` - Reset automático à meia-noite
- ✅ `record_message_sent()` - Incrementa contador
- ✅ `record_message_delivered()` - Incrementa + bônus no health (+0.5)
- ✅ `record_message_read()` - Incrementa + bônus maior (+1)
- ✅ `record_message_failed()` - Incrementa + penalidade (-10)
- ✅ `delivery_rate` (property) - Taxa de entrega
- ✅ `read_rate` (property) - Taxa de leitura
- ✅ `is_healthy` (property) - Verifica se está saudável
- ✅ `health_status` (property) - Status textual (excellent, good, warning, critical)
- ✅ `can_send_message()` - Verifica se pode enviar (considerando limites)

### **3. API REST (Django REST Framework)**

#### **Endpoints Implementados:**

```
GET    /api/campaigns/campaigns/          - Listar campanhas
POST   /api/campaigns/campaigns/          - Criar campanha
GET    /api/campaigns/campaigns/{id}/     - Detalhes da campanha
PATCH  /api/campaigns/campaigns/{id}/     - Atualizar campanha
DELETE /api/campaigns/campaigns/{id}/     - Deletar campanha

POST   /api/campaigns/campaigns/{id}/start/    - Iniciar campanha
POST   /api/campaigns/campaigns/{id}/pause/    - Pausar campanha
POST   /api/campaigns/campaigns/{id}/resume/   - Retomar campanha
POST   /api/campaigns/campaigns/{id}/cancel/   - Cancelar campanha

GET    /api/campaigns/campaigns/{id}/contacts/ - Listar contatos da campanha
GET    /api/campaigns/campaigns/{id}/logs/     - Listar logs da campanha
GET    /api/campaigns/campaigns/stats/         - Estatísticas gerais
```

#### **Filtros nos Logs:**
- `?log_type=message_sent` - Filtrar por tipo
- `?severity=error` - Filtrar por severidade
- `?limit=50` - Limitar quantidade

#### **Serializers:**
- ✅ `CampaignSerializer` - Completo com nested relationships
- ✅ `CampaignMessageSerializer` - Mensagens
- ✅ `CampaignContactSerializer` - Contatos
- ✅ `CampaignLogSerializer` - Logs
- ✅ `CampaignStatsSerializer` - Estatísticas
- ✅ `CampaignInstanceSerializer` - Instâncias simplificadas

### **4. Segurança e Isolamento**

- ✅ **Filtro por Tenant:** Cada cliente vê apenas suas campanhas
- ✅ **Autenticação obrigatória:** `IsAuthenticated`
- ✅ **Logs imutáveis:** Não podem ser editados/deletados manualmente
- ✅ **Auto-associação:** Campanha criada automaticamente associada ao tenant do usuário

### **5. Migrations**

- ✅ `0001_initial` - Criação de todas as tabelas
- ✅ `notifications.0002` - Campos de health tracking
- ✅ Índices otimizados para queries rápidas

### **6. Admin do Django**

- ✅ Interface completa para gerenciar campanhas
- ✅ Filtros por status, modo de rotação, data
- ✅ Busca por nome, tenant
- ✅ Logs read-only (não editáveis)
- ✅ Exibição de métricas

---

## 📊 **Como os Logs Funcionam:**

### **Cenário 1: Criação de Campanha**
```python
# Ao criar campanha
campaign = Campaign.objects.create(...)
CampaignLog.log_campaign_created(campaign, user)

# Log criado:
{
  "log_type": "created",
  "severity": "info",
  "message": "Campanha 'Black Friday 2025' criada",
  "details": {
    "rotation_mode": "intelligent",
    "total_contacts": 500,
    "instances_count": 3
  },
  "created_by": user
}
```

### **Cenário 2: Envio de Mensagem**
```python
import time
start_time = time.time()

# Enviar mensagem via API
response = instance.send_message(contact.phone, message)

duration_ms = (time.time() - start_time) * 1000

# Log de envio
CampaignLog.log_message_sent(
    campaign, instance, contact, campaign_contact,
    duration_ms=duration_ms
)

# Log criado:
{
  "log_type": "message_sent",
  "severity": "info",
  "message": "Mensagem enviada para João Silva",
  "details": {
    "contact_id": "uuid",
    "contact_phone": "5511999999999",
    "instance_id": "uuid",
    "instance_name": "Paulo Cel"
  },
  "instance": instance,
  "contact": contact,
  "campaign_contact": campaign_contact,
  "duration_ms": 245,
  "campaign_progress": 45.5,
  "instance_health_score": 95
}
```

### **Cenário 3: Falha no Envio**
```python
try:
    instance.send_message(contact.phone, message)
except Exception as e:
    # Log de falha com todos os detalhes
    CampaignLog.log_message_failed(
        campaign, instance, contact, campaign_contact,
        error_msg=str(e),
        request_data={"phone": contact.phone, "message": message},
        response_data=response_data,
        http_status=400
    )

# Log criado:
{
  "log_type": "message_failed",
  "severity": "error",
  "message": "Falha ao enviar para João Silva: Number not registered",
  "details": {
    "contact_id": "uuid",
    "contact_phone": "5511999999999",
    "error": "Number not registered on WhatsApp"
  },
  "request_data": {...},
  "response_data": {...},
  "http_status": 400,
  "instance_health_score": 85
}
```

### **Cenário 4: Problema de Saúde**
```python
# Ao detectar health baixo
if instance.health_score < 50:
    CampaignLog.log_health_issue(
        campaign, instance,
        "Health score abaixo do limite mínimo"
    )
    # Pausar instância automaticamente
    CampaignLog.log_instance_paused(
        campaign, instance,
        reason="Health score crítico: 42"
    )
```

---

## 🔍 **Queries de Análise com os Logs:**

### **1. Taxa de sucesso por instância:**
```python
logs = CampaignLog.objects.filter(
    campaign=campaign,
    instance=instance,
    log_type__in=['message_sent', 'message_failed']
)
success = logs.filter(log_type='message_sent').count()
failed = logs.filter(log_type='message_failed').count()
rate = (success / (success + failed)) * 100
```

### **2. Erros mais comuns:**
```python
error_logs = CampaignLog.objects.filter(
    campaign=campaign,
    log_type='message_failed'
).values('details__error').annotate(count=Count('id')).order_by('-count')
```

### **3. Performance média:**
```python
avg_duration = CampaignLog.objects.filter(
    campaign=campaign,
    log_type='message_sent'
).aggregate(avg=Avg('duration_ms'))
```

### **4. Timeline da campanha:**
```python
logs = CampaignLog.objects.filter(
    campaign=campaign
).order_by('created_at')
```

### **5. Problemas críticos:**
```python
critical_logs = CampaignLog.objects.filter(
    campaign=campaign,
    severity__in=['error', 'critical']
).order_by('-created_at')
```

---

## 🎯 **Próximos Passos (Não Implementados Ainda):**

1. ⏳ **Lógica de Rotação Completa** (RR, Balanceado, Inteligente)
2. ⏳ **Tasks Celery** para processamento assíncrono
3. ⏳ **Frontend** - Página de campanhas
4. ⏳ **Testes automatizados** completos
5. ⏳ **Dashboard** de analytics com gráficos
6. ⏳ **Webhooks** para atualizar status em tempo real
7. ⏳ **Rate limiting** inteligente por instância
8. ⏳ **Warming up** automático para instâncias novas

---

## ✅ **Status Atual:**

- ✅ Backend: Modelos, API, Logs **COMPLETO**
- ✅ Migrations: **APLICADAS**
- ✅ Admin: **CONFIGURADO**
- ⏳ Lógica de Rotação: **PENDENTE**
- ⏳ Tasks Celery: **PENDENTE**
- ⏳ Frontend: **PENDENTE**
- ⏳ Testes: **PENDENTE**

---

## 📝 **Teste Manual via API:**

```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "paulo.bernal@rbtec.com.br", "password": "senha123"}'

# 2. Criar Campanha
curl -X POST http://localhost:8000/api/campaigns/campaigns/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste",
    "rotation_mode": "intelligent",
    "instances": ["uuid1", "uuid2"],
    "messages": [{"content": "Olá!", "order": 1}]
  }'

# 3. Ver Logs
curl http://localhost:8000/api/campaigns/campaigns/{id}/logs/ \
  -H "Authorization: Bearer {token}"
```

---

**🎉 Sistema de logs está 100% funcional e pronto para capturar TUDO!**



