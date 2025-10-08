# 🚀 ALREA CAMPAIGNS - Roadmap MVP

> **Objetivo:** Sistema de disparos WhatsApp funcionando em 2-3 dias  
> **Estratégia:** MVP primeiro, features avançadas depois  
> **Data:** 2025-10-08

---

## 📊 FASES DE IMPLEMENTAÇÃO

### **FASE 1: MVP - Sistema Core (2-3 DIAS)** ⭐ PRIORIDADE MÁXIMA

**Objetivo:** Disparos funcionando com controle total

#### Funcionalidades Incluídas:
- ✅ CRUD de campanhas (criar, editar, listar)
- ✅ Cadastro manual de até 5 mensagens
- ✅ Preview WhatsApp em tempo real (modal split)
- ✅ Rotação balanceada de mensagens
- ✅ Sistema de janelas (imediato, dias úteis, horário comercial, personalizado)
- ✅ Pausar/Retomar/Encerrar campanhas
- ✅ Lock anti-spam (mesmo número em múltiplas campanhas)
- ✅ Logs detalhados
- ✅ Dashboard básico de acompanhamento
- ✅ Celery + Workers funcionando

#### NÃO Incluído (Fase 2):
- ❌ Geração de mensagens com IA (N8N)
- ❌ Dashboard avançado de métricas
- ❌ Reutilização de mensagens de sucesso
- ❌ Sugestões inteligentes

---

## 📅 CRONOGRAMA DETALHADO

### **DIA 1: Backend Core (6-7h)**

```
08:00 - 10:00 | Models + Migrations (2h)
──────────────────────────────────────────────
✅ Campaign
✅ CampaignMessage  
✅ CampaignContact
✅ CampaignLog
✅ Holiday
✅ Rodar migrations

10:00 - 11:30 | Serializers (1.5h)
──────────────────────────────────────────────
✅ CampaignSerializer (com validações)
✅ MessageSerializer
✅ CampaignContactSerializer
✅ Validators customizados

11:30 - 13:30 | API REST (2h)
──────────────────────────────────────────────
✅ CampaignViewSet (CRUD)
✅ Endpoints: start, pause, resume, cancel
✅ MessageViewSet (CRUD)
✅ Endpoint: preview (3 contatos)

13:30 - 15:00 | Services (1.5h)
──────────────────────────────────────────────
✅ CampaignService (start, pause, resume)
✅ MessageRotationService
✅ is_allowed_to_send()
✅ calculate_next_send_time()

15:00 - 16:00 | Testes Básicos (1h)
──────────────────────────────────────────────
✅ Criar campanha via API
✅ Adicionar mensagens
✅ Testar validações
✅ Testar pause/resume

TOTAL DIA 1: 7 horas ✅
ENTREGÁVEL: API REST funcionando
```

### **DIA 2: Celery + Disparos (6-7h)**

```
08:00 - 09:00 | Setup Celery (1h)
──────────────────────────────────────────────
✅ Configurar celery.py
✅ settings.py (broker, beat schedule)
✅ Instalar Redis (se necessário)
✅ Testar celery worker + beat

09:00 - 11:30 | Tasks Principais (2.5h)
──────────────────────────────────────────────
✅ campaign_scheduler (beat task - 10s)
✅ send_message_task (dispatcher)
✅ Sistema de lock Redis (anti-spam)
✅ Integração is_allowed_to_send()

11:30 - 13:30 | Integração WhatsApp Gateway (2h)
──────────────────────────────────────────────
✅ WhatsAppGatewayService
✅ Método send_text_message()
✅ Tratamento de erros
✅ Parsing de responses

13:30 - 15:00 | Testes End-to-End (1.5h)
──────────────────────────────────────────────
✅ Criar campanha
✅ Iniciar campanha
✅ Verificar disparo real
✅ Testar pause durante disparo
✅ Testar retomada
✅ Verificar logs

15:00 - 16:00 | Seed de Feriados + Ajustes (1h)
──────────────────────────────────────────────
✅ Seed de feriados 2025
✅ Testar skip_weekends
✅ Testar skip_holidays
✅ Ajustar delays

TOTAL DIA 2: 7 horas ✅
ENTREGÁVEL: Disparos funcionando corretamente
```

### **DIA 3: Frontend + UI (8h)**

```
08:00 - 09:00 | API Client TypeScript (1h)
──────────────────────────────────────────────
✅ campaigns.ts
✅ messages.ts
✅ Types e interfaces

09:00 - 12:00 | Preview WhatsApp (3h) ⭐ Mais complexo
──────────────────────────────────────────────
✅ WhatsAppSimulator component
✅ Header verde, avatar, status
✅ Background estilo WhatsApp
✅ Balão verde com tail
✅ Timestamp + check marks
✅ Input bar visual
✅ Renderização de variáveis
✅ Navegação entre 3 contatos

12:00 - 14:00 | MessageEditorModal (2h)
──────────────────────────────────────────────
✅ Layout split (editor + preview)
✅ Textarea com ref (cursor position)
✅ Painel de variáveis clicáveis
✅ Inserção na posição do cursor
✅ Contador de caracteres
✅ Integração com preview

14:00 - 16:00 | Páginas Principais (2h)
──────────────────────────────────────────────
✅ CampaignsListPage
✅ CampaignCreatePage
✅ CampaignDetailsPage (com logs)
✅ Cards de campanha com status

16:00 - 17:00 | Botão IA "Em breve" (1h)
──────────────────────────────────────────────
✅ Botão desabilitado com badge "Em breve"
✅ Tooltip explicativo
✅ UI preparada para Fase 2
✅ Sem bloquear fluxo (pode criar manual)

TOTAL DIA 3: 8 horas ✅
ENTREGÁVEL: UI completa + Disparos via interface
```

