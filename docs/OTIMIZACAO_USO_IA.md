# Otimização do Uso de IA - Análise e Propostas

## 📊 Situação Atual

### Problemas Identificados

1. **Contexto Completo Enviado Toda Vez**
   - A cada chamada da IA, todo o contexto é reconstruído e enviado para N8N
   - Mensagens recentes (até 20) são enviadas completas
   - RAG e memória são buscados e enviados a cada vez
   - Payload pode ser muito grande (vários KB)

2. **Embeddings Não São Cacheados**
   - `embed_text()` é chamado toda vez que precisa de embedding
   - Mensagens já processadas têm seus embeddings recalculados
   - Mesmo texto gera embedding múltiplas vezes

3. **Respostas da IA Não São Salvas**
   - Apenas audit logs são salvos (`AiGatewayAudit`)
   - Respostas completas não são armazenadas
   - Não há histórico de interações IA para análise

4. **Sem Cache de Respostas**
   - Mesmo contexto pode gerar mesma resposta múltiplas vezes
   - Não há verificação de respostas similares anteriores

5. **Contexto Não É Incremental**
   - Sempre envia todas as mensagens recentes
   - Não usa resumos de conversas anteriores
   - Não diferencia contexto novo vs já processado

## 🎯 Propostas de Otimização

### 1. Cache de Embeddings de Mensagens

**Objetivo:** Evitar recalcular embeddings de mensagens já processadas.

**Implementação:**
- Adicionar campo `embedding` na tabela `chat_message` (ou usar tabela separada `message_embeddings`)
- Ao gerar embedding, verificar se já existe antes de chamar N8N
- Cachear por hash do conteúdo da mensagem

**Benefícios:**
- Redução de chamadas ao N8N para embeddings
- Latência menor ao buscar contexto
- Menor custo de processamento

**Arquivos Afetados:**
- `backend/apps/ai/embeddings.py`
- `backend/apps/chat/models.py` (migration)
- `backend/apps/ai/secretary_service.py`
- `backend/apps/ai/triage_service.py`

---

### 2. Cache de Respostas da IA

**Objetivo:** Evitar reprocessar contextos similares que já foram respondidos.

**Implementação:**
- Criar tabela `ai_response_cache`:
  ```python
  class AiResponseCache(models.Model):
      tenant = ForeignKey(Tenant)
      context_hash = CharField(max_length=64, db_index=True)  # SHA256 do contexto normalizado
      agent_type = CharField(max_length=50)  # 'secretary', 'triage', etc
      response_text = TextField()
      metadata = JSONField()  # model, latency, etc
      created_at = DateTimeField(auto_now_add=True)
      expires_at = DateTimeField()
      hit_count = IntegerField(default=0)  # Contador de hits
  ```
- Antes de chamar N8N, calcular hash do contexto normalizado
- Verificar se existe resposta cacheada (similaridade > 0.95)
- Se existir e não expirado, retornar resposta cacheada
- Se não existir, chamar N8N e salvar resposta

**Benefícios:**
- Respostas instantâneas para contextos similares
- Redução drástica de chamadas ao N8N
- Menor latência percebida pelo usuário

**Arquivos Afetados:**
- `backend/apps/ai/models.py` (novo modelo)
- `backend/apps/ai/secretary_service.py`
- `backend/apps/ai/triage_service.py`
- `backend/apps/ai/views.py` (gateway_test)

---

### 3. Histórico Completo de Interações IA

**Objetivo:** Salvar todas as interações IA para análise, debugging e melhoria contínua.

**Implementação:**
- Expandir `AiGatewayAudit` ou criar `AiInteraction`:
  ```python
  class AiInteraction(models.Model):
      tenant = ForeignKey(Tenant)
      conversation_id = UUIDField(null=True)
      message_id = UUIDField(null=True)
      agent_type = CharField(max_length=50)  # 'secretary', 'triage', 'gateway'
      request_payload = JSONField()  # Payload completo enviado
      response_payload = JSONField()  # Resposta completa recebida
      context_hash = CharField(max_length=64)  # Hash do contexto
      model_name = CharField(max_length=100)
      latency_ms = IntegerField()
      tokens_input = IntegerField(null=True)  # Se disponível
      tokens_output = IntegerField(null=True)  # Se disponível
      cost_estimate = DecimalField(null=True)  # Estimativa de custo
      cache_hit = BooleanField(default=False)  # Se foi cache hit
      created_at = DateTimeField(auto_now_add=True)
  ```
