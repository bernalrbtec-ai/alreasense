# 🚀 **SISTEMA DE BILLING - DOCUMENTAÇÃO COMPLETA**

> **Sistema de Cobrança e Notificações via WhatsApp**  
> Multi-tenant | Alta Performance | Resiliente | Escalável

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-green.svg)](https://www.djangoproject.com/)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-aio--pika-orange.svg)](https://aio-pika.readthedocs.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)

---

## 📚 **DOCUMENTAÇÃO**

### 🎯 **COMECE AQUI:**

| Documento | Descrição | Para quem? |
|-----------|-----------|------------|
| **[📋 ÍNDICE MESTRE](./BILLING_SYSTEM_INDEX.md)** | Navegação e visão geral completa | 👥 Todos |
| **[🎯 REGRAS E DECISÕES](./BILLING_SYSTEM_RULES.md)** | **LEIA PRIMEIRO!** Todas as regras e decisões | 👨‍💻 Devs |
| **[🔧 EVOLUTION API SERVICE](./EVOLUTION_API_SERVICE_SPEC.md)** | Especificação completa do serviço centralizado | 👨‍💻 Devs |
| **[⚡ QUICK START](./BILLING_QUICKSTART.md)** | Teste em 15 minutos | 👨‍💻 Devs |
| **[🔧 ERRATA](./BILLING_SYSTEM_ERRATA.md)** | Correções e complementos | 👨‍💻 Devs |
| **[🔄 REUTILIZAÇÃO](./BILLING_SYSTEM_REUSE_ANALYSIS.md)** | O que já existe e pode ser aproveitado | 👨‍💻 Devs |

### 📖 **GUIAS COMPLETOS:**

| Documento | Conteúdo |
|-----------|----------|
| **[📄 PARTE 1](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md)** | Arquitetura, Models, Utils, Workers, RabbitMQ |
| **[📄 PARTE 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md)** | Services, APIs, Serializers, Observabilidade, Troubleshooting |

---

## 🎯 **O QUE É?**

Sistema que permite **clientes externos** (ERPs, CRMs, etc) enviarem cobranças, lembretes e notificações via API REST, que são automaticamente processadas e enviadas via **WhatsApp** usando a **Evolution API**.

### **3 Tipos de Mensagens:**

| Tipo | Descrição | Prioridade | Horário Comercial |
|------|-----------|------------|-------------------|
| 🔴 **Overdue** | Cobrança atrasada | Alta (10) | ✅ Sim |
| 🟡 **Upcoming** | Cobrança a vencer | Média (5) | ✅ Sim |
| 🔵 **Notification** | Avisos gerais | Baixa (1) | ❌ Não (24/7) |

---

## ✨ **FEATURES PRINCIPAIS**

### **🎭 Anti-Bloqueio WhatsApp**
- ✅ Até 5 variações por template
- ✅ Rotação aleatória, sequencial ou ponderada
- ✅ Tracking de performance por variação

### **🕐 Respeito ao Horário Comercial**
- ✅ Pausa automática fora do horário
- ✅ Retoma automática no próximo horário válido
- ✅ Notificações 24/7 (opcional)
- ✅ Configura dias úteis e fins de semana

### **⚡ Throttling Inteligente**
- ✅ Configurável por tenant (ex: 20 msgs/min)
- ✅ Rate limiting por API Key
- ✅ Rate limiting por IP (proteção adicional)

### **🏥 Resiliente**
- ✅ Detecta instância Evolution offline
- ✅ Pausa automática quando offline
- ✅ Monitora recuperação
- ✅ Retoma automática quando volta
- ✅ Retry automático inteligente

### **📊 Observabilidade**
- ✅ Prometheus metrics
- ✅ Structured logging
- ✅ Health checks (heartbeat)
- ✅ Progress tracking (ETA)
- ✅ Webhooks para callbacks

### **🔐 Segurança**
- ✅ API Key authentication
- ✅ Rate limiting (API Key + IP)
- ✅ Template sanitization (XSS)
- ✅ Phone validation
- ✅ Multi-tenant nativo

---

## 🏗️ **ARQUITETURA**

```
┌─────────────┐
│   ERP/CRM   │  (Cliente Externo)
└──────┬──────┘
       │ POST /api/v1/billing/send/overdue
       ▼
┌─────────────────────────────────────────┐
│          DJANGO REST API                │
│  • Authentication (API Key)              │
│  • Rate Limiting                         │
│  • Validation                            │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│     BILLING CAMPAIGN SERVICE            │
│  • Cria Campaign + Queue                │
│  • Enriquece variáveis (calcula dias)   │
│  • Seleciona variações                  │
│  • Valida horário comercial             │
└──────────┬──────────────────────────────┘
           │
           ▼ Publica mensagem
┌─────────────────────────────────────────┐
│          RABBITMQ (Broker)              │
│  Queue: billing.overdue (prioridade 10) │
│  Queue: billing.upcoming (prioridade 5) │
│  Queue: billing.notification (prio 1)   │
└──────────┬──────────────────────────────┘
           │
           ▼ Consumer pega mensagem
┌─────────────────────────────────────────┐
│        BILLING SENDER WORKER            │
│  • Processa em batches (100 por vez)    │
│  • Throttling (ex: 1 msg a cada 3 seg)  │
│  • Verifica horário antes de CADA msg   │
│  • Verifica instância (health check)    │
│  • Retry em falhas                      │
│  • Heartbeat (worker health)            │
└──────────┬──────────────────────────────┘
           │
           ▼ Envia mensagem
┌─────────────────────────────────────────┐
│         EVOLUTION API                   │
│  • Envia via WhatsApp                   │
│  • Retorna status (sent/delivered/read) │
└──────────┬──────────────────────────────┘
           │
           ▼ Salva histórico
┌─────────────────────────────────────────┐
│        CHAT SYSTEM (Histórico)          │
│  • Cria/atualiza Conversation           │
│  • Salva Message                        │
│  • Fecha conversa automaticamente       │
│  • Reabre se cliente responder          │
└─────────────────────────────────────────┘
```

---

## 📦 **STACK TECNOLÓGICA**

| Componente | Tecnologia | Versão |
|------------|------------|--------|
| **Backend** | Django + DRF | 5.0+ |
| **Queue** | RabbitMQ + aio-pika | ⚠️ **NÃO Celery!** |
| **Database** | PostgreSQL | 15+ |
| **Cache** | Redis | 7+ |
| **WhatsApp** | Evolution API | Latest |
| **Metrics** | Prometheus | - |
| **Deploy** | Railway | - |

---

## ⏱️ **TEMPO DE IMPLEMENTAÇÃO**

### **Breakdown por Fase:**

| Fase | Descrição | Tempo | Complexidade |
|------|-----------|-------|--------------|
| **1** | Models + Migrations | 2-3 dias | Média |
| **2** | Utils (Validators, Template Engine) | 1-2 dias | Baixa |
| **3** | Services (Campaign, Send, Scheduler) | 3-4 dias | Alta |
| **4** | Worker + RabbitMQ | 3-4 dias | Alta |
| **5** | APIs + Serializers | 2-3 dias | Média |
| **6** | Integração com Chat | 1-2 dias | Média |
| **7** | Testes (>80% coverage) | 2-3 dias | Média |
| **8** | Deploy + Monitoramento | 1-2 dias | Baixa |
| **TOTAL** | - | **15-20 dias** | - |

*1 desenvolvedor experiente em tempo integral*

---

## 🚀 **ROTEIRO RÁPIDO**

### **1️⃣ Leitura (1-2 horas)**
1. ✅ Ler [ÍNDICE MESTRE](./BILLING_SYSTEM_INDEX.md)
2. ✅ Ler **[ERRATA](./BILLING_SYSTEM_ERRATA.md)** (CRÍTICO!)
3. ✅ Ler [PARTE 1](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md) - Arquitetura
4. ✅ Ler [PARTE 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md) - APIs

### **2️⃣ Setup Inicial (1 hora)**
1. ✅ Criar branch: `git checkout -b feature/billing-system`
2. ✅ Criar estrutura de pastas (ver ERRATA)
3. ✅ Adicionar ao `INSTALLED_APPS`
4. ✅ Configurar URLs

### **3️⃣ Teste Rápido (15 minutos)**
1. ✅ Seguir [QUICK START](./BILLING_QUICKSTART.md)
2. ✅ Criar templates de teste
3. ✅ Criar API Key
4. ✅ Fazer request de teste
5. ✅ Verificar mensagem no WhatsApp

### **4️⃣ Implementação Completa (15-20 dias)**
1. ✅ Seguir [Checklist - Parte 1](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#checklist-de-implementação)
2. ✅ Testar cada fase antes de avançar
3. ✅ Usar [Troubleshooting - Parte 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#troubleshooting) quando necessário
4. ✅ Deploy em staging
5. ✅ Deploy em produção

---

## 📊 **ESTATÍSTICAS**

- **Linhas de código:** ~6.400
- **Linhas de documentação:** ~4.000
- **Arquivos criados:** 25+
- **Models:** 6
- **APIs:** 5 endpoints
- **Services:** 3 principais
- **Utils:** 4 helpers
- **Tests:** 5+ arquivos

---

## ⚠️ **PONTOS CRÍTICOS**

### **🔴 CRÍTICO (Não pode falhar!):**
1. ⚠️ **NÃO USE CELERY** - O projeto usa RabbitMQ + aio-pika
2. ⚠️ **Ler ERRATA primeiro** - Tem correções críticas
3. ⚠️ **SELECT FOR UPDATE** obrigatório no worker batch
4. ⚠️ **Instance Health Check** antes de CADA envio
5. ⚠️ **Bulk operations** para criar contatos (performance)

### **🟡 IMPORTANTE:**
1. ⚠️ Template sanitization (XSS)
2. ⚠️ Phone validation antes de criar contato
3. ⚠️ Rate limiting na API
4. ⚠️ Cache do business hours no worker
5. ⚠️ EvolutionAPIService (ver ERRATA)

### **🟢 RECOMENDADO:**
1. ✅ Prometheus metrics
2. ✅ Structured logging
3. ✅ Webhook callbacks
4. ✅ Frontend dashboard
5. ✅ Testes >80% coverage

---

## 🧪 **COMO TESTAR**

### **Teste Rápido (15 min):**
```bash
# 1. Seguir Quick Start
cat BILLING_QUICKSTART.md

# 2. Rodar consumer
python manage.py run_billing_consumer

# 3. Fazer request
curl -X POST http://localhost:8000/api/v1/billing/send/overdue \
  -H "X-Billing-API-Key: billing_..." \
  -H "Content-Type: application/json" \
  -d '{"external_id": "teste-001", "contacts": [...]}'
```

### **Testes Unitários:**
```bash
# Rodar todos os testes
python manage.py test apps.billing

# Com coverage
coverage run --source='apps.billing' manage.py test apps.billing
coverage report
```

### **Teste de Stress:**
```python
# Enviar 1000 mensagens de uma vez
# Ver PARTE 2 - Exemplos de Uso
```

---

## 🐛 **TROUBLESHOOTING**

### **Problema: Mensagens não enviando**
→ Ver [Troubleshooting - Parte 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#problema-1-mensagens-não-estão-sendo-enviadas)

### **Problema: Rate limit lento**
→ Ver [Troubleshooting - Parte 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#problema-2-rate-limit-muito-lento)

### **Problema: Imports faltando**
→ Ver [ERRATA](./BILLING_SYSTEM_ERRATA.md#imports-faltando)

### **Problema: Evolution API não funciona**
→ Ver [ERRATA](./BILLING_SYSTEM_ERRATA.md#problema-crítico-evolutionapiservice)

### **Outros problemas:**
→ Ver [FAQ - Parte 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#faq)

---

## 📞 **SUPORTE**

### **Dúvidas Frequentes:**
→ Ver [FAQ - Parte 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#faq)

### **Exemplos de Uso:**
→ Ver [Exemplos - Parte 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#exemplos-de-uso)

### **Erros Comuns:**
→ Ver [ERRATA](./BILLING_SYSTEM_ERRATA.md)

---

## 🎯 **ROADMAP FUTURO**

### **v1.1 (Planejado)**
- [ ] Frontend Dashboard completo
- [ ] Webhooks bidirecionais
- [ ] Analytics detalhado
- [ ] A/B testing de templates
- [ ] Agendamento avançado

### **v1.2 (Ideias)**
- [ ] Suporte a outros canais (SMS, Email)
- [ ] ML para otimizar horários de envio
- [ ] Segmentação avançada
- [ ] Templates dinâmicos (drag-and-drop)

---

## 📝 **CHANGELOG**

### **v1.0 (Dezembro 2025)** - Versão Inicial
- ✅ Arquitetura completa com RabbitMQ
- ✅ 6 Models com relacionamentos
- ✅ 3 tipos de mensagens (overdue, upcoming, notification)
- ✅ Anti-bloqueio WhatsApp (5 variações)
- ✅ Horário comercial (pausa/retoma)
- ✅ Throttling configurável
- ✅ Tratamento de instância offline
- ✅ Retry automático
- ✅ APIs REST completas
- ✅ Observabilidade (Prometheus)
- ✅ Documentação completa (4 documentos)
- ✅ Quick Start funcional
- ✅ Testes unitários de exemplo

---

## 🏆 **CONTRIBUIDORES**

Desenvolvido para **Alrea Sense** - Sistema de Chat e Campanhas Multi-tenant

---

## 📄 **LICENÇA**

Proprietary - Todos os direitos reservados

---

## 🚀 **COMEÇAR AGORA**

```bash
# 1. Ler documentação
cat BILLING_SYSTEM_INDEX.md
cat BILLING_SYSTEM_ERRATA.md  # ← CRÍTICO!

# 2. Teste rápido
cat BILLING_QUICKSTART.md

# 3. Implementação completa
# Seguir Parte 1 → Parte 2 → Checklist
```

---

**📚 [IR PARA ÍNDICE MESTRE](./BILLING_SYSTEM_INDEX.md)**

**🎯 [IR PARA REGRAS E DECISÕES (LEIA PRIMEIRO!)](./BILLING_SYSTEM_RULES.md)**

**🔧 [IR PARA EVOLUTION API SERVICE](./EVOLUTION_API_SERVICE_SPEC.md)**

**⚡ [IR PARA QUICK START](./BILLING_QUICKSTART.md)**

**🔧 [IR PARA ERRATA](./BILLING_SYSTEM_ERRATA.md)**

**🔄 [IR PARA ANÁLISE DE REUTILIZAÇÃO](./BILLING_SYSTEM_REUSE_ANALYSIS.md)**

---

<div align="center">

**🎉 Boa implementação!**

*Sistema de Billing - Alrea Sense*  
*Versão 1.0 - Dezembro 2025*

</div>

