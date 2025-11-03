# 🔄 REFATORAÇÃO: Fluxo de Recebimento de Anexos

## ✅ OBJETIVO

Padronizar o fluxo de RECEBIMENTO com o fluxo de ENVIO, removendo processamento desnecessário de imagens e padronizando paths S3.

---

## 📝 MUDANÇAS REALIZADAS

### 1. ✅ Removido Processamento de Imagem

**Antes:**
- ✅ Processava imagem (thumbnail, resize, optimize)
- ✅ Fazia upload de thumbnail separado

**Agora:**
- ❌ Remove processamento de imagem (upload direto)
- ❌ Remove upload de thumbnail
- ✅ Mantém apenas conversão de áudio OGG/WEBM → MP3

**Benefícios:**
- Código mais simples
- Processamento mais rápido
- Menor uso de CPU/memória

---

### 2. ✅ Path S3 Padronizado

**Antes:**
```python
s3_path = generate_media_path(tenant_id, f'chat_{media_type}s', filename)
# Resultado: chat_images/{tenant_id}/20250101/{hash}.jpg
```

**Agora:**
```python
s3_path = f"chat/{tenant_id}/attachments/{attachment_id}.{ext}"
# Resultado: chat/{tenant_id}/attachments/{uuid}.jpg
```

**Benefícios:**
- ✅ Estrutura unificada com ENVIO
- ✅ Facilita manutenção e limpeza
- ✅ Mesma organização para ambos os fluxos

---

### 3. ✅ Simplificação de Código

**Removido:**
- ❌ Lógica de processamento de imagem
- ❌ Upload de thumbnail separado
- ❌ Variáveis `thumbnail_data`, `thumb_s3_path`, `thumb_url`

**Mantido:**
- ✅ Download do WhatsApp (com retry)
- ✅ Validação de tamanho
- ✅ Conversão de áudio OGG/WEBM → MP3
- ✅ Upload para S3 (com retry)
- ✅ Cache Redis
- ✅ WebSocket broadcast

---

## 🔄 FLUXO ATUAL (Padronizado)

### RECEBIMENTO:
```
1. Webhook recebe mensagem com media_url (temporária WhatsApp)
   ↓
2. Cria MessageAttachment placeholder (file_url='', metadata={'processing': True})
   ↓
3. Enfileira process_incoming_media (RabbitMQ)
   ↓
4. Worker processa:
   - Baixa do WhatsApp (com retry 3x)
   - Valida tamanho
   - Converte áudio OGG/WEBM → MP3 (se necessário)
   - Upload direto para S3 (sem processar imagem)
   - Path: chat/{tenant_id}/attachments/{uuid}.{ext}
   ↓
5. Atualiza MessageAttachment (remove 'processing' flag)
   ↓
6. Cache Redis (opcional)
   ↓
7. WebSocket broadcast attachment_updated
```

### ENVIO (para comparação):
```
1. Frontend seleciona arquivo
   ↓
2. POST /upload-presigned-url/ → retorna presigned URL
   ↓
3. Frontend faz upload direto para S3
   ↓
4. POST /confirm-upload/ → Backend:
   - Converte áudio OGG/WEBM → MP3 (se necessário)
   - Path: chat/{tenant_id}/attachments/{uuid}.{ext}
   - Cria Message + MessageAttachment
   ↓
5. Enfileira envio para Evolution API
   ↓
6. WebSocket broadcast
```

**✅ Ambos agora usam:**
- Mesmo path S3: `chat/{tenant_id}/attachments/{uuid}.{ext}`
- Mesma conversão de áudio (se necessário)
- Upload direto (sem processar imagem)

---

## 📊 COMPARAÇÃO ANTES/DEPOIS

| Aspecto | ANTES | DEPOIS |
|---------|-------|--------|
| **Path S3** | `chat_images/...` ou `chat_audios/...` | `chat/{tenant}/attachments/...` ✅ |
| **Processamento Imagem** | ✅ Thumbnail + Resize + Optimize | ❌ Removido |
| **Upload Thumbnail** | ✅ Separado | ❌ Removido |
| **Conversão Áudio** | ✅ OGG/WEBM → MP3 | ✅ OGG/WEBM → MP3 |
| **Código** | ~650 linhas | ~500 linhas ✅ |
| **Complexidade** | Alta (processamento) | Baixa (direto) ✅ |

---

## 🧪 TESTES NECESSÁRIOS

- [ ] ✅ Receber imagem do WhatsApp
- [ ] ✅ Receber áudio do WhatsApp
- [ ] ✅ Receber documento do WhatsApp
- [ ] ✅ Verificar path S3 está correto
- [ ] ✅ Verificar WebSocket broadcast funciona
- [ ] ✅ Verificar frontend exibe corretamente (sem thumbnail)

---

## ⚠️ BREAKING CHANGES

### WebSocket `attachment_updated`

**Antes:**
```json
{
  "data": {
    "file_url": "...",
    "thumbnail_url": "...",
    "mime_type": "...",
    ...
  }
}
```

**Agora:**
```json
{
  "data": {
    "file_url": "...",
    "thumbnail_url": null,  // ✅ Sempre null (não geramos mais)
    "mime_type": "...",
    ...
  }
}
```

**Frontend:** Já trata `thumbnail_url` como opcional, então é compatível.

---

## 📚 ARQUIVOS MODIFICADOS

- ✅ `backend/apps/chat/media_tasks.py` - `handle_process_incoming_media()`

---

## ✅ PRÓXIMOS PASSOS

1. ✅ Testar recebimento de imagens
2. ✅ Testar recebimento de áudios
3. ✅ Verificar frontend funciona corretamente
4. ✅ Monitorar logs para erros

