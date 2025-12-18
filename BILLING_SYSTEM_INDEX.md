# 📚 **ÍNDICE MESTRE - SISTEMA DE BILLING**

> **Guia completo de implementação do Sistema de Cobrança e Notificações via WhatsApp**

---

## 🚀 **TL;DR (RESUMO EXECUTIVO)**

**O que é?** Sistema que permite clientes externos enviarem cobranças via API, processadas e enviadas automaticamente via WhatsApp.

**Principais Features:**
- ✅ 3 tipos de mensagens (atrasada, a vencer, notificação)
- ✅ Anti-bloqueio WhatsApp (5 variações por template)
- ✅ Horário comercial (pausa/retoma automático)
- ✅ Throttling configurável (ex: 20 msgs/min)
- ✅ Tratamento de instância offline
- ✅ Retry automático inteligente
- ✅ Multi-tenant nativo

**Tecnologias:**
- Backend: Django 5 + DRF
- Queue: RabbitMQ + aio-pika (NÃO Celery!)
- WhatsApp: Evolution API
- Database: PostgreSQL 15

**Tempo de Implementação:** 15-20 dias (1 dev experiente)

---

## 📋 **ESTRUTURA DOS DOCUMENTOS**

### 🎯 **REGRA MESTRE:** `BILLING_SYSTEM_RULES.md`
> **LEIA PRIMEIRO!** Todas as regras, decisões e padrões de código

**Conteúdo:**
- ✅ Decisões arquiteturais aprovadas
- ✅ O que reutilizar vs criar
- ✅ Padrões de código obrigatórios
- ✅ Estrutura de pastas completa
- ✅ EvolutionAPIService (decisão aprovada - ver spec separada)
- ✅ Checklist de implementação
- ✅ Cenários críticos

**[→ IR PARA REGRAS E DECISÕES](./BILLING_SYSTEM_RULES.md)** ⭐ **LEIA PRIMEIRO!**

---

### 🔧 **EVOLUTION API SERVICE:** `EVOLUTION_API_SERVICE_SPEC.md`
> **Especificação completa do serviço centralizado**

**Conteúdo:**
- ✅ API detalhada de todos os métodos
- ✅ Código completo de implementação
- ✅ Testes unitários
- ✅ Plano de migração passo a passo
- ✅ Roadmap futuro (v1.1, v1.2, etc.)

**[→ IR PARA SPEC DO EVOLUTION API SERVICE](./EVOLUTION_API_SERVICE_SPEC.md)**

---

### 🔧 **EVOLUTION API SERVICE:** `EVOLUTION_API_SERVICE_SPEC.md`
> **Especificação completa do serviço centralizado**

**Conteúdo:**
- ✅ API completa do serviço
- ✅ Implementação detalhada
- ✅ Exemplos de uso
- ✅ Plano de migração
- ✅ Testes
- ✅ Roadmap futuro

**[→ IR PARA EVOLUTION API SERVICE](./EVOLUTION_API_SERVICE_SPEC.md)** 🔧

---

### 📄 **PARTE 1:** `BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md`
> **Foco:** Arquitetura, Models, Utils, Workers e RabbitMQ

**Conteúdo:**
1. ✅ Visão Geral e Arquitetura
2. ✅ Modelos Completos (6 models)
   - BillingConfig
   - BillingAPIKey
   - BillingTemplate + Variations
   - BillingCampaign
   - BillingQueue
   - BillingContact
3. ✅ Utils e Helpers
   - PhoneValidator
   - TemplateSanitizer
   - DateCalculator
   - TemplateEngine
   - Constants
4. ✅ Tratamento de Falhas de Instância
   - InstanceHealthChecker
   - InstanceRecoveryService
5. ✅ Workers e RabbitMQ
   - BillingSenderWorker
   - BillingQueuePublisher
   - BillingConsumer
   - Management Commands
   - Periodic Tasks
6. ✅ Checklist de Implementação (8 fases)
7. ✅ Deploy no Railway

