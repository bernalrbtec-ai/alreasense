# 📚 DOCUMENTAÇÃO CONSOLIDADA - ALREA SENSE

## 🎯 ÍNDICE

1. [Início Rápido](#início-rápido)
2. [Arquitetura](#arquitetura)
3. [Performance](#performance)
4. [Integrações](#integrações)
5. [Segurança](#segurança)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 INÍCIO RÁPIDO

### **Stack Tecnológica**
- **Backend:** Django 5 + DRF + Channels + RabbitMQ
- **Frontend:** React 18 + TypeScript + Vite + Zustand
- **Database:** PostgreSQL 15 + pgvector
- **Cache:** Redis 7
- **Storage:** MinIO/S3 (Railway)
- **Queue:** RabbitMQ (NÃO Celery!)

### **Regras Críticas**
- ✅ **NÃO USE CELERY** - O projeto usa RabbitMQ + aio-pika
- ✅ **SEMPRE TESTE ANTES DE COMMIT** - Crie scripts de teste locais
- ✅ **MULTI-TENANT FIRST** - Todo modelo precisa de `tenant_id`
- ✅ **WEBSOCKET PARA REAL-TIME** - Use Channels, não polling
- ✅ **SEMPRE verifique migrations existentes** antes de criar novas

Ver `rules.md` para regras completas.

---

## 🏗️ ARQUITETURA

### **Produtos Ativos**
- **Flow** - Campanhas + Chat + Contatos
- **Sense** - IA (legado)
- **Notifications** - Sistema de notificações
- **API Pública** - Integrações externas

### **Sistema de Mídia**
- Base64 prioritário (mais confiável)
- Fallback para URL descriptografada
- Processamento assíncrono via RabbitMQ
- Storage S3/MinIO com proxy interno

**Documentação completa:** `IMPLEMENTACAO_SISTEMA_MIDIA.md`

---

## ⚡ PERFORMANCE

### **Otimizações Implementadas (Nov/2025)**

#### **Backend:**
1. ✅ **unread_count** - Calculado em batch (evita N+1 queries)
2. ✅ **get_last_message** - Prefetch_related (evita N+1 queries)
3. ✅ **Paginação de mensagens** - 50 por requisição
4. ✅ **Cache** - instance_friendly_name (5 min), contact_tags (10 min)
5. ✅ **S3 URLs** - Cache de URLs geradas (10 min)

#### **Frontend:**
1. ✅ **Paginação de mensagens** - Lazy loading (50 por vez)
2. ✅ **Lazy loading** - Botão "Carregar mensagens antigas"
3. ✅ **Memoização** - useMemo e useCallback para evitar re-renders
4. ✅ **Fade-in otimizado** - Delay reduzido, limitado a 50 mensagens

**Impacto:** 10-25x mais rápido (de ~300 queries para ~5 queries em 100 conversas)

**Documentação completa:** `OTIMIZACOES_PERFORMANCE_CHAT.md`

---

## 🔌 INTEGRAÇÕES

### **Evolution API**

**Webhooks (Atual - Recomendado):**
- ✅ Simples e confiável
- ✅ Padrão da indústria (HTTP POST)
- ✅ Fácil de debugar
- ✅ Idempotência via cache
- ✅ Processamento assíncrono (RabbitMQ)

**WebSocket (Opcional):**
- Disponível via Evolution API (socket.io)
- Modo Global ou Tradicional
- Requer `python-socketio`
- Mais complexo, use apenas se necessário

**Recomendação:** Manter webhooks (já funciona bem)

**Documentação completa:** `ANALISE_WEBSOCKET_EVOLUTION.md`

### **RabbitMQ**
- URL: `RABBITMQ_URL` (Railway)
- Usado para: Processamento assíncrono de mídia, mensagens
- NÃO usar Celery (projeto usa aio-pika)

---

## 🔐 SEGURANÇA

### **Regras Críticas**
1. ❌ **NUNCA** hardcode credenciais no código
2. ✅ **SEMPRE** use variáveis de ambiente
3. ✅ **SEMPRE** mascare secrets em respostas de API
4. ✅ **SEMPRE** restrinja CORS
5. ✅ **SEMPRE** use pre-commit hooks
6. ✅ **SEMPRE** logue acessos sensíveis
7. ✅ **SEMPRE** implemente rate limiting

### **Pre-commit Hooks**
- Detecta credenciais antes do commit
- Bloqueia secrets automaticamente
- Verifica debug prints

### **API Key Masking**
- Keys sempre mascaradas em GET
- Flag `api_key_set` indica se configurada
- Aceita update mas nunca retorna completa

---

## 🐛 TROUBLESHOOTING

### **Migrations**
**Problema:** Migrations conflitantes
**Solução:** Sempre verificar migrations existentes antes de criar novas
```bash
ls backend/apps/[app]/migrations/
python manage.py showmigrations [app]
```

### **RabbitMQ**
**Problema:** Conexão falha
**Solução:** Verificar variável `RABBITMQ_URL` (não `RABBITMQ_PRIVATE_URL`)

### **Performance**
**Problema:** Queries lentas
**Solução:** Verificar se está usando `select_related`/`prefetch_related`
- ✅ Use `annotate()` para contagens em batch
- ✅ Use `Prefetch()` para última mensagem
- ✅ Implemente paginação

### **Mídia**
**Problema:** Arquivos não aparecem
**Solução:** 
1. Verificar se processo RabbitMQ está rodando
2. Verificar logs de `media_tasks.py`
3. Verificar se S3 está configurado corretamente

---

## 📝 DOCUMENTAÇÃO DETALHADA

### **Arquivos Essenciais:**
- `rules.md` - Regras de desenvolvimento e arquitetura
- `IMPLEMENTACAO_SISTEMA_MIDIA.md` - Sistema de mídia completo
- `ANALISE_COMPLETA_PROJETO_2025.md` - Análise arquitetural
- `OTIMIZACOES_PERFORMANCE_CHAT.md` - Otimizações de performance
- `ANALISE_WEBSOCKET_EVOLUTION.md` - WebSocket vs Webhooks

### **Outros Documentos:**
- `PROXIMAS_FEATURES_CHAT.md` - Features planejadas
- `GUIA_RAPIDO_CAMPANHAS_EMAIL.md` - Campanhas de email

---

## 🔄 CHANGELOG

### **Nov/2025 - Otimizações de Performance**
- ✅ Otimização de N+1 queries (unread_count, last_message)
- ✅ Paginação de mensagens (50 por requisição)
- ✅ Cache de conversas e tags
- ✅ Memoização de componentes React
- ✅ Lazy loading de mensagens antigas

### **Out/2025 - Correções e Melhorias**
- ✅ Sistema de mídia refatorado (Base64 prioritário)
- ✅ Departamentos padrão para instâncias
- ✅ Mensagens de transferência customizadas
- ✅ Correção de grupos WhatsApp (LID)
- ✅ Sistema de anexos otimizado

---

## 📞 SUPORTE

Para dúvidas ou problemas:
1. Verificar `rules.md` para regras do projeto
2. Verificar logs no Railway
3. Consultar documentação específica acima
4. Verificar se há migrations pendentes

---

**Última atualização:** Nov/2025

