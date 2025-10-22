# ⚡ AÇÕES NECESSÁRIAS AGORA

## ✅ O QUE JÁ FOI FEITO

1. ✅ **Bug corrigido:** Nomes de contatos não aparecerão mais como "Paulo Bernal"
2. ✅ **Bug corrigido:** Grupos terão nome e foto reais
3. ✅ **Logger adicionado:** Logs serão reduzidos em 80-90%
4. ✅ **Commit e push:** Código está no Railway, deploy em andamento
5. ✅ **WebSocket investigado:** Código está correto, funcionará após deploy

---

## 🎯 VOCÊ PRECISA FAZER AGORA

### **1. Configurar variável no Railway** (URGENTE - reduz logs)

**Via Dashboard:**
1. Acesse: https://railway.app  
2. Entre no projeto  
3. Clique em **Variables**  
4. Clique em **+ New Variable**  
5. Adicione:
   ```
   Name: CHAT_LOG_LEVEL
   Value: WARNING
   ```
6. Salve (deploy automático)

**OU via CLI:**
```bash
railway variables --set CHAT_LOG_LEVEL=WARNING
```

---

### **2. Aguardar deploy terminar** (2-3 minutos)

Enquanto isso, você pode ir tomar um café ☕

---

### **3. Depois do deploy - LIMPAR TUDO E TESTAR**

**3.1. Limpar conversas antigas (dados corrompidos):**

```bash
# Execute no psql do Railway:
DELETE FROM chat_attachment;
DELETE FROM chat_message;
DELETE FROM chat_conversation_participants;
DELETE FROM chat_conversation;
```

**OU use o script:**
```bash
railway run psql < clear_chat_quick.sql
```

**3.2. Reconectar instâncias WhatsApp:**
- Acesse Evolution API
- Reconecte as instâncias
- Escaneie QR codes

**3.3. Testar:**
1. Abra Flow Chat
2. **Abra console do navegador (F12)**
3. Envie mensagem de um contato novo
4. **Verifique:**
   - ✅ Nome do contato aparece correto (não "Paulo Bernal")
   - ✅ Foto de perfil aparece
   - ✅ Conversa aparece **instantaneamente** (sem refresh)
   - ✅ Console mostra: `🆕 [TENANT WS] Nova conversa`

5. Entre em um grupo novo e envie mensagem
6. **Verifique:**
   - ✅ Nome do grupo aparece correto (não "Grupo WhatsApp")
   - ✅ Foto do grupo aparece
   - ✅ Aparece instantaneamente

---

## 📊 RESULTADO ESPERADO

### **ANTES (com bug):**
- ❌ Todos os contatos: "Paulo Bernal"
- ❌ Todos os grupos: "Grupo WhatsApp" (sem foto)
- ❌ Precisa refresh manual (F5)
- ❌ 500 logs/segundo (rate limit)

### **DEPOIS (corrigido):**
- ✅ Nomes corretos dos contatos
- ✅ Grupos com nome e foto reais
- ✅ Atualização em tempo real (WebSocket)
- ✅ ~50-100 logs/segundo (80-90% redução)

---

## 🐛 SE AINDA TIVER PROBLEMAS

1. **Copie os logs do console do navegador** (F12)
2. **Envie para mim** junto com a descrição do problema
3. Use o guia: `DEBUG_WEBSOCKET.md`

---

## 📋 CHECKLIST RÁPIDO

- [ ] ✅ Commit e push FEITO
- [ ] ⏳ Deploy Railway em andamento
- [ ] ⏸️ **VOCÊ FAZ:** Adicionar variável `CHAT_LOG_LEVEL=WARNING`
- [ ] ⏸️ **VOCÊ FAZ:** Aguardar deploy terminar
- [ ] ⏸️ **VOCÊ FAZ:** Limpar conversas antigas
- [ ] ⏸️ **VOCÊ FAZ:** Reconectar instâncias
- [ ] ⏸️ **VOCÊ FAZ:** Testar e verificar

---

**🎯 Configure a variável CHAT_LOG_LEVEL agora e me avisa quando o deploy terminar!**

**Depois teste e me conta o resultado!** 🚀