---

## ✅ ESTIMATIVA FINAL (SEM IA)

### **Otimista: 2 dias**
```
Dia 1: Backend (7h)
Dia 2: Celery + Frontend (até 16h)

Total: ~14-16h de dev
Se trabalhar 8h/dia: 2 dias
```

### **Realista: 2.5-3 dias** 👈 **RECOMENDADO**
```
Dia 1: Backend + testes (7h)
Dia 2: Celery + WhatsApp + testes (7h)
Dia 3: Frontend + refinamentos (6-8h)

Total: ~20h de dev
Considerando bugs/ajustes: 2.5-3 dias
```

### **Com Imprevistos: 3-4 dias**
```
+ Problemas com Celery/Redis
+ Bugs na integração WhatsApp
+ Ajustes de CSS no simulador
+ Tweaks de UX

Total: 3-4 dias
```

---

## 🎯 MVP SCOPE (O QUE ENTREGAR)

### **Backend:**
- ✅ 6 Models completos
- ✅ API REST (15+ endpoints)
- ✅ Celery scheduler (10s)
- ✅ Celery dispatcher (workers)
- ✅ Integração WhatsApp Gateway
- ✅ Sistema de locks Redis
- ✅ Validações de horário/feriados

### **Frontend:**
- ✅ Lista de campanhas
- ✅ Criar campanha (wizard/formulário)
- ✅ **Modal de mensagens com preview WhatsApp** ⭐
- ✅ Detalhes de campanha (progresso, logs)
- ✅ Controles (pausar, retomar, encerrar)
- ✅ Dashboard básico

### **Funcional:**
- ✅ Criar campanha com 1-5 mensagens
- ✅ Selecionar contatos (por tag ou manual)
- ✅ Configurar janelas de disparo
- ✅ Iniciar campanha
- ✅ Pausar/retomar em tempo real
- ✅ Rotação automática de mensagens
- ✅ Respeitar horários e feriados
- ✅ Logs completos

---

## 🔄 FASE 2: Features Avançadas (DEPOIS DO MVP)

### **Prioridade Alta:**
1. **Geração IA (N8N)** - 2 dias
   - Integração com webhook N8N
   - Prompt engineering
   - Modal de aprovação de variações
   - Testes de qualidade

2. **Dashboard de Métricas** - 1 dia
   - Melhor mensagem (taxa de resposta)
   - Melhor horário
   - Gráficos por hora
   - Insights automáticos

3. **Reutilização de Mensagens** - 0.5 dia
   - Sugestões baseadas em campanhas anteriores
   - "Usar como base"

### **Prioridade Média:**
4. **Envio de Mídias** - 2 dias
   - Upload de imagens
   - Vídeos, áudios
   - Preview de mídia

5. **Templates Salvos** - 1 dia
   - Biblioteca de mensagens
   - Tags e categorias

### **Prioridade Baixa:**
6. **A/B Testing** - 2 dias
7. **Webhooks** - 1 dia
8. **API Pública** - 2 dias

---

## 🎯 CHECKLIST DE ENTREGA MVP

### **Antes de considerar MVP pronto:**

**Backend:**
- [ ] Todas as migrations rodando
- [ ] API REST testada (Postman/Thunder)
- [ ] Celery scheduler rodando a cada 10s
- [ ] Workers processando tasks
- [ ] Envio real via WhatsApp funcionando
- [ ] Pause/resume funcionando corretamente
- [ ] Logs sendo criados

**Frontend:**
- [ ] Criar campanha (formulário completo)
- [ ] Adicionar 1-5 mensagens manualmente
- [ ] **Preview WhatsApp funcionando** ⭐
- [ ] Variáveis sendo renderizadas
- [ ] Navegação entre 3 contatos no preview
- [ ] Lista de campanhas com status
- [ ] Detalhes com progresso em tempo real
- [ ] Botões de controle funcionando

**Integração:**
- [ ] Campanha iniciada dispara envios
- [ ] Mensagens chegam no WhatsApp
- [ ] Logs aparecem no frontend
- [ ] Pause interrompe imediatamente
- [ ] Resume retoma de onde parou
- [ ] Janelas de horário respeitadas
- [ ] Feriados/fim de semana pulados

---

## 💡 DICAS PARA ACELERAR

### **Use o que já existe:**
```
✅ Auth/Multi-tenant do ALREA Sense (pronto)
✅ Billing/Planos (pronto)
✅ Frontend base React (pronto)
✅ PostgreSQL + Redis (já configurado)
```

### **Implemente incremental:**
```
Dia 1: Backend funcional (mesmo sem frontend)
  ↓ Testar via Postman/Django Admin
  
Dia 2: Celery funcional (mesmo sem frontend)
  ↓ Testar criando campanha via Admin
  ↓ Verificar se dispara
  
Dia 3: Frontend
  ↓ Conectar com backend já testado
```

### **Priorize o crítico:**
```
1. Disparo funcionando ⭐⭐⭐
2. Pause/resume funcionando ⭐⭐⭐
3. Preview WhatsApp bonito ⭐⭐
4. Tudo mais ⭐
```

---

## 🎯 RESPOSTA FINAL

### **2-3 dias é VIÁVEL? SIM!** ✅

**Breakdown:**
- **Dia 1:** Backend completo
- **Dia 2:** Celery + disparos reais funcionando  
- **Dia 3:** UI + Preview WhatsApp

**Com IA removida do MVP:** Economiza 1-1.5 dias!

**Podemos implementar IA depois tranquilamente** (já deixamos UI preparada com botão "Em breve")

---

**Resumo:** Com foco e sem distrações, **2 dias** é apertado mas possível. **3 dias** é confortável e realista. 

Me avisa quando terminar o básico! 🚀

