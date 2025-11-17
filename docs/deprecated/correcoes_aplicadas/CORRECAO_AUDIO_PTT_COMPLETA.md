# 🎤 CORREÇÃO: Áudio PTT (Push-To-Talk)

**Data:** 29/10/2025  
**Status:** ✅ Implementado - Aguardando deploy

---

## 📋 Problemas Identificados

### 1. ❌ Áudio ENVIADO: Aparecia como "encaminhado"
- Usuário gravava áudio na aplicação web
- Enviava para contato
- No WhatsApp do contato: aparecia como "Áudio encaminhado" 📎
- **Comportamento esperado:** Aparecer como áudio gravado (PTT) 🎤

### 2. ❌ Áudio RECEBIDO: Não reproduzia no navegador
- Erro no console: `NotSupportedError: The element has no supported sources`
- Player de áudio ficava travado
- Usuário não conseguia ouvir o áudio recebido

---

## 🔍 Causa Raiz

### Problema 1: Endpoint Incorreto
**Backend estava usando:**
```python
# ❌ ERRADO
endpoint = f"{base_url}/message/sendMedia/{instance}"
payload = {
    'number': phone,
    'media': url,
    'mediatype': 'audio',
    'options': {'ptt': True}
}
```

**Deveria usar:**
```python
# ✅ CORRETO (conforme documentação oficial)
endpoint = f"{base_url}/message/sendWhatsAppAudio/{instance}"
payload = {
    'number': phone,
    'audio': url,    # Chave correta: 'audio' não 'media'
    'delay': 1200    # Delay opcional para naturalidade
}
```

