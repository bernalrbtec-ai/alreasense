# 🧪 TESTE DE PERFORMANCE - APÓS LIMPEZA

## ✅ Status Atual
- ✅ Conversas limpas
- ✅ Anexos limpos
- ✅ Otimizações de performance implementadas
- ✅ Sistema pronto para testes

## 🎯 O Que Testar

### **1. Primeira Carga de Conversas**
**Cenário:** Sistema vazio, primeira conversa recebida

**O que verificar:**
- ✅ Conversa aparece imediatamente
- ✅ Mensagem aparece rapidamente
- ✅ Nome do contato carrega corretamente
- ✅ Foto de perfil carrega (se houver)

**Performance esperada:**
- < 500ms para carregar primeira conversa
- < 200ms para carregar mensagens

---

### **2. Carga de Múltiplas Conversas**
**Cenário:** Receber várias conversas simultaneamente

**O que verificar:**
- ✅ Todas as conversas aparecem
- ✅ Última mensagem carrega corretamente
- ✅ Unread count funciona (deve ser 0 ou 1)
- ✅ Sem lag ou travamento

**Performance esperada:**
- 10 conversas: < 1s
- 50 conversas: < 2s
- 100 conversas: < 3s

---

### **3. Mensagens com Anexos**
**Cenário:** Receber mensagens com imagens, PDFs, áudios

**O que verificar:**
- ✅ Anexo processado rapidamente (RabbitMQ)
- ✅ Preview aparece no chat
- ✅ Download funciona
- ✅ Sem erros de carregamento

**Performance esperada:**
- Base64: < 2s para aparecer
- URL descriptografada: < 3s
- Fallback: < 5s

---

### **4. Paginação de Mensagens**
**Cenário:** Conversa com muitas mensagens (criar manualmente se necessário)

**O que verificar:**
- ✅ Carrega apenas últimas 50 mensagens
- ✅ Botão "Carregar mensagens antigas" aparece
- ✅ Scroll mantém posição ao carregar mais
- ✅ Sem lag ao carregar mais mensagens

**Performance esperada:**
- Primeira carga: < 500ms
- Carregar mais: < 300ms

---

### **5. Filtro de Conversas**
**Cenário:** Filtrar por departamento ou busca

**O que verificar:**
- ✅ Filtro responde instantaneamente
- ✅ Busca funciona rápido
- ✅ Sem re-renders desnecessários

**Performance esperada:**
- Filtro: < 100ms
- Busca: < 200ms

---

## 📊 Métricas a Observar

### **Backend (Logs Railway):**
- Tempo de resposta das queries
- Número de queries por requisição
- Cache hits/misses

### **Frontend (DevTools):**
- Network requests
- Render time
- Memory usage

### **Queries Esperadas:**
- **Antes (otimização):** ~300 queries para 100 conversas
- **Depois (otimização):** ~5 queries para 100 conversas

---

## 🔍 O Que Verificar Especificamente

### **1. Unread Count**
- Deve ser calculado em batch (1 query para todas)
- Não deve fazer query por conversa

### **2. Last Message**
- Deve usar prefetch_related (1 query para todas)
- Não deve fazer query por conversa

### **3. Paginação**
- Deve carregar apenas 50 mensagens por vez
- Não deve carregar todas de uma vez

### **4. Cache**
- Instance friendly name: cache de 5 min
- Contact tags: cache de 10 min
- S3 URLs: cache de 10 min

---

## 🐛 Problemas Conhecidos a Observar

### **Se Conversas Aparecem Sem Conteúdo:**
- ✅ Verificar se RabbitMQ está processando
- ✅ Verificar logs de `media_tasks.py`
- ✅ Aguardar 1-2 segundos (processamento assíncrono)

### **Se Grupo Demora Para Aparecer Nome:**
- ✅ Verificar se `refresh-info` foi chamado
- ✅ Verificar cache de grupo
- ✅ Verificar se Evolution API respondeu

### **Se Toasts Atrasados:**
- ✅ Verificar `useTenantSocket.ts`
- ✅ Verificar duration dos toasts
- ✅ Verificar `globalToastRegistry`

---

## 📝 Checklist de Teste

### **Funcionalidade:**
- [ ] Receber primeira mensagem
- [ ] Criar conversa manualmente
- [ ] Enviar mensagem
- [ ] Enviar anexo (imagem)
- [ ] Enviar anexo (PDF)
- [ ] Enviar anexo (áudio)
- [ ] Filtrar por departamento
- [ ] Buscar conversa
- [ ] Carregar mensagens antigas
- [ ] Transferir conversa

### **Performance:**
- [ ] Tempo de carregamento < 1s (10 conversas)
- [ ] Tempo de carregamento < 3s (100 conversas)
- [ ] Queries < 10 (100 conversas)
- [ ] Cache funcionando
- [ ] Sem re-renders desnecessários

### **UI/UX:**
- [ ] Mensagens aparecem rápido
- [ ] Anexos carregam corretamente
- [ ] Scroll funciona suave
- [ ] Filtros respondem rápido
- [ ] Sem lag ou travamento

---

## 🎯 Próximos Passos

Após os testes:
1. ✅ Verificar se performance está dentro do esperado
2. ✅ Identificar gargalos restantes (se houver)
3. ✅ Ajustar cache times se necessário
4. ✅ Ajustar pagination limits se necessário

---

## 📞 Monitoramento

**Logs a observar:**
- `backend/apps/chat/api/views.py` - Queries de conversas
- `backend/apps/chat/api/serializers.py` - Serialização
- `backend/apps/chat/media_tasks.py` - Processamento de mídia
- `frontend/src/modules/chat/components/MessageList.tsx` - Carregamento de mensagens

**Ferramentas:**
- Railway logs (backend)
- Browser DevTools (frontend)
- Django Debug Toolbar (se ativado)
- React DevTools Profiler

---

**Boa sorte com os testes! 🚀**

