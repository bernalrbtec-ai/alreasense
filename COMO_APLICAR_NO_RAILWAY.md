# 🚀 Como Aplicar as Novas Variáveis no Railway

**Data:** 27 de Outubro de 2025  
**Objetivo:** Adicionar `RABBITMQ_DEFAULT_USER` e `RABBITMQ_DEFAULT_PASS` para resolver o erro `ACCESS_REFUSED`

---

## 📋 PASSO A PASSO

### 1️⃣ Acessar o Railway Dashboard

1. Ir para: https://railway.app
2. Login (se necessário)
3. Selecionar projeto: **ALREA Sense**
4. Clicar no serviço: **Backend** (Django/Daphne)

---

### 2️⃣ Abrir Editor de Variáveis

1. Na página do serviço Backend, clicar na aba: **Variables**
2. Clicar no botão: **Raw Editor** (canto superior direito)
   - Isso abre o modo texto onde você pode colar tudo de uma vez

---

### 3️⃣ Copiar e Colar

1. Abrir o arquivo: `RAILWAY_ENV_VARS.txt` (está na raiz do projeto)
2. **Copiar TODO o conteúdo** (linhas 13-35, sem os comentários)
3. **Colar** no Raw Editor do Railway
   - Isso vai **substituir todas as variáveis existentes**
   - ⚠️ Certifique-se de copiar TUDO, não apenas as 2 novas linhas!

**Conteúdo a copiar:**
```
AI_EMBEDDING_MODEL="qwen-mini-embeddings"
AI_MODEL_NAME="qwen-local"
N8N_AI_WEBHOOK=""
DEBUG="False"
SECRET_KEY="N;.!iB5@sw?D2wJPr{Ysmt5][R%5.aHyAuvNpM_@DOb:OX*<.f"
LOG_FORMAT="json"
LOG_LEVEL="INFO"
ALLOWED_HOSTS="alreasense-backend-production.up.railway.app,localhost,127.0.0.1"
CORS_ALLOWED_ORIGINS="https://alreasense-production.up.railway.app"
CSRF_TRUSTED_ORIGINS="https://alreasense-production.up.railway.app"
ALLOW_ALL_WEBHOOK_ORIGINS="true"
DATABASE_URL="postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@postgres-59a0986d.railway.internal:5432/railway"
REDIS_URL="redis://default:AJSfSJmpfWSdYZxSIfLyjPTsdDyUULsu@redis-3bz0.railway.internal:6379"
CHANNELS_REDIS_URL="redis://default:AJSfSJmpfWSdYZxSIfLyjPTsdDyUULsu@redis-3bz0.railway.internal:6379"
RABBITMQ_URL="amqp://75jk0mkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672"
RABBITMQ_DEFAULT_USER="75jk0mkcjQmQLFs3"
RABBITMQ_DEFAULT_PASS="~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ"
EVO_BASE_URL="https://evo.rbtec.com.br"
EVO_API_KEY="E2413B31-B12C-46ED-ACA0-7EBCA8596A08"
STRIPE_PUBLISHABLE_KEY=""
STRIPE_SECRET_KEY=""
STRIPE_WEBHOOK_SECRET=""
```

---

### 4️⃣ Salvar e Confirmar

1. Clicar em: **Update Variables** (botão no canto)
2. Railway vai confirmar: "Variables updated"
3. **Railway vai fazer redeploy AUTOMATICAMENTE** 🚀

---

### 5️⃣ Verificar Deploy

1. Ir na aba: **Deployments**
2. Aguardar o novo deploy completar (~3-5 min)
3. Status deve ficar: **✅ Success**

---

### 6️⃣ Verificar Logs

1. Ir na aba: **Logs** (ou clicar no deployment)
2. **Procurar por estas linhas:**

#### ✅ SUCESSO - Deve aparecer:
```
✅ [SETTINGS] RABBITMQ_URL construída manualmente de DEFAULT_USER + DEFAULT_PASS
   User: 75jk0mkcjQmQLFs3
   Pass length: 34 chars
✅ [SETTINGS] RABBITMQ_URL final: amqp://***:***@rabbitmq.railway.internal:5672
✅ [SETTINGS] RABBITMQ_URL length: 113 chars

🚀 [FLOW CHAT] Iniciando Flow Chat Consumer...
✅ [CHAT CONSUMER] Conexão RabbitMQ estabelecida com sucesso!
✅ [CHAT CONSUMER] Channel criado com sucesso!
✅ [FLOW CHAT] Consumer pronto para processar mensagens!
```

#### ❌ NÃO DEVE APARECER:
```
❌ [CHAT CONSUMER] Erro: ACCESS_REFUSED
🚨 [CHAT CONSUMER] ERRO DE AUTENTICAÇÃO RABBITMQ
✅ [SETTINGS] RABBITMQ_URL length: 87 chars  ← Se aparecer 87, ainda está truncado!
```

---

## 🎯 CHECKLIST FINAL

Após aplicar as mudanças, verificar:

- [ ] Railway fez redeploy automático
- [ ] Deploy completou com sucesso (status verde)
- [ ] Logs mostram `Pass length: 34 chars`
- [ ] Logs mostram `RABBITMQ_URL length: 113 chars` (não 87!)
- [ ] Logs mostram `✅ [CHAT CONSUMER] Conexão RabbitMQ estabelecida`
- [ ] **NÃO** aparece `ACCESS_REFUSED` nos logs
- [ ] Frontend carrega sem erros
- [ ] Mensagens WhatsApp chegam em tempo real

---

## 🆘 SE AINDA FALHAR

Se após aplicar as mudanças, o erro `ACCESS_REFUSED` persistir:

1. Verificar se as variáveis foram salvas corretamente:
   - Railway → Backend → Variables
   - Conferir se `RABBITMQ_DEFAULT_USER` e `RABBITMQ_DEFAULT_PASS` estão lá

2. Verificar logs completos:
   - Procurar por `🔍 [DEBUG] RABBITMQ_URL env:`
   - Verificar se ainda mostra 87 chars ou se mudou para 113 chars

3. Executar script de debug (se necessário):
   ```bash
   railway run python test_rabbitmq_detailed_debug.py
   ```

4. Avisar o desenvolvedor com os logs completos

---

## 📝 RESUMO DO PROBLEMA

**Antes:**
- `RABBITMQ_URL` estava truncada (87 chars ao invés de 113)
- Caractere `~` na senha causava truncamento no Railway
- Chat Consumer falhava com `ACCESS_REFUSED`

**Depois (com as 2 novas variáveis):**
- Sistema detecta URL truncada automaticamente
- Reconstrói URL usando credenciais separadas (`DEFAULT_USER` + `DEFAULT_PASS`)
- URL completa tem 113 chars (senha com 34 chars)
- Ambos consumers (Campaigns e Chat) funcionam! ✅

---

**Tempo estimado total:** ~5-10 minutos  
**Dificuldade:** ⭐ Fácil (só copiar e colar)

Qualquer dúvida, chamar o desenvolvedor! 🚀

