# 📋 ANÁLISE: Implementação de Recebimento de Stickers (WhatsApp)

> **Data:** 2025-12-10  
> **Objetivo:** Documentar como implementar recebimento de stickers do WhatsApp via Evolution API  
> **Status:** Análise - SEM CODIFICAÇÃO

---

## 🎯 VISÃO GERAL

### O que são Stickers no WhatsApp?

Stickers são imagens animadas ou estáticas (geralmente 512x512 pixels) que podem ser enviadas no WhatsApp. Eles são diferentes de imagens normais porque:
- Têm formato específico (geralmente WebP animado ou PNG estático)
- São tratados como um tipo especial de mensagem pela Evolution API
- Podem ter animação (WebP animado)
- Têm metadados específicos (pack, id, etc)

### Tipos de Stickers

1. **Stickers Estáticos** (PNG)
   - Formato: PNG com fundo transparente
   - Tamanho: 512x512 pixels
   - Sem animação

2. **Stickers Animados** (WebP)
   - Formato: WebP animado
   - Tamanho: 512x512 pixels
   - Com animação

---

## 🔍 ANÁLISE DO CÓDIGO ATUAL

### Como o Sistema Processa Mensagens Atualmente

**Arquivo:** `backend/apps/chat/webhooks.py`

O sistema já processa vários tipos de mensagem:

```python
# Tipos suportados atualmente:
- 'text' → Mensagem de texto
- 'imageMessage' → Imagem
- 'videoMessage' → Vídeo
- 'audioMessage' → Áudio
- 'documentMessage' → Documento
- 'contactMessage' → Contato compartilhado
- 'locationMessage' → Localização
- 'reactionMessage' → Reação (emoji)
```

**Fluxo atual:**
1. Webhook recebe evento `messages.upsert` da Evolution API
2. Extrai `messageType` do payload
3. Processa conforme o tipo (linha ~820)
4. Para mídia: envia para fila RabbitMQ para download assíncrono

### Onde Adicionar Suporte a Stickers

**Localização:** `backend/apps/chat/webhooks.py` - função `handle_message_upsert()`

**Linha aproximada:** ~1336 (após `audioMessage`)

---

## 📦 ESTRUTURA DO PAYLOAD DA EVOLUTION API

### Como a Evolution API Envia Stickers

Baseado na documentação da Evolution API, stickers vêm como:

```json
{
  "event": "messages.upsert",
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "id": "message_id_here"
    },
    "message": {
      "stickerMessage": {
        "url": "https://mmg.whatsapp.net/...",
        "mimetype": "image/webp",
        "fileLength": 12345,
        "width": 512,
        "height": 512,
        "mediaKey": "...",
        "stickerSentTs": 1234567890,
        "isAnimated": true,
        "isFirstFrame": false,
        "firstFrameSidecar": "...",
        "firstFrameLength": 1234,
        "animatedSidecar": "...",
        "animatedSidecarLength": 12345,
        "stickerPackId": "pack_id",
        "stickerId": "sticker_id"
      }
    },
    "messageType": "stickerMessage",
    "messageTimestamp": 1234567890
  }
}
```

### Campos Importantes

- **`stickerMessage.url`**: URL temporária para download (similar a imagens)
- **`stickerMessage.mimetype`**: Geralmente `image/webp` (animado) ou `image/png` (estático)
- **`stickerMessage.isAnimated`**: Boolean indicando se é animado
- **`stickerMessage.width/height`**: Dimensões (geralmente 512x512)
- **`stickerMessage.stickerPackId`**: ID do pacote de stickers
- **`stickerMessage.stickerId`**: ID único do sticker

---

## 🛠️ O QUE PRECISA SER IMPLEMENTADO

### 1. Detecção do Tipo de Mensagem

**Onde:** `backend/apps/chat/webhooks.py` - função `handle_message_upsert()`

**Ação:**
- Adicionar verificação para `message_type == 'stickerMessage'`
- Similar ao que já existe para `imageMessage`, `videoMessage`, etc.

**Código de referência (linha ~1274):**
```python
elif message_type == 'imageMessage':
    image_msg = message_info.get('imageMessage', {})
    content = image_msg.get('caption', '')
    # ... processamento
```

### 2. Extração dos Dados do Sticker

**Onde:** Mesmo local acima