- Salvar antes e depois de cada chamada IA
- Permitir análise de padrões, custos, performance

**Benefícios:**
- Visibilidade completa do uso de IA
- Análise de custos e performance
- Debugging facilitado
- Dados para treinamento/fine-tuning

**Arquivos Afetados:**
- `backend/apps/ai/models.py` (novo modelo)
- `backend/apps/ai/secretary_service.py`
- `backend/apps/ai/triage_service.py`
- `backend/apps/ai/views.py`

---

### 4. Resumos de Conversas

**Objetivo:** Reduzir tamanho do contexto enviado usando resumos ao invés de todas as mensagens.

**Implementação:**
- Criar tabela `conversation_summary`:
  ```python
  class ConversationSummary(models.Model):
      conversation = OneToOneField(Conversation)
      summary_text = TextField()  # Resumo gerado pela IA
      message_count = IntegerField()  # Quantas mensagens foram resumidas
      last_message_id = UUIDField()  # Última mensagem incluída no resumo
      embedding = JSONField(null=True)  # Embedding do resumo
      created_at = DateTimeField(auto_now_add=True)
      updated_at = DateTimeField(auto_now=True)
  ```
- Ao construir contexto:
  - Se conversa tem > 50 mensagens, usar resumo + últimas 10 mensagens
  - Gerar resumo periodicamente (ex: a cada 20 mensagens novas)
  - Usar resumo no contexto ao invés de todas as mensagens antigas

**Benefícios:**
- Payload muito menor
- Contexto mais relevante (resumo + recente)
- Menor latência de processamento

**Arquivos Afetados:**
- `backend/apps/chat/models.py` (novo modelo)
- `backend/apps/ai/secretary_service.py` (`_build_secretary_context`)
- `backend/apps/ai/triage_service.py` (`_build_context`)
- Nova task para gerar resumos periodicamente

---

### 5. Contexto Incremental

**Objetivo:** Enviar apenas novas informações ao invés de reconstruir tudo.

**Implementação:**
- Rastrear última mensagem processada por agente IA em cada conversa:
  ```python
  class ConversationAiState(models.Model):
      conversation = OneToOneField(Conversation)
      last_secretary_message_id = UUIDField(null=True)
      last_triage_message_id = UUIDField(null=True)
      last_summary_at = DateTimeField(null=True)
      updated_at = DateTimeField(auto_now=True)
  ```
- Ao construir contexto:
  - Buscar apenas mensagens após `last_secretary_message_id`
  - Combinar com resumo existente (se houver)
  - Atualizar `last_secretary_message_id` após processar

**Benefícios:**
- Payload mínimo necessário
- Processamento mais rápido
- Menor custo de API

**Arquivos Afetados:**
- `backend/apps/chat/models.py` (novo modelo)
- `backend/apps/ai/secretary_service.py`
- `backend/apps/ai/triage_service.py`

---

### 6. Cache de Busca RAG

**Objetivo:** Cachear resultados de busca RAG para queries similares.

**Implementação:**
- Usar Redis ou tabela de cache:
  ```python
  class AiRagCache(models.Model):
      tenant = ForeignKey(Tenant)
      query_hash = CharField(max_length=64, db_index=True)  # Hash da query
      query_embedding = JSONField()  # Embedding da query
      results = JSONField()  # Resultados da busca
      created_at = DateTimeField(auto_now_add=True)
      expires_at = DateTimeField()
  ```
- Antes de buscar RAG, verificar cache
- Se cache hit e não expirado, retornar resultados cacheados
- TTL: 1 hora (RAG muda pouco)

**Benefícios:**
- Menos queries ao banco
- Latência menor
- Menor carga no pgvector

**Arquivos Afetados:**
- `backend/apps/ai/models.py` (novo modelo ou usar Redis)
- `backend/apps/ai/vector_store.py`

---

## 📋 Plano de Implementação

