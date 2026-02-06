# Melhorias Identificadas - IA Gateway Teste

## 🔴 Problemas Críticos Encontrados

### 1. **Bug: Variável Duplicada no Frontend**
**Localização:** `frontend/src/pages/ConfigurationsPage.tsx:832 e 854`

**Problema:**
```typescript
const requestData: any = { ... }  // linha 832
// ...
const requestData = data.request || payload.request || null  // linha 854 - SOBRESCREVE!
```

**Impacto:** A variável `requestData` é sobrescrita, perdendo os dados do request original.

**Solução:**
```typescript
const requestPayload: any = { ... }  // renomear
// ...
const requestData = data.request || payload.request || null  // manter nome
```

---

### 2. **Falta Validação de Permissões em `gateway_reply`**
**Localização:** `backend/apps/ai/views.py:467`

**Problema:**
- Endpoint aceita qualquer usuário autenticado (`IsTenantMember`)
- Não valida se usuário tem acesso à conversa específica
- Não valida se usuário pode enviar mensagens (departamento, status da conversa)

**Risco:** Usuário pode enviar mensagens em conversas que não tem acesso.

**Solução:**
```python
from apps.authn.permissions import CanAccessChat

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, CanAccessChat])
def gateway_reply(request):
    # ... validação adicional:
    # - Verificar se conversa pertence ao tenant
    # - Verificar se usuário tem acesso ao departamento da conversa
    # - Verificar se conversa não está bloqueada
```

---

### 3. **Falta Validação de Tamanho Máximo**
**Localização:** `backend/apps/ai/views.py:492`

**Problema:**
- `reply_text` não tem limite de tamanho
- Pode causar problemas no WhatsApp (limite de 4096 caracteres)
- Pode causar problemas de performance no banco

**Solução:**
```python
MAX_REPLY_TEXT_LENGTH = 4096  # Limite do WhatsApp

reply_text = str(request.data.get("reply_text") or "").strip()
if len(reply_text) > MAX_REPLY_TEXT_LENGTH:
    return Response(
        {"error": f"reply_text excede {MAX_REPLY_TEXT_LENGTH} caracteres"},
        status=status.HTTP_400_BAD_REQUEST,
    )
```

---

### 4. **Código Duplicado: Criação de Mensagem**
**Localização:** `backend/apps/ai/views.py:401-450 e 512-580`

**Problema:**
- Lógica de criar mensagem e fazer broadcast está duplicada
- Difícil manter consistência
- Se houver bug, precisa corrigir em 2 lugares

**Solução:**
```python
def _create_and_broadcast_message(conversation, sender, content, is_internal=False):
    """Helper para criar mensagem e fazer broadcast."""
    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=sender,
        content=content,
        direction='outgoing',
        status='pending',
        is_internal=is_internal,
    )
    
    # Broadcast via WebSocket
    _broadcast_message(message)
    
    # Enviar para Evolution API
    from apps.chat.tasks import send_message_to_evolution
    send_message_to_evolution.delay(str(message.id))
    
    return message
```

---

## ⚠️ Problemas de Segurança

### 5. **Falta Rate Limiting**
**Localização:** Ambos endpoints

**Problema:**
- Sem rate limiting, usuário pode fazer spam de testes
- Pode sobrecarregar n8n e banco de dados
- Pode causar custos elevados

**Solução:**
```python
from django.core.cache import cache
from rest_framework.decorators import throttle_classes
from rest_framework.throttling import UserRateThrottle

class GatewayTestThrottle(UserRateThrottle):
    rate = '10/minute'  # 10 testes por minuto

@throttle_classes([GatewayTestThrottle])
@api_view(['POST'])
def gateway_test(request):
    ...
```

---

### 6. **Falta Validação de UUID em `gateway_test`**
**Localização:** `backend/apps/ai/views.py:260`

**Problema:**
```python
conversation_id = _parse_uuid(request.data.get("conversation_id")) or uuid.uuid4()
```

Se `conversation_id` inválido for fornecido, cria UUID aleatório sem avisar o usuário.

**Solução:**
```python
conversation_id_raw = request.data.get("conversation_id")
if conversation_id_raw:
    conversation_id = _parse_uuid(conversation_id_raw)
    if not conversation_id:
        return Response(
            {"error": "conversation_id inválido"},
            status=status.HTTP_400_BAD_REQUEST,
        )
else:
    conversation_id = uuid.uuid4()  # Apenas se não fornecido
```