**Dados a extrair:**
- URL de download (`stickerMessage.url`)
- MIME type (`stickerMessage.mimetype`)
- Tamanho do arquivo (`stickerMessage.fileLength`)
- Dimensões (`stickerMessage.width`, `stickerMessage.height`)
- Se é animado (`stickerMessage.isAnimated`)
- Pack ID e Sticker ID (opcional, para organização)

### 3. Processamento Assíncrono

**Onde:** `backend/apps/chat/media_tasks.py` ou `backend/apps/chat/tasks.py`

**Ação:**
- Criar handler similar a `process_incoming_media`
- Stickers devem ser processados como imagens (mesmo fluxo)
- Download → Upload S3 → Criar MessageAttachment

**Considerações:**
- Stickers animados (WebP) podem ser maiores
- Não precisa de thumbnail (já são pequenos - 512x512)
- Manter formato original (WebP ou PNG)

### 4. Modelo MessageAttachment

**Onde:** `backend/apps/chat/models.py`

**Status:** ✅ Já suporta qualquer tipo de mídia

**Campos relevantes:**
- `file_type`: Adicionar opção `'sticker'`
- `mime_type`: Já existe (suporta `image/webp`, `image/png`)
- `is_image`: Stickers podem ser considerados imagens
- `is_animated`: Novo campo? Ou usar metadata?

**Decisão necessária:**
- Adicionar campo `is_sticker` boolean?
- Ou usar `file_type = 'sticker'`?
- Ou usar `metadata` para armazenar `isAnimated`, `packId`, etc?

### 5. Frontend - Exibição

**Onde:** Frontend React (componentes de mensagem)

**Ação:**
- Criar componente para exibir stickers
- Suportar WebP animado (navegadores modernos)
- Fallback para primeira frame se não suportar animação
- Mostrar indicador visual de "sticker" (opcional)

**Considerações:**
- WebP animado requer suporte do navegador
- Usar `<img>` tag com `src` direto (não precisa player especial)
- Tamanho fixo: 512x512 pixels (ou escalar proporcionalmente)

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

### Backend

- [ ] **1. Detecção no Webhook**
  - [ ] Adicionar `elif message_type == 'stickerMessage'` em `handle_message_upsert()`
  - [ ] Extrair dados do `stickerMessage`
  - [ ] Extrair `quotedMessage` se houver (resposta)
  - [ ] Processar menções se houver (contextInfo.mentionedJid)

- [ ] **2. Modelo MessageAttachment**
  - [ ] Decidir: adicionar campo `is_sticker` ou usar `file_type`?
  - [ ] Adicionar `'sticker'` em `FILE_TYPE_CHOICES` (se usar enum)
  - [ ] Adicionar campos em `metadata` para `isAnimated`, `packId`, `stickerId` (opcional)

- [ ] **3. Processamento Assíncrono**
  - [ ] Criar handler `process_incoming_sticker()` em `media_tasks.py`
  - [ ] Ou adaptar `process_incoming_media()` para suportar stickers
  - [ ] Download do WhatsApp (URL temporária)
  - [ ] Upload para S3
  - [ ] Criar MessageAttachment com tipo correto
  - [ ] Não gerar thumbnail (stickers já são pequenos)

- [ ] **4. Serializer**
  - [ ] Atualizar `MessageSerializer` para incluir stickers
  - [ ] Adicionar campo `is_sticker` ou `file_type` na resposta
  - [ ] Incluir metadados do sticker (isAnimated, packId, etc)

### Frontend

- [ ] **5. Componente de Exibição**
  - [ ] Criar componente `StickerMessage.tsx`
  - [ ] Suportar WebP animado
  - [ ] Fallback para primeira frame se não suportar
  - [ ] Estilização (tamanho fixo ou responsivo)

- [ ] **6. Integração no Chat**
  - [ ] Adicionar renderização de stickers em `MessageList`
  - [ ] Detectar tipo de mensagem e renderizar componente correto
  - [ ] Testar com stickers animados e estáticos

### Testes

- [ ] **7. Testes Backend**
  - [ ] Teste unitário: processamento de sticker estático
  - [ ] Teste unitário: processamento de sticker animado
  - [ ] Teste de integração: webhook completo com sticker
  - [ ] Teste de download e upload S3