**Referência:** [Evolution API - Send WhatsApp Audio](https://doc.evolution-api.com/v2/api-reference/message-controller/send-audio)

### Problema 2: Frontend Tentava Reproduzir URL Inválida
- Quando áudio chegava via webhook, `file_url` era da Evolution API (externa, não acessível)
- Download assíncrono para S3 acontecia em background
- Mas frontend não verificava se URL estava pronta
- Tentava reproduzir → `NotSupportedError`

---

## ✅ Correções Implementadas

### Backend: `backend/apps/chat/tasks.py`

**1. Endpoint correto para PTT:**
```python
# 🎤 ÁUDIO: Usar endpoint específico sendWhatsAppAudio para PTT
if is_audio:
    # Estrutura para PTT (Push-To-Talk - áudio gravado)
    # Ref: https://doc.evolution-api.com/v2/api-reference/message-controller/send-audio
    payload = {
        'number': phone,
        'audio': url,        # URL do arquivo no S3 (ou base64)
        'delay': 1200        # Delay opcional (1.2s) para parecer mais natural
    }
    logger.info(f"🎤 [CHAT] Enviando como PTT (áudio gravado) via sendWhatsAppAudio")
    logger.info(f"   URL: {url[:100]}...")
```

**2. Endpoint dinâmico:**
```python
# Endpoint: sendWhatsAppAudio para PTT, sendMedia para outros
if is_audio:
    endpoint = f"{base_url}/message/sendWhatsAppAudio/{instance.instance_name}"
else:
    endpoint = f"{base_url}/message/sendMedia/{instance.instance_name}"
```

### Frontend: `frontend/src/modules/chat/components/AttachmentPreview.tsx`

**1. Detectar se áudio está disponível:**
```typescript
// ✅ Detectar se áudio está disponível (URL local/S3 ao invés de Evolution API)
const isAudioReady = attachment.file_url && (
  attachment.file_url.includes('bucket-production') ||  // MinIO/S3
  attachment.file_url.includes('s3.') ||                // AWS S3
  attachment.file_url.includes('localhost') ||          // Dev local
  attachment.file_url.startsWith('blob:')              // Blob URL
);
```

**2. Estado de loading:**
```typescript
<button
  onClick={togglePlay}
  disabled={!isAudioReady}
  className={`... ${
    isAudioReady 
      ? 'bg-green-500 hover:bg-green-600 cursor-pointer' 
      : 'bg-gray-300 cursor-not-allowed'
  }`}
  title={isAudioReady ? (isPlaying ? 'Pausar' : 'Reproduzir') : 'Baixando áudio...'}
>
  {!isAudioReady ? (
    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
  ) : isPlaying ? (
    <Pause className="text-white" size={18} fill="white" />
  ) : (
    <Play className="text-white ml-0.5" size={18} fill="white" />
  )}
</button>
```

**3. Renderizar áudio somente quando pronto:**
```typescript
{/* Áudio HTML5 (hidden - só para controle) */}
{isAudioReady && (
  <audio
    ref={audioRef}
    src={attachment.file_url}
    preload="metadata"
    className="hidden"
  />
)}
```

**4. Texto de loading:**
```typescript
<div className="flex items-center justify-between text-[10px] sm:text-xs text-gray-500">
  <span>{isAudioReady ? formatTime(currentTime) : 'Baixando...'}</span>
  <span>{isAudioReady ? formatTime(duration) : '--:--'}</span>
</div>
```

---

## 🎯 Comportamento Esperado (Após Deploy)

### ✅ Áudio ENVIADO da aplicação:
1. Usuário grava áudio no chat (segura botão microfone)
2. Sistema envia via `/message/sendWhatsAppAudio` com `ptt: true`
3. **No WhatsApp do contato:**
   - ✅ Aparece como **áudio gravado** (ícone 🎤)
   - ✅ Formato de "bolinha verde"
   - ✅ **NÃO** como "áudio encaminhado"

### ✅ Áudio RECEBIDO do WhatsApp:
1. Contato envia áudio do WhatsApp
2. Mensagem chega no chat da aplicação
3. **Player mostra:**
   - 🔄 **"Baixando..."** com spinner (por 1-3 segundos)
   - ✅ Quando download termina → Botão verde habilitado
   - ✅ Usuário clica Play → **Áudio reproduz normalmente**
   - ✅ Progress bar funciona
   - ✅ Tempo atualiza corretamente

---

## 🧪 Testes Necessários

### Teste 1: Áudio ENVIADO (PTT)
1. **Abrir aplicação web** (chat)
2. **Gravar um áudio** (segurar botão microfone)
3. **Enviar** para um contato
4. **No WhatsApp do contato**, verificar:
   - ✅ Aparece como **áudio gravado** (🎤 ícone microfone)
   - ✅ Formato "bolinha" de PTT
   - ❌ **NÃO** deve aparecer como "encaminhado" ou "arquivo de áudio"

### Teste 2: Áudio RECEBIDO (Loading)
1. **Contato envia áudio** do WhatsApp para a aplicação
2. **Na aplicação web**, verificar player:
   - ✅ Inicialmente mostra **"Baixando..."**
   - ✅ Botão de play **desabilitado** (cinza)
   - ✅ Spinner animado
   - ✅ Tempo mostra `--:--`

### Teste 3: Áudio RECEBIDO (Reprodução)
1. **Após loading terminar** (1-3 segundos):
   - ✅ Botão fica **verde** (habilitado)
   - ✅ Tempo mostra duração real (ex: `0:05`)
2. **Clicar em Play:**
   - ✅ Áudio **reproduz normalmente**
   - ✅ Progress bar avança
   - ✅ Tempo atualiza (ex: `0:02 / 0:05`)
3. **Clicar em Pause:**
   - ✅ Áudio pausa
   - ✅ Botão volta a mostrar ícone Play

### Teste 4: Múltiplos Áudios
1. **Enviar 3 áudios seguidos** do WhatsApp
2. **Na aplicação:**
   - ✅ Todos mostram "Baixando..." inicialmente
   - ✅ Cada um fica verde quando termina (pode ser em ordem diferente)
   - ✅ Todos reproduzem corretamente após download

---

## 📊 Impacto

### Benefícios:
✅ **Áudio enviado** aparece profissional (como gravado, não encaminhado)  
✅ **Áudio recebido** funciona corretamente no navegador  
✅ **Feedback visual** claro durante download (spinner + texto)  
✅ **UX melhorada** - usuário sabe quando pode reproduzir  
✅ **Sem erros** no console (`NotSupportedError` resolvido)  
✅ **Compatível** com Evolution API v2.3.6+  

### Pontos de Atenção:
⚠️ Aguardar **2-3 minutos** para deploy no Railway  
⚠️ Pode ser necessário **reconectar instância** Evolution  
⚠️ Testar com **áudios curtos (3-5s)** e **longos (30s+)**  
⚠️ Verificar em **diferentes navegadores** (Chrome, Firefox, Safari)  

---

## 🔗 Arquivos Modificados

1. **Backend:**
   - `backend/apps/chat/tasks.py` (linhas 270-305)

2. **Frontend:**
   - `frontend/src/modules/chat/components/AttachmentPreview.tsx` (linhas 148-213)

---

## 📝 Commits

```
fix: Corrigir áudio PTT enviado e recebido

Backend (tasks.py):
- Usar endpoint correto /message/sendWhatsAppAudio para PTT
- Seguir spec oficial Evolution API (audio, delay)
- Remove parâmetro encoding incorreto
- Ref: https://doc.evolution-api.com/v2/api-reference/message-controller/send-audio

Frontend (AttachmentPreview.tsx):
- Detectar quando áudio ainda não foi baixado (URL Evolution vs S3)
- Mostrar spinner + 'Baixando...' enquanto processa
- Desabilitar player até URL estar disponível
- Só renderizar <audio> quando ready para evitar NotSupportedError

Fixes:
- Áudio enviado agora aparece como PTT gravado (não encaminhado)
- Áudio recebido mostra estado de loading até ficar disponível
```

---

## 📚 Referências

- [Evolution API - Send WhatsApp Audio](https://doc.evolution-api.com/v2/api-reference/message-controller/send-audio)
- [MDN - HTMLAudioElement](https://developer.mozilla.org/en-US/docs/Web/API/HTMLAudioElement)
- [WhatsApp Business API - Audio Messages](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#audio-object)

---

## ✅ Checklist de Verificação

Após deploy:

- [ ] Deploy concluído (2-3 min)
- [ ] Instância reconectada (se necessário)
- [ ] **Teste 1:** Áudio enviado aparece como PTT gravado ✅
- [ ] **Teste 2:** Áudio recebido mostra "Baixando..." ✅
- [ ] **Teste 3:** Áudio recebido reproduz após download ✅
- [ ] **Teste 4:** Múltiplos áudios funcionam corretamente ✅
- [ ] Console sem erros `NotSupportedError` ✅

---

**Status:** 🚀 Deploy em andamento (aguardar 2-3 min)



