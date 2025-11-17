# 🚨 PROBLEMA ENCONTRADO: RABBITMQ_URL Truncada

**Data:** 27 de Outubro de 2025 (Pós-almoço)

---

## 🔍 EVIDÊNCIA DO PROBLEMA

### Nos logs do Railway:
```
🔍 [DEBUG] RABBITMQ_URL env: amqp://75jk0mkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-Eq
                                                                             ↑ PARA AQUI
```

### Senha Correta (do Railway):
```
RABBITMQ_DEFAULT_PASS: ~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ
                                                 ↑ FALTAM 6 CHARS (eurdvJ)
```

**Resultado:** URL está **INCOMPLETA** → Credenciais **ERRADAS** → `ACCESS_REFUSED`

---

## 🎯 POR QUE CAMPAIGNS FUNCIONA?

### Hipótese 1: Campaigns usa conexão diferente
- Campaigns pode ter sua própria lógica de conexão
- Pode estar pegando de `RABBITMQ_PRIVATE_URL` diretamente
- Ou tem credenciais hardcoded antigas (não desejável)

### Hipótese 2: Railway tem 2 variáveis diferentes
- `RABBITMQ_URL` (pública, proxy) → TRUNCADA ❌
- `RABBITMQ_PRIVATE_URL` (interna) → CORRETA ✅
- Campaigns usa a PRIVATE, Chat usa a pública

---

## ✅ SOLUÇÕES

### 🔴 SOLUÇÃO 1: Forçar uso de RABBITMQ_PRIVATE_URL (RECOMENDADA)

**Problema:** Settings.py já tenta usar `RABBITMQ_PRIVATE_URL` primeiro, mas os logs mostram "Not set".

**Ação:** Verificar no Railway se `RABBITMQ_PRIVATE_URL` realmente existe.

**Passos:**
1. Acessar Railway Dashboard
2. Ir em variáveis de ambiente do serviço RabbitMQ
3. Verificar se existe `RABBITMQ_PRIVATE_URL`
4. Se NÃO existir, criar manualmente:
   ```
   RABBITMQ_PRIVATE_URL=amqp://75jk0mkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672
   ```

**Por quê usar PRIVATE?**
- ✅ Mais rápido (comunicação interna Railway)
- ✅ Mais seguro (não expõe ao proxy)
- ✅ Recomendado pelo Railway

---

### 🟡 SOLUÇÃO 2: Corrigir RABBITMQ_URL no Railway

**Ação:** Atualizar a variável `RABBITMQ_URL` com a senha COMPLETA.

**Passos:**
1. Acessar Railway Dashboard → Backend Service → Variables
2. Editar `RABBITMQ_URL`
3. Substituir por:
   ```
   amqp://75jk0mkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672
   ```
4. Salvar e fazer redeploy

**⚠️ ATENÇÃO:** Railway pode estar truncando automaticamente. Se truncar novamente, usar SOLUÇÃO 3.

---

### 🟢 SOLUÇÃO 3: URL Encoding na Variável (Se Railway trunca especiais)

Se Railway está truncando porque tem `~` na senha, precisamos **URL encodar** a senha **NA VARIÁVEL DE AMBIENTE**, não no código.

**URL Encoded:**
```
~ → %7E
```

**Senha encoded:**
```
~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ
→
%7ECiJnJU1I-1k%7EGS.vRf4qj8-EqeurdvJ
```

**URL completa:**
```
amqp://75jk0mkcjQmQLFs3:%7ECiJnJU1I-1k%7EGS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672
```

**Passos:**
1. Editar `RABBITMQ_URL` no Railway
2. Usar URL com senha encoded acima
3. Redeploy

---

### 🔵 SOLUÇÃO 4: Usar Credenciais Diretas (Temporário para DEBUG)

**Ação:** Construir URL manualmente no `settings.py` usando `RABBITMQ_DEFAULT_USER` e `RABBITMQ_DEFAULT_PASS`.

**Código:**
```python
# Em settings.py, após tentar RABBITMQ_URL
if not RABBITMQ_URL:
    user = config('RABBITMQ_DEFAULT_USER', default=None)
    password = config('RABBITMQ_DEFAULT_PASS', default=None)
    host = 'rabbitmq.railway.internal'
    port = 5672
    
    if user and password:
        from urllib.parse import quote
        # URL encode APENAS a senha
        password_encoded = quote(password, safe='')
        RABBITMQ_URL = f'amqp://{user}:{password_encoded}@{host}:{port}'
        print(f"✅ [SETTINGS] RABBITMQ_URL construída manualmente")
```

**⚠️ Problema:** Isso seria aplicar encoding novamente (pode causar double encoding).

**Melhor:** Usar **SEM encoding**, confiar que aio-pika faz o encoding:
```python
if user and password:
    RABBITMQ_URL = f'amqp://{user}:{password}@{host}:{port}'
```

---

## 🧪 TESTE RÁPIDO NO RAILWAY

Execute este comando no Railway para verificar:

```bash
railway run bash -c 'echo "USER: $RABBITMQ_DEFAULT_USER" && echo "PASS length: ${#RABBITMQ_DEFAULT_PASS}" && echo "URL length: ${#RABBITMQ_URL}"'
```

**Resultados esperados:**
```
USER: 75jk0mkcjQmQLFs3
PASS length: 34
URL length: 113 (aproximadamente)
```

**Se URL length < 100:** URL está truncada! ❌

---

## 📊 CHECKLIST DE VERIFICAÇÃO

No Railway Dashboard, verificar:

- [ ] Variável `RABBITMQ_PRIVATE_URL` existe?
- [ ] Variável `RABBITMQ_URL` tem 110+ caracteres?
- [ ] Senha em `RABBITMQ_DEFAULT_PASS` tem 34 caracteres?
- [ ] User em `RABBITMQ_DEFAULT_USER` é `75jk0mkcjQmQLFs3` (com zero, não O)?

---

## 🎯 RECOMENDAÇÃO FINAL

**MELHOR SOLUÇÃO:** Usar `RABBITMQ_PRIVATE_URL` (interna).

**Por quê?**
1. ✅ Railway recomenda usar variáveis `*_PRIVATE_URL` para comunicação interna
2. ✅ Evita problemas com proxy
3. ✅ Mais rápido
4. ✅ Campaigns provavelmente está usando ela (por isso funciona)

**AÇÃO IMEDIATA:**
1. Verificar se `RABBITMQ_PRIVATE_URL` existe no Railway
2. Se NÃO existe, criar com a senha completa
3. Fazer redeploy
4. Verificar logs: deve mostrar "✅ Usando RABBITMQ_PRIVATE_URL (internal)"

---

## 🚀 DEPOIS DE APLICAR A FIX

**Logs esperados:**
```
✅ [SETTINGS] Usando RABBITMQ_PRIVATE_URL (internal - recomendado)
✅ [SETTINGS] RABBITMQ_URL final: amqp://***:***@rabbitmq.railway.internal:5672
...
✅ [CHAT CONSUMER] Conexão RabbitMQ estabelecida com sucesso!
✅ [FLOW CHAT] Consumer pronto para processar mensagens!
```

**SEM nenhum:**
```
❌ ACCESS_REFUSED
```

---

**Status:** 🔍 **PROBLEMA IDENTIFICADO**  
**Próxima Ação:** Verificar/criar `RABBITMQ_PRIVATE_URL` no Railway

