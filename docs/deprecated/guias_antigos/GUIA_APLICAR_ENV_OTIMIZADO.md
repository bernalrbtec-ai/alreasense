# 🚀 GUIA: Como Aplicar ENV Otimizado no Railway

## 🎯 PROBLEMA IDENTIFICADO

O **erro do RabbitMQ** (`localhost:5672`) ocorreu porque:

❌ **Variável `RABBITMQ_URL` NÃO estava configurada no serviço Backend!**

Mesmo com o RabbitMQ rodando no Railway, o Backend não sabia como conectar.

---

## ✅ SOLUÇÃO APLICADA

### 1️⃣ **Código Corrigido** (Commit `af1e491`)

```python
# backend/alrea_sense/settings.py
# ✅ Agora prioriza RABBITMQ_PRIVATE_URL (internal - mais rápido)
RABBITMQ_URL = config('RABBITMQ_PRIVATE_URL', default=None)
```

### 2️⃣ **Variáveis a Adicionar no Railway**

```bash
# ✅ ADICIONAR no Backend → Variables
RABBITMQ_URL="amqp://75jk0mkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672"
```

### 3️⃣ **Variáveis a Remover** (Limpeza)

```bash
# ❌ REMOVER do Backend → Variables (não usadas)
CELERY_BROKER_URL          # Projeto usa RabbitMQ + aio-pika, não Celery
CELERY_RESULT_BACKEND      # Projeto usa RabbitMQ + aio-pika, não Celery
MONGOHOST                  # Projeto usa PostgreSQL + pgvector, não MongoDB
MONGOPORT                  # Projeto usa PostgreSQL + pgvector, não MongoDB
MONGOUSER                  # Projeto usa PostgreSQL + pgvector, não MongoDB
MONGOPASSWORD              # Projeto usa PostgreSQL + pgvector, não MongoDB
MONGO_URL                  # Projeto usa PostgreSQL + pgvector, não MongoDB
```

---

## 📋 PASSO A PASSO NO RAILWAY

### **Passo 1: Acessar Railway**
```
https://railway.app
→ Projeto: ALREA Sense
→ Serviço: Backend
→ Aba: Variables
```

### **Passo 2: Adicionar RABBITMQ_URL**

**Opção A: Variable Reference (Recomendado) ✅**
```
1. Clique em "+ New Variable"
2. Clique em "Variable Reference"
3. Selecione: Service → RabbitMQ
4. Selecione: Variable → RABBITMQ_PRIVATE_URL
5. Name: RABBITMQ_URL
6. Save
```

**Opção B: Raw Value**
```
1. Clique em "+ New Variable"
2. Key: RABBITMQ_URL
3. Value: amqp://75jk0mkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672
4. Add
```

### **Passo 3: Remover Variáveis Antigas** (Opcional)

Para cada variável não usada:
```
1. Localize a variável (ex: CELERY_BROKER_URL)
2. Clique nos 3 pontinhos "⋮"
3. Clique em "Remove"
4. Confirme
```

### **Passo 4: Aguardar Redeploy**
```
Railway vai fazer redeploy automático (2-3 min)
```

---

## 🧪 COMO VERIFICAR SE FUNCIONOU

### **1️⃣ Verificar Logs do Railway**

No serviço **Backend** → Deployments → [Ativo] → Logs:

```bash
# ✅ Deve aparecer:
🔍 [DEBUG] RABBITMQ_PRIVATE_URL env: amqp://75jk0mkcjQmQLFs3:...
✅ [SETTINGS] Usando RABBITMQ_PRIVATE_URL (internal - recomendado)
✅ [SETTINGS] RABBITMQ_URL final: amqp://***:***@rabbitmq.railway.internal:5672

# ✅ Chat consumer deve conectar:
✅ [CHAT CONSUMER] Conectado ao RabbitMQ
✅ [CHAT CONSUMER] Filas declaradas

# ❌ NÃO deve mais aparecer:
❌ Connection to amqp://guest:******@localhost:5672/ closed
❌ [Errno 111] Connect call failed
```

### **2️⃣ Testar Funcionalidade**

```bash
1. Acesse: https://alreasense-production.up.railway.app
2. Vá em "Chat" ou "Campanhas"
3. Teste enviar uma mensagem
4. Verifique se processa corretamente
```

---

## 📊 RESUMO DAS MUDANÇAS

| Item | Antes | Depois | Status |
|------|-------|--------|--------|
| RABBITMQ_URL | ❌ Não existia | ✅ Configurado | CRÍTICO |
| CELERY_* | ⚠️ Configurado | ❌ Removido | Limpeza |
| MONGO* | ⚠️ Configurado | ❌ Removido | Limpeza |
| Prioridade | URL (proxy) | PRIVATE_URL (internal) | Performance |

---

## 🎯 ENV COMPLETO OTIMIZADO

Veja o arquivo `ENV_OTIMIZADO_RAILWAY.txt` para referência completa de todas as variáveis.

**Principais mudanças:**
1. ✅ **RABBITMQ_URL** adicionado (critical fix!)
2. ❌ **Celery** removido (não usado)
3. ❌ **MongoDB** removido (não usado)
4. 📝 Documentação clara de cada variável
5. ⚠️ Alerta sobre EVO_API_KEY que pode ter vazado

---

## 🔐 SEGURANÇA

### ⚠️ ATENÇÃO: EVO_API_KEY

A chave Evolution API no seu .env é a **mesma que vazou antes**:
```
EVO_API_KEY="584B4A4A-0815-AC86-DC39-C38FC27E8E17"
```

**Recomendação:**
1. Gere uma nova API key no servidor Evolution
2. Atualize a variável no Railway
3. Delete a key antiga do servidor

---

## ✅ CHECKLIST FINAL

```
[ ] Push do código feito (commit af1e491) ✅
[ ] Acessei Railway → Backend → Variables
[ ] Adicionei RABBITMQ_URL (variable reference ou raw)
[ ] (Opcional) Removi CELERY_BROKER_URL
[ ] (Opcional) Removi CELERY_RESULT_BACKEND
[ ] (Opcional) Removi variáveis MONGO*
[ ] Aguardei redeploy (2-3 min)
[ ] Verifiquei logs (sem erro localhost:5672)
[ ] Testei chat/campanhas (funcionando)
[ ] (Recomendado) Rotacionei EVO_API_KEY
```

---

## 🚨 SE DER ERRO

### Erro persiste após adicionar RABBITMQ_URL?

1. Verifique se a variável foi salva:
   ```
   Railway → Backend → Variables → Procure RABBITMQ_URL
   ```

2. Force um redeploy:
   ```
   Railway → Backend → Deployments → Redeploy
   ```

3. Verifique os logs de debug:
   ```
   Logs devem mostrar: "✅ [SETTINGS] Usando RABBITMQ_PRIVATE_URL"
   ```

4. Se ainda não funcionar, me avise! 🆘

---

## 📚 DOCUMENTAÇÃO RELACIONADA

- `ENV_OTIMIZADO_RAILWAY.txt` - Referência completa de variáveis
- `.cursorrules` - Lições aprendidas sobre RabbitMQ
- `ANALISE_SEGURANCA_COMPLETA.md` - Auditoria de segurança

---

## ✅ RESULTADO ESPERADO

Após aplicar essas mudanças:

```
✅ Chat consumer conecta ao RabbitMQ corretamente
✅ Mensagens são processadas
✅ Campanhas funcionam
✅ Webhooks são recebidos
✅ Performance otimizada (internal URL)
✅ Env limpo (sem variáveis não usadas)
```

🎉 **Sistema 100% funcional!**

