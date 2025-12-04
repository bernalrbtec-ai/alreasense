# 🔧 Correções de Minificação - Erro "Cannot access 'X' before initialization"

## 📋 Resumo do Problema

O erro `ReferenceError: Cannot access 'X' before initialization` ocorria ao acessar grupos no chat devido a conflitos de minificação. O minificador estava renomeando variáveis de uma letra (u, d, m, c, etc.) causando conflitos de inicialização.

## ✅ Todas as Correções Aplicadas

### Variáveis Renomeadas:

1. **`u`** → `reactionUserItem` (no map de users em MessageReactions)
2. **`m`** → `messageItem` (em find callbacks)
3. **`a`** → `attachmentItem` / `messageA` / `conversationA` (em find/map/sort)
4. **`b`** → `messageB` / `conversationB` (em sort callbacks)
5. **`msg`** → `messageItem` (em forEach callbacks)
6. **`id`** → `messageIdItem` (no map de messageIds)
7. **`acc`** → `accumulator` (no reduce)
8. **`user`** → `currentUser` (em MessageReactions)
9. **`data`** → `reactionData` / `reactionDataValue` (em MessageReactions)
10. **`contact`** → `contactItem` (em SharedContactCard e ChatWindow)
11. **`conv`** → `conversationItem` (em SharedContactCard)
12. **`c`** → `conversationItem` / `contactItem` (em vários arquivos)
13. **`i`** → `tagIndex` (no map de ai_tags)
14. **`message`** → `messageItem` (em forEach de chatStore)
15. **`emoji`** → `emojiKey` (em desestruturação Object.entries)
16. **`att`** → `attachmentItem` (em some callback)

### Arquivos Corrigidos:

- ✅ `MessageList.tsx` - Todas as variáveis de uma letra renomeadas
- ✅ `ChatWindow.tsx` - Variáveis 'c' em find callbacks
- ✅ `SharedContactCard.tsx` - Variáveis 'contact' e 'conv'
- ✅ `useChatSocket.ts` - Variável 'm' em find
- ✅ `useTenantSocket.ts` - Variável 'c' em find
- ✅ `usePollingFallback.ts` - Variáveis 'a' e 'b' em sort
- ✅ `chatStore.ts` - Variáveis 'c', 'message', 'messageId', 'att'
- ✅ `conversationUpdater.ts` - Variáveis 'c', 'a', 'b'
- ✅ `messageUtils.ts` - Variáveis 'a' e 'b' em sort
- ✅ `ForwardMessageModal.tsx` - Variáveis 'c' em filter
- ✅ `AttachmentPreview.tsx` - Variável 'i' em map

### Configuração do Vite:

Adicionada configuração no `vite.config.ts` para:
- Manter nomes de variáveis durante minificação (`keepNames: true`)
- Usar esbuild ao invés de terser (mais previsível)

## 🧹 Scripts de Limpeza de Cache

Criados scripts para limpar todos os caches:
- `frontend/limpar-cache.bat` (Windows)
- `frontend/limpar-cache.sh` (Linux/Mac)

## 📝 Comandos para Limpar Cache Manualmente

### Windows:
```bash
cd frontend
rmdir /s /q node_modules\.vite
rmdir /s /q dist
npm cache clean --force
npm install
npm run dev
```

### Linux/Mac:
```bash
cd frontend
rm -rf node_modules/.vite
rm -rf dist
npm cache clean --force
npm install
npm run dev
```

## 🔍 Se o Erro Persistir

1. **Limpar cache do navegador** (Ctrl+Shift+Delete)
2. **Testar em aba anônima/privada**
3. **Verificar se o build está usando a configuração atualizada**
4. **Verificar logs do console para identificar a linha exata do erro**
5. **Considerar desabilitar minificação temporariamente para debug**

## 📚 Referências

- Todas as variáveis de uma letra foram renomeadas para nomes descritivos
- Configuração do Vite ajustada para manter nomes de variáveis
- Scripts de limpeza de cache criados