### Fase 1: Cache de Embeddings (Prioridade Alta)
- [ ] Migration: adicionar campo `embedding` em `Message` ou criar `MessageEmbedding`
- [ ] Modificar `embed_text()` para verificar cache antes de gerar
- [ ] Salvar embedding após gerar
- [ ] Atualizar `secretary_service` e `triage_service` para usar cache

**Impacto Esperado:** Redução de 60-80% nas chamadas de embedding

---

### Fase 2: Cache de Respostas (Prioridade Alta)
- [ ] Migration: criar tabela `AiResponseCache`
- [ ] Função para calcular hash de contexto normalizado
- [ ] Verificar cache antes de chamar N8N
- [ ] Salvar resposta após chamar N8N
- [ ] TTL configurável (padrão: 1 hora)

**Impacto Esperado:** Redução de 30-50% nas chamadas ao N8N

---

### Fase 3: Histórico Completo (Prioridade Média)
- [ ] Migration: criar tabela `AiInteraction`
- [ ] Salvar todas as interações (request + response)
- [ ] Endpoint para visualizar histórico
- [ ] Dashboard de métricas (custo, latência, cache hit rate)

**Impacto Esperado:** Visibilidade completa + dados para otimização

---

### Fase 4: Resumos de Conversas (Prioridade Média)
- [ ] Migration: criar tabela `ConversationSummary`
- [ ] Task periódica para gerar resumos
- [ ] Modificar `_build_context` para usar resumos
- [ ] Configurar quando gerar resumo (ex: a cada 20 mensagens)

**Impacto Esperado:** Redução de 40-60% no tamanho do payload

---

### Fase 5: Contexto Incremental (Prioridade Baixa)
- [ ] Migration: criar tabela `ConversationAiState`
- [ ] Rastrear última mensagem processada
- [ ] Modificar construção de contexto para ser incremental
- [ ] Atualizar estado após processar

**Impacto Esperado:** Redução adicional de 20-30% no payload

---

### Fase 6: Cache de RAG (Prioridade Baixa)
- [ ] Implementar cache de resultados RAG (Redis ou tabela)
- [ ] Verificar cache antes de buscar no pgvector
- [ ] TTL: 1 hora

**Impacto Esperado:** Redução de 50-70% nas queries RAG

---

## 🔧 Configurações Recomendadas

```python
# settings.py
AI_CACHE_ENABLED = True
AI_RESPONSE_CACHE_TTL = 3600  # 1 hora
AI_EMBEDDING_CACHE_ENABLED = True
AI_RAG_CACHE_TTL = 3600  # 1 hora
AI_SUMMARY_ENABLED = True
AI_SUMMARY_MESSAGE_THRESHOLD = 50  # Gerar resumo após 50 mensagens
AI_SUMMARY_UPDATE_INTERVAL = 20  # Atualizar resumo a cada 20 mensagens novas
AI_INTERACTION_LOGGING_ENABLED = True
```

---

## 📊 Métricas de Sucesso

- **Redução de chamadas ao N8N:** Meta: 50-70%
- **Redução de latência média:** Meta: 30-50%
- **Redução de custo de API:** Meta: 40-60%
- **Cache hit rate:** Meta: > 60%
- **Tamanho médio do payload:** Meta: Redução de 50%

---

## 🚨 Considerações Importantes

1. **Isolamento Multi-tenant:** Todos os caches devem ser isolados por tenant
2. **Expiração:** Caches devem expirar para não ficar desatualizados
3. **Invalidação:** Cache deve ser invalidado quando dados mudam (ex: novo conhecimento RAG)
4. **LGPD:** Respostas cacheadas podem conter dados pessoais - considerar retenção
5. **Performance:** Índices adequados em todas as tabelas de cache
6. **Monitoramento:** Logs e métricas para acompanhar eficácia dos caches

---

## 📝 Próximos Passos

1. Revisar este documento com o time
2. Priorizar fases de implementação
3. Criar issues/tasks para cada fase
4. Implementar Fase 1 (Cache de Embeddings)
5. Medir impacto e ajustar

---

**Autor:** Análise realizada em 10/02/2026  
**Status:** Proposta - Aguardando aprovação