- [ ] **8. Testes Frontend**
  - [ ] Teste visual: exibição de sticker estático
  - [ ] Teste visual: exibição de sticker animado
  - [ ] Teste de fallback em navegadores antigos

---

## 🔄 FLUXO COMPLETO

### Recebimento de Sticker

```
1. WhatsApp → Evolution API
   └─ Usuário envia sticker

2. Evolution API → Webhook Django
   └─ POST /webhook/evolution/
   └─ Event: messages.upsert
   └─ messageType: "stickerMessage"

3. Django Webhook Handler
   └─ Detecta message_type == 'stickerMessage'
   └─ Extrai dados do stickerMessage
   └─ Cria Message (sem attachment ainda)
   └─ Envia para fila RabbitMQ: process_incoming_sticker

4. RabbitMQ Consumer
   └─ Recebe task: process_incoming_sticker
   └─ Download do sticker do WhatsApp (URL temporária)
   └─ Upload para S3 (MinIO)
   └─ Cria MessageAttachment:
      - file_type: 'sticker'
      - mime_type: 'image/webp' ou 'image/png'
      - file_url: URL do S3
      - metadata: { isAnimated: true, packId: '...', stickerId: '...' }

5. WebSocket Broadcast
   └─ Notifica frontend sobre nova mensagem
   └─ Frontend renderiza sticker
```

---

## 🎨 CONSIDERAÇÕES DE UX/UI

### Exibição no Chat

**Tamanho recomendado:**
- Stickers devem aparecer em tamanho fixo: **200x200px** ou **256x256px**
- Manter proporção 1:1 (quadrado)
- Não distorcer imagem

**Indicadores visuais:**
- Opcional: badge "Sticker" ou ícone
- Opcional: indicador de animação (gif icon)
- Opcional: mostrar pack name (se disponível)

**Interações:**
- Click para ampliar (modal)
- Download (opcional)
- Compartilhar (opcional)

---

## ⚠️ PONTOS DE ATENÇÃO

### 1. Formato WebP Animado

- Navegadores antigos podem não suportar WebP animado
- **Solução:** Usar primeira frame como fallback
- Campo `firstFrameSidecar` no payload pode ajudar

### 2. Tamanho dos Arquivos

- Stickers animados podem ser maiores que estáticos
- **Limite recomendado:** 1MB por sticker
- Validar tamanho antes de processar

### 3. Cache

- Stickers são reutilizados frequentemente
- **Otimização:** Cache agressivo (30 dias)
- Usar `media_hash` para detectar duplicatas

### 4. Performance

- Stickers animados podem ser pesados
- **Otimização:** Lazy loading no frontend
- Carregar apenas quando visível na tela

---

## 📚 REFERÊNCIAS

### Evolution API

- Documentação oficial: [Evolution API Docs](https://doc.evolution-api.com/)
- Webhook events: `messages.upsert`
- Message types: `stickerMessage`

### Formatos

- **WebP Animado:** [WebP Specification](https://developers.google.com/speed/webp)
- **PNG:** Formato padrão para stickers estáticos

### WhatsApp

- Stickers devem ter 512x512 pixels
- Formato: PNG (estático) ou WebP (animado)
- Fundo transparente recomendado

---

## ✅ CONCLUSÃO

### Resumo

Para implementar recebimento de stickers:

1. **Backend:**
   - Adicionar detecção de `stickerMessage` no webhook
   - Criar handler de processamento assíncrono
   - Adaptar modelo `MessageAttachment` (se necessário)

2. **Frontend:**
   - Criar componente de exibição
   - Suportar WebP animado com fallback
   - Integrar no fluxo de mensagens

3. **Testes:**
   - Testar com stickers estáticos e animados
   - Validar em diferentes navegadores
   - Testar performance e cache

### Complexidade

- **Backend:** Média (similar a imagens, mas com algumas particularidades)
- **Frontend:** Baixa (renderização simples de imagem)
- **Testes:** Média (precisa testar animação e fallbacks)

### Tempo Estimado

- **Backend:** 4-6 horas
- **Frontend:** 2-3 horas
- **Testes:** 2-3 horas
- **Total:** 8-12 horas

---

**Próximos Passos:**
1. Revisar esta análise
2. Decidir sobre estrutura de dados (campos do modelo)
3. Implementar backend primeiro
4. Implementar frontend
5. Testar e ajustar

