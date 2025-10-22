# ⚡ CONFIGURAÇÃO RÁPIDA - Railway

## 🎯 AÇÃO NECESSÁRIA AGORA

O deploy está em andamento, mas você precisa adicionar **1 variável de ambiente** no Railway:

### **Opção 1: Via Dashboard (Recomendado)**

1. Acesse: https://railway.app
2. Entre no projeto
3. Clique em **Variables**
4. Clique em **+ New Variable**
5. Adicione:
   ```
   Name: CHAT_LOG_LEVEL
   Value: WARNING
   ```
6. Salve (deploy automático acontece)

### **Opção 2: Via CLI (Se tiver instalado)**

```bash
railway variables --set CHAT_LOG_LEVEL=WARNING
```

---

## 🎯 O QUE ISSO FAZ

- ✅ **Reduz logs em 80-90%** (evita rate limit)
- ✅ **Mantém apenas avisos e erros** (o importante)
- ✅ **Silencia logs verbosos do webhook** (que estava causando 500 logs/segundo)

---

## ⏱️ AGUARDAR

- Deploy do código: **2-3 minutos**
- Aplicação da variável: **automático após adicionar**

---

## ✅ RESULTADO ESPERADO

**Depois do deploy + variável:**
1. ✅ Nomes dos contatos corretos (não mais "Paulo Bernal" em todos)
2. ✅ Grupos com nome e foto reais
3. ✅ Logs reduzidos drasticamente
4. ⚠️ WebSocket de novas conversas ainda precisa ser investigado

---

**Configure a variável agora e me avisa quando terminar! 🚀**