---

### 7. **Falta Validação de `send_to_chat` sem `reply_text`**
**Localização:** `backend/apps/ai/views.py:391-392`

**Problema:**
```python
send_to_chat = request.data.get("send_to_chat", False)
if send_to_chat and conversation_id:
    # ... tenta criar mensagem mesmo se reply_text estiver vazio
```

**Solução:**
```python
send_to_chat = request.data.get("send_to_chat", False)
if send_to_chat and conversation_id and reply_text:
    # ... criar mensagem
elif send_to_chat and conversation_id and not reply_text:
    logger.warning("send_to_chat habilitado mas reply_text vazio")
```

---

## 🟡 Melhorias de UX

### 8. **Falta Feedback Visual Quando Mensagem é Enviada ao Chat**
**Localização:** `frontend/src/pages/ConfigurationsPage.tsx:874`

**Problema:**
- Usuário não sabe se mensagem foi enviada ao chat
- Não há confirmação visual

**Solução:**
```typescript
// Após sucesso
if (modelTestSendToChat && modelTestConversationId) {
  showSuccessToast('Mensagem enviada ao chat com sucesso!')
}
```

---

### 9. **Falta Validação no Frontend Antes de Enviar**
**Localização:** `frontend/src/pages/ConfigurationsPage.tsx:813`

**Problema:**
- Não valida se `send_to_chat` está marcado sem conversa selecionada
- Não valida se conversa foi selecionada mas checkbox não está marcado

**Solução:**
```typescript
if (modelTestSendToChat && !modelTestConversationId) {
  setModelTestError('Selecione uma conversa para enviar ao chat')
  return
}
```

---

### 10. **Falta Tratamento de Erro Quando Conversa Não Existe**
**Localização:** `backend/apps/ai/views.py:447-450`

**Problema:**
- Erro é logado mas não retornado ao frontend
- Usuário não sabe o que aconteceu

**Solução:**
```python
except Conversation.DoesNotExist:
    logger.warning(f"⚠️ [GATEWAY TEST] Conversa não encontrada: {conversation_id}")
    return Response(
        {
            "status": "error",
            "error_code": "CONVERSATION_NOT_FOUND",
            "error_message": f"Conversa {conversation_id} não encontrada",
            "request_id": str(request_id),
            "trace_id": str(trace_id),
        },
        status=status.HTTP_404_NOT_FOUND,
    )
```

---

## 🟢 Melhorias para Sugestões Futuras

### 11. **Prompt Customizado - Validações Necessárias**

**Problemas a considerar:**
- ❌ Sem limite de tamanho (pode ser muito grande)
- ❌ Sem sanitização (pode conter código malicioso)
- ❌ Sem validação de encoding

**Solução:**
```python
MAX_PROMPT_LENGTH = 10000  # 10KB

custom_prompt = request.data.get("prompt", "").strip()
if custom_prompt:
    if len(custom_prompt) > MAX_PROMPT_LENGTH:
        return Response(
            {"error": f"Prompt excede {MAX_PROMPT_LENGTH} caracteres"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Sanitizar: remover caracteres de controle
    custom_prompt = "".join(char for char in custom_prompt if ord(char) >= 32)
```

---

### 12. **Upload RAG - Validações Necessárias**

**Problemas a considerar:**
- ❌ Sem validação de tipo de arquivo
- ❌ Sem limite de tamanho
- ❌ Processamento síncrono pode travar requisição
- ❌ Sem tratamento de encoding
- ❌ Sem validação de conteúdo malicioso

**Solução:**
```python
ALLOWED_EXTENSIONS = {'.txt', '.md', '.pdf'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def validate_rag_file(file):
    # Validar extensão
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Tipo de arquivo não permitido: {ext}")
    
    # Validar tamanho
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(f"Arquivo muito grande: {file.size} bytes")
    
    # Validar encoding (tentar ler)
    try:
        if ext == '.pdf':
            # Processar PDF
            pass
        else:
            content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        raise ValidationError("Arquivo com encoding inválido")
    
    return content
```

**Processamento Assíncrono:**
```python
# Criar endpoint separado para upload
@api_view(['POST'])
def upload_rag_test_file(request):
    file = request.FILES.get('file')
    # Validar e processar
    # Retornar ID temporário
    # Processar em background (Celery)
```