**[→ IR PARA PARTE 1](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md)**

---

### 📄 **PARTE 2:** `BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md`
> **Foco:** Services, APIs, Frontend, Observabilidade e Troubleshooting

**Conteúdo:**
1. ✅ Services Completos
   - BusinessHoursScheduler
   - BillingCampaignService (orchestrator)
   - BillingSendService
2. ✅ APIs REST Completas
   - Authentication (API Key)
   - Rate Limiting
   - Serializers
   - Views (5 endpoints)
   - URLs
3. ✅ Observabilidade
   - Prometheus Metrics
   - Structured Logging
   - Monitoring
4. ✅ Troubleshooting
   - Mensagens não enviando
   - Rate limit lento
   - Instância offline
   - Worker parado
5. ✅ FAQ
   - Como criar API Key
   - Como testar localmente
   - Como monitorar produção
6. ✅ Exemplos de Uso
   - Requests completos
   - Responses esperadas
   - Casos de uso reais

**[→ IR PARA PARTE 2](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md)**

---

## 🗂️ **NAVEGAÇÃO RÁPIDA POR TÓPICO**

### 🏗️ **Arquitetura e Conceitos**
- [Visão Geral](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#visão-geral) - Parte 1
- [Arquitetura Completa](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#arquitetura) - Parte 1
- [Fluxo de Dados](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#arquitetura) - Parte 1

### 📦 **Modelos e Database**
- [Todos os Models](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#modelos) - Parte 1
- [Migrations](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#checklist-de-implementação) - Parte 1
- [Indexes e Performance](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#performance) - Parte 1

### 🔧 **Código Core**
- [Utils (Validators, Template Engine)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#services-e-utils) - Parte 1
- [Services (Campaign, Send, Hours)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#services-completos) - Parte 2
- [Worker + RabbitMQ](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#workers-e-rabbitmq-consumers) - Parte 1

### 🌐 **API e Integração**
- [Authentication](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#authentication) - Parte 2
- [Endpoints](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#views) - Parte 2
- [Serializers](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#serializers) - Parte 2
- [Exemplos de Uso](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#exemplos-de-uso) - Parte 2

### 🚨 **Falhas e Recuperação**
- [Instance Health Check](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#tratamento-de-falhas) - Parte 1
- [Retry Logic](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#tratamento-de-falhas) - Parte 1
- [Pause/Resume](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#worker-principal) - Parte 1

### 📊 **Monitoramento e Debug**
- [Observabilidade](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#observabilidade) - Parte 2
- [Troubleshooting](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#troubleshooting) - Parte 2
- [FAQ](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#faq) - Parte 2

### 🚀 **Deploy e Produção**
- [Deploy Railway](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#deploy-no-railway) - Parte 1
- [Variáveis de Ambiente](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#deploy-no-railway) - Parte 1
- [Processos (Procfile)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#deploy-no-railway) - Parte 1

### ✅ **Implementação Passo a Passo**
- [Checklist Completo (8 Fases)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#checklist-de-implementação) - Parte 1
- [Fase 1: Models (2-3 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-1-modelos-e-migrations-2-3-dias)
- [Fase 2: Utils (1-2 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-2-utils-e-helpers-1-2-dias)
- [Fase 3: Services (3-4 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-3-services-3-4-dias)
- [Fase 4: Worker + RabbitMQ (3-4 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-4-worker-e-rabbitmq-3-4-dias)
- [Fase 5: APIs (2-3 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-5-apis-e-serializers-2-3-dias)
- [Fase 6: Chat Integration (1-2 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-6-integração-com-chat-1-2-dias)
- [Fase 7: Testes (2-3 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-7-testes-2-3-dias)
- [Fase 8: Deploy (1-2 dias)](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-8-deploy-e-monitoramento-1-2-dias)

---

## 🎯 **ROTEIRO RECOMENDADO**

### 👨‍💻 **Para Desenvolvedores (Implementação):**
1. **LER PRIMEIRO:** [Regras e Decisões](./BILLING_SYSTEM_RULES.md) - **CRÍTICO!**
2. Ler [Análise de Reutilização](./BILLING_SYSTEM_REUSE_ANALYSIS.md) - O que já existe
3. Ler [Visão Geral](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#visão-geral)
4. Ler [Arquitetura](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#arquitetura)
5. Começar pela [Fase 1: Models](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-1-modelos-e-migrations-2-3-dias)
6. Seguir o [Checklist](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#checklist-de-implementação) sequencialmente
7. Usar [Troubleshooting](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#troubleshooting) quando necessário

### 🏢 **Para Product Owners / Gestores:**
1. Ler [TL;DR](#tldr-resumo-executivo) acima
2. Ver [Exemplos de Uso](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#exemplos-de-uso)
3. Avaliar [Checklist](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#checklist-de-implementação) para timeline

### 🔧 **Para DevOps:**
1. Ver [Deploy no Railway](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#deploy-no-railway)
2. Configurar [Observabilidade](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#observabilidade)
3. Familiarizar com [Troubleshooting](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#troubleshooting)

### 🧪 **Para QA / Testers:**
1. Ver [Exemplos de Uso](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#exemplos-de-uso)
2. Ler [Fase 7: Testes](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md#fase-7-testes-2-3-dias)
3. Usar [FAQ](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md#faq) para teste local

---

## 📊 **RESUMO DE COMPLEXIDADE**

| Componente | Linhas de Código | Complexidade | Tempo Estimado |
|------------|------------------|--------------|----------------|
| **Models** | ~1000 | Média | 2-3 dias |
| **Utils** | ~800 | Baixa | 1-2 dias |
| **Services** | ~1500 | Alta | 3-4 dias |
| **Worker** | ~600 | Alta | 2-3 dias |
| **RabbitMQ** | ~500 | Média | 1-2 dias |
| **APIs** | ~800 | Média | 2-3 dias |
| **Testes** | ~1200 | Média | 2-3 dias |
| **Deploy** | - | Baixa | 1 dia |
| **TOTAL** | ~6400 | - | **15-20 dias** |

---

## ⚠️ **PONTOS CRÍTICOS DE ATENÇÃO**

### 🔴 **CRÍTICO:**
1. **NÃO USE CELERY** - O projeto usa RabbitMQ + aio-pika
2. **SELECT FOR UPDATE** obrigatório na worker batch query
3. **Instance Health Check** antes de CADA envio
4. **Bulk operations** para criar contatos (performance!)

### 🟡 **IMPORTANTE:**
1. Template sanitization (XSS)
2. Phone validation antes de criar contato
3. Rate limiting na API
4. Cache do business hours no worker

### 🟢 **BOM TER:**
1. Prometheus metrics
2. Structured logging
3. Webhook callbacks
4. Frontend dashboard

---

## 🔗 **LINKS ÚTEIS**

- [Evolution API Docs](https://doc.evolution-api.com/)
- [RabbitMQ + aio-pika](https://aio-pika.readthedocs.io/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)

---

## 📝 **CHANGELOG**

### v1.0 (Dezembro 2025)
- ✅ Documentação inicial completa
- ✅ Arquitetura com RabbitMQ (corrigido de Celery)
- ✅ Models completos com indexes
- ✅ Services (Campaign, Send, Scheduler)
- ✅ APIs REST completas
- ✅ Troubleshooting e FAQ
- ✅ Exemplos práticos

---

## 🎯 **PRÓXIMOS PASSOS**

1. **Revisar este índice** para entender a estrutura completa
2. **Ler Parte 1** (Arquitetura + Models + Worker)
3. **Ler Parte 2** (Services + APIs + Observabilidade)
4. **Começar implementação** pela Fase 1 do Checklist
5. **Testar localmente** seguindo o FAQ
6. **Deploy em staging** antes de produção

---

**🚀 Boa implementação!**

