# 🔇 REDUZIR LOGS NO RAILWAY - Solução para Rate Limit

## 🚨 PROBLEMA
```
Railway rate limit of 500 logs/sec reached for replica
Messages dropped: 3835
```

## ✅ SOLUÇÃO IMPLEMENTADA

### **1. Logger Específico para Chat**
Adicionado no `settings.py`:
```python
'apps.chat': {
    'handlers': ['console'],
    'level': config('CHAT_LOG_LEVEL', default='WARNING'),  # Apenas WARNING e ERROR
    'propagate': False,
},
```

### **2. Variável de Ambiente no Railway**

**Opção A: Via Dashboard**
1. Acesse o projeto no Railway
2. Vá em **Variables**
3. Adicione:
   ```
   CHAT_LOG_LEVEL=WARNING
   ```
4. Deploy automático

**Opção B: Via CLI**
```bash
railway variables --set CHAT_LOG_LEVEL=WARNING
```

---

## 📊 NÍVEIS DE LOG

| Nível | O que loga | Quando usar |
|-------|-----------|-------------|
| `DEBUG` | Tudo (muito verboso) | Desenvolvimento local |
| `INFO` | Informações gerais | Desenvolvimento/staging |
| `WARNING` | Avisos + Erros | **PRODUÇÃO (recomendado)** |
| `ERROR` | Apenas erros | Produção com problemas |
| `CRITICAL` | Apenas críticos | Não recomendado |

---

## 🎯 CONFIGURAÇÃO RECOMENDADA

### **Produção (Railway):**
```bash
# No Railway dashboard ou .env:
CHAT_LOG_LEVEL=WARNING
LOG_LEVEL=INFO
```

### **Local (desenvolvimento):**
```bash
# No .env local:
CHAT_LOG_LEVEL=INFO
LOG_LEVEL=DEBUG
```

---

## 📉 REDUÇÃO ESPERADA

### **ANTES (com INFO):**
- ✅ `logger.info()` → **SIM** (causa rate limit)
- ✅ `logger.warning()` → **SIM**
- ✅ `logger.error()` → **SIM**
- **Resultado:** ~500 logs/segundo ❌

### **DEPOIS (com WARNING):**
- ❌ `logger.info()` → **NÃO** (silenciado)
- ✅ `logger.warning()` → **SIM**
- ✅ `logger.error()` → **SIM**
- **Resultado:** ~50-100 logs/segundo ✅

**Redução:** ~80-90% dos logs!

---

## 🧪 TESTAR LOCALMENTE

```bash
# 1. Configurar local para WARNING
export CHAT_LOG_LEVEL=WARNING

# 2. Rodar servidor
python manage.py runserver

# 3. Enviar mensagem de teste
# ✅ Você verá: apenas warnings e errors
# ❌ Você NÃO verá: logs info verbosos
```

---

## 🔍 LOGS QUE SERÃO SILENCIADOS

Com `CHAT_LOG_LEVEL=WARNING`, estes logs **não aparecerão mais**:
```python
logger.info("📥 [WEBHOOK UPSERT] ====== INICIANDO PROCESSAMENTO ======")
logger.info("📥 [WEBHOOK UPSERT] Tenant: ...")
logger.info("📥 [WEBHOOK UPSERT] Dados recebidos: ...")
logger.info("📱 [WEBHOOK UPSERT] Instância: ...")
logger.info("🔍 [TIPO] Conversa: ...")
logger.info("👥 [GRUPO] Enviado por: ...")
logger.info("📤 ENVIADA [WEBHOOK] ...")
logger.info("📋 [CONVERSA] NOVA: ...")
logger.info("📸 [FOTO] Iniciando busca...")
logger.info("✅ [GRUPO NOVO] Informações recebidas!")
# ... e muitos outros
```

---

## ✅ LOGS QUE CONTINUARÃO APARECENDO

Com `CHAT_LOG_LEVEL=WARNING`, estes logs **continuarão** (são importantes):
```python
logger.warning("⚠️ [REFRESH] Nenhuma instância ativa...")
logger.warning("⚠️ [INDIVIDUAL] Erro ao buscar foto: 404")
logger.error("❌ [WEBHOOK] Erro ao buscar foto de perfil: ...")
logger.error("❌ [GRUPO INFO] Erro ao buscar informações: ...")
```

---

## 🚀 DEPLOY

### **Passo 1: Commit**
```bash
git add backend/alrea_sense/settings.py
git commit -m "feat: Adicionar logger específico para chat com level WARNING"
git push
```

### **Passo 2: Configurar Railway**
```bash
# Via CLI
railway variables --set CHAT_LOG_LEVEL=WARNING

# OU via Dashboard:
# Railway > Variables > Add > CHAT_LOG_LEVEL=WARNING
```

### **Passo 3: Aguardar deploy** (2-3 min)

### **Passo 4: Monitorar**
```bash
railway logs
# Você deve ver MUITO menos logs agora!
```

---

## 📊 COMPARAÇÃO

### **ANTES:**
```
[INFO] 📥 [WEBHOOK UPSERT] ====== INICIANDO PROCESSAMENTO ======
[INFO] 📥 [WEBHOOK UPSERT] Tenant: RBTEC (ID: ...)
[INFO] 📥 [WEBHOOK UPSERT] Dados recebidos: {...massive json...}
[INFO] 📱 [WEBHOOK UPSERT] Instância: PauloCel
[INFO] 🔍 [TIPO] Conversa: individual | RemoteJID: ...
[INFO] 📥 RECEBIDA [WEBHOOK] +5517999999999: Olá...
[INFO] Tenant: RBTEC | Message ID: ...
[INFO] 👤 Nome: Paulo | 📸 Foto de Perfil: https://...
[INFO] 📋 [CONVERSA] EXISTENTE: +5517999999999 | Tipo: individual
[INFO] 💬 [MENSAGEM] Criada: ID=... | Content=Olá
[INFO] 📡 [BROADCAST] Enviando via WebSocket...
... ~15-20 logs por mensagem! ❌
```

### **DEPOIS:**
```
(silêncio... apenas se houver erro/warning)
... ~0-2 logs por mensagem! ✅
```

---

## 💡 DICAS EXTRAS

### **Se ainda tiver muitos logs:**

1. **Aumentar para ERROR** (apenas erros):
   ```bash
   railway variables --set CHAT_LOG_LEVEL=ERROR
   ```

2. **Desabilitar logs do Django** (não recomendado):
   ```bash
   railway variables --set LOG_LEVEL=WARNING
   ```

3. **Verificar outros apps** que podem estar logando:
   ```bash
   railway logs --filter "apps.campaigns"
   railway logs --filter "apps.notifications"
   ```

---

## 🔄 REVERTER SE NECESSÁRIO

Se precisar ver os logs novamente (debug):
```bash
# Voltar para INFO temporariamente
railway variables --set CHAT_LOG_LEVEL=INFO

# Depois de debugar, voltar para WARNING
railway variables --set CHAT_LOG_LEVEL=WARNING
```

---

## ✅ CHECKLIST

- [ ] Commit do código (`settings.py` atualizado)
- [ ] Push para Railway
- [ ] Adicionar variável `CHAT_LOG_LEVEL=WARNING` no Railway
- [ ] Aguardar deploy (2-3 min)
- [ ] Monitorar logs (`railway logs`)
- [ ] Verificar se rate limit parou
- [ ] Testar se sistema continua funcionando

---

**🎯 Pronto! Logs reduzidos em ~80-90%! 🎉**

Rate limit de 500 logs/segundo deve sumir completamente!