---

### 13. **Melhorias de Performance**

**Problemas:**
- Carregar 50 conversas pode ser lento
- Não há cache de conversas
- Não há paginação no seletor

**Solução:**
```typescript
// Carregar apenas quando necessário
const [conversationsLoading, setConversationsLoading] = useState(false)

const loadConversations = async () => {
  if (modelTestConversations.length > 0) return // Já carregado
  
  setConversationsLoading(true)
  try {
    const response = await api.get('/chat/conversations/', {
      params: { limit: 20, ordering: '-last_message_at' }
    })
    // ...
  } finally {
    setConversationsLoading(false)
  }
}
```

---

### 14. **Melhorias de Observabilidade**

**Problemas:**
- Falta métricas de uso
- Falta tracking de erros
- Falta alertas para falhas frequentes

**Solução:**
```python
# Adicionar métricas
from apps.common.metrics import increment_counter, record_histogram

increment_counter('ai.gateway.test.requests', tags={'model': model_name})
record_histogram('ai.gateway.test.latency_ms', latency_ms)
```

---

## 📋 Checklist de Implementação

### Prioridade Alta (Crítico)
- [x] Corrigir variável duplicada `requestData` no frontend
- [x] Adicionar validação de permissões em `gateway_reply` (e em `gateway_test` ao enviar ao chat)
- [x] Adicionar validação de tamanho máximo de `reply_text` (4096)
- [x] Extrair função helper `_create_and_broadcast_message` (DRY)

### Prioridade Média (Importante)
- [x] Adicionar rate limiting (`GatewayTestThrottle` 20/min, `GatewayReplyThrottle` 60/min)
- [x] Melhorar validação de UUIDs (`conversation_id` inválido retorna 400)
- [x] Adicionar feedback visual quando mensagem é enviada (toast sucesso/erro + `send_to_chat_result`)
- [x] Melhorar tratamento de erros (404 conversa, 429 throttle, validação send_to_chat no frontend)

### Prioridade Baixa (Melhorias)
- [ ] Adicionar validações para prompt customizado
- [ ] Adicionar validações para upload RAG
- [ ] Melhorar performance do carregamento de conversas
- [ ] Adicionar métricas e observabilidade

---

## 🔍 Pontos de Atenção na Sugestão de Prompt/RAG

### Prompt Customizado
1. ✅ **Onde enviar no payload?**
   - Sugestão: `payload["prompt"]` no nível raiz OU `payload["metadata"]["custom_prompt"]`
   - Preferência: nível raiz para facilitar no n8n

2. ✅ **Como o n8n deve usar?**
   - Se `prompt` existir, usar ao invés do padrão
   - Se não existir, usar prompt padrão do sistema

3. ✅ **Validações necessárias:**
   - Tamanho máximo: 10KB
   - Encoding: UTF-8
   - Sanitização: remover caracteres de controle

### Upload RAG
1. ✅ **Onde processar?**
   - Opção A: Backend processa e envia no payload (mais simples)
   - Opção B: n8n processa arquivo recebido (mais flexível)
   - Preferência: Opção A para testes rápidos

2. ✅ **Como enviar no payload?**
   ```json
   {
     "knowledge_items": [
       {
         "id": "temp-uuid",
         "title": "Documento de teste",
         "content": "...",
         "source": "test_upload"
       }
     ]
   }
   ```

3. ✅ **Armazenamento temporário:**
   - Criar `AiKnowledgeDocument` com `metadata.is_test: true`
   - Deletar após 1 hora (job assíncrono)
   - OU deletar imediatamente após teste

4. ✅ **Validações necessárias:**
   - Tipo de arquivo: `.txt`, `.md`, `.pdf`
   - Tamanho máximo: 5MB
   - Encoding: UTF-8 (para texto)
   - Processamento assíncrono para PDFs grandes

---

## 🎯 Recomendações Finais

1. **Implementar correções críticas primeiro** (bug de variável, validações de segurança)
2. **Adicionar testes unitários** para os endpoints novos
3. **Documentar comportamento esperado** do n8n quando recebe prompt/knowledge_items
4. **Criar endpoint separado para upload RAG** (não misturar com teste)
5. **Adicionar logging estruturado** para facilitar debug
