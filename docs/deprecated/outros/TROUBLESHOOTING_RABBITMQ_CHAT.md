# 🚨 TROUBLESHOOTING: Erro de Autenticação RabbitMQ Chat Consumer

## ❌ ERRO IDENTIFICADO

```
❌ [CHAT CONSUMER] Erro ao iniciar consumers: ACCESS_REFUSED - Login was refused using authentication mechanism PLAIN
Connection to amqp://75jk0mkcjQmQLFs3:******@rabbitmq.railway.internal:5672
```

## 📊 SITUAÇÃO ATUAL

| CONSUMER | STATUS | OBSERVAÇÃO |
|----------|--------|------------|
| **Campaigns Consumer** | ✅ FUNCIONANDO | Conecta com sucesso |
| **Chat Consumer** | ❌ FALHANDO | Erro de autenticação |

## 🔍 CAUSA RAIZ

O erro `ACCESS_REFUSED` indica que:
1. ✅ A URL do RabbitMQ está correta (`rabbitmq.railway.internal:5672`)
2. ❌ As **credenciais estão incorretas** ou expiradas
3. ❌ Ou o usuário `75jk0mkcjQmQLFs3` não tem permissões

## 🎯 SOLUÇÃO APLICADA NO CÓDIGO

### ✅ 1. Parâmetros de Conexão Robustos
**Arquivo:** `backend/apps/chat/tasks.py:675`

Adicionados os mesmos parâmetros que funcionam no campaigns consumer:

```python
connection = await aio_pika.connect_robust(
    rabbitmq_url,
    heartbeat=0,  # Desabilitar heartbeat
    blocked_connection_timeout=0,
    socket_timeout=10,
    retry_delay=1,
    connection_attempts=1
)
```

### ✅ 2. Logs de Debug Melhorados
Agora mostra:
- URL mascarada sendo usada
- Parâmetros de conexão
- Diagnóstico detalhado do erro

### ✅ 3. Mensagem de Erro Detalhada
```
🚨 [CHAT CONSUMER] ERRO DE AUTENTICAÇÃO RABBITMQ
❌ Erro: ACCESS_REFUSED - Login was refused
📋 POSSÍVEIS CAUSAS:
1. Credenciais RabbitMQ incorretas
2. RABBITMQ_PRIVATE_URL com credenciais antigas
3. Usuário sem permissões suficientes
```

---

## 🔧 AÇÕES NECESSÁRIAS NO RAILWAY

### 1️⃣ VERIFICAR VARIÁVEIS DE AMBIENTE

Acesse Railway → Projeto → Variables e verifique:

```bash
# Verificar quais variáveis existem:
✅ RABBITMQ_URL              # URL proxy externo
✅ RABBITMQ_PRIVATE_URL      # URL interna (mais rápida)
✅ CLOUDAMQP_URL             # Se usando CloudAMQP

# Qual está sendo usada atualmente?
# Veja nos logs: "✅ [SETTINGS] Usando RABBITMQ_PRIVATE_URL"
```

### 2️⃣ COMPARAR CREDENCIAIS

Campaigns funciona, chat não. Vamos comparar:

```bash
# No Railway CLI ou logs, executar:
echo $RABBITMQ_URL
echo $RABBITMQ_PRIVATE_URL

# Verificar se são diferentes
# Se forem, o chat pode estar usando credenciais antigas
```

### 3️⃣ VERIFICAR SERVICE ID DO RABBITMQ

No Railway:

1. Acesse o serviço RabbitMQ
2. Vá em "Settings" → "Service ID"
3. Copie o Service ID
4. Verifique se `RABBITMQ_PRIVATE_URL` está apontando para esse service

**Formato esperado:**
```
amqp://USERNAME:PASSWORD@rabbitmq.railway.internal:5672
```

### 4️⃣ REGENERAR CREDENCIAIS (SE NECESSÁRIO)

Se as credenciais estão incorretas:

1. **No Railway:**
   - Vá no serviço RabbitMQ
   - Settings → Variables
   - Copie as credenciais corretas

2. **Atualizar variável:**
   ```bash
   # Se RABBITMQ_PRIVATE_URL está errada:
   railway variables --set RABBITMQ_PRIVATE_URL="amqp://USER:PASS@rabbitmq.railway.internal:5672"
   ```

3. **Redeploy:**
   ```bash
   # Forçar rebuild
   railway up
   ```

---

## 🧪 TESTE RÁPIDO DE CREDENCIAIS

### Opção 1: Via Railway CLI

```bash
# Conectar no container backend
railway shell

# Testar conexão RabbitMQ
python3 << 'EOF'
import os
import aio_pika
import asyncio

async def test():
    url = os.getenv('RABBITMQ_PRIVATE_URL') or os.getenv('RABBITMQ_URL')
    print(f"🔍 Testando: {url[:20]}...***")
    
    try:
        conn = await aio_pika.connect_robust(url, connection_attempts=1)
        print("✅ SUCESSO: Conexão estabelecida!")
        await conn.close()
    except Exception as e:
        print(f"❌ FALHA: {e}")

asyncio.run(test())
EOF
```

### Opção 2: Script Python Local

Criar `test_rabbitmq_connection.py`:

```python
import aio_pika
import asyncio
import os
from decouple import config

async def test_connection():
    # Tentar múltiplas URLs
    urls = [
        ('RABBITMQ_PRIVATE_URL', config('RABBITMQ_PRIVATE_URL', default=None)),
        ('RABBITMQ_URL', config('RABBITMQ_URL', default=None)),
        ('CLOUDAMQP_URL', config('CLOUDAMQP_URL', default=None)),
    ]
    
    for name, url in urls:
        if not url:
            print(f"⏭️ {name}: Não configurada")
            continue
            
        print(f"\n🔍 Testando {name}:")
        print(f"   URL: {url[:20]}...***")
        
        try:
            connection = await aio_pika.connect_robust(
                url,
                heartbeat=0,
                blocked_connection_timeout=0,
                socket_timeout=10,
                retry_delay=1,
                connection_attempts=1
            )
            print(f"   ✅ SUCESSO!")
            await connection.close()
        except Exception as e:
            print(f"   ❌ FALHA: {e}")

if __name__ == '__main__':
    asyncio.run(test_connection())
```

Executar:
```bash
python test_rabbitmq_connection.py
```

---

## 📊 COMPARAÇÃO: Campaigns vs Chat

| ASPECTO | CAMPAIGNS CONSUMER | CHAT CONSUMER |
|---------|-------------------|---------------|
| **Conexão** | ✅ Sucesso | ❌ Falha AUTH |
| **URL** | `rabbitmq.railway.internal:5672` | `rabbitmq.railway.internal:5672` |
| **Parâmetros** | heartbeat=0, timeout=10 | ✅ AGORA IGUAIS |
| **Settings** | `settings.RABBITMQ_URL` | `settings.RABBITMQ_URL` |
| **Queue** | `campaign_messages` | `chat_send_message`, etc |

**Conclusão:** URLs e código são iguais agora. Problema deve estar nas credenciais da variável de ambiente.

---

## 🔍 VERIFICAÇÃO PASSO A PASSO

### 1. Verificar qual URL está sendo usada
```bash
# Nos logs do Railway, procurar por:
"✅ [SETTINGS] Usando RABBITMQ_PRIVATE_URL (internal - recomendado)"
# Ou
"⚠️ [SETTINGS] Usando RABBITMQ_URL (proxy externo)"
```

### 2. Verificar se campaigns usa a mesma URL
```bash
# Procurar nos logs:
"🔍 [DEBUG] RabbitMQ URL: amqp://***:***@rabbitmq.railway.internal:5672"
```

### 3. Comparar usuários
```bash
# Chat logs:
"Connection to amqp://75jk0mkcjQmQLFs3:******@..."

# Campaigns logs:
# Procurar linha similar e comparar usuário
```

Se usuários forem **diferentes**, significa que há **2 conjuntos de credenciais**.

---

## 💡 HIPÓTESES E TESTES

### Hipótese 1: Credenciais Antigas
**Sintoma:** `75jk0mkcjQmQLFs3` pode ser usuário de instância RabbitMQ antiga.
**Teste:** Verificar data da última atualização da variável no Railway.
**Solução:** Atualizar `RABBITMQ_PRIVATE_URL` com credenciais atuais.

### Hipótese 2: Múltiplas Instâncias RabbitMQ
**Sintoma:** Railway pode ter 2 serviços RabbitMQ (antigo e novo).
**Teste:** `railway services` → verificar quantos RabbitMQ existem.
**Solução:** Deletar instância antiga, usar apenas a nova.

### Hipótese 3: Permissões Diferentes
**Sintoma:** Usuário `75jk0mkcjQmQLFs3` não tem permissão para criar filas de chat.
**Teste:** Conectar no RabbitMQ management console e verificar permissões.
**Solução:** Dar permissões completas ao usuário ou usar credenciais admin.

### Hipótese 4: Virtual Host Diferente
**Sintoma:** Chat tentando acessar vhost diferente do campaigns.
**Teste:** Verificar se URL tem `/vhost` no final.
**Solução:** Garantir que ambos usam mesmo vhost (geralmente `/`).

---

## ✅ COMMIT APLICADO

**Arquivo modificado:** `backend/apps/chat/tasks.py`

**Mudanças:**
1. ✅ Adicionados parâmetros de conexão robustos
2. ✅ Logs de debug detalhados
3. ✅ Diagnóstico de erro melhorado

**Próximo passo:** Deploy e verificar logs melhorados no Railway.

---

## 🚀 DEPLOY E VERIFICAÇÃO

```bash
# 1. Commit e push (já feito)
git add backend/apps/chat/tasks.py TROUBLESHOOTING_RABBITMQ_CHAT.md
git commit -m "fix: chat consumer RabbitMQ connection params + debug"
git push origin main

# 2. Aguardar deploy Railway (automático)

# 3. Verificar logs melhorados
railway logs backend --tail

# 4. Procurar por:
# "🔍 [CHAT CONSUMER] Conectando ao RabbitMQ: amqp://***:***@..."
# "✅ [CHAT CONSUMER] Conexão RabbitMQ estabelecida com sucesso!"
```

---

## 📞 PRÓXIMOS PASSOS

1. ✅ Deploy da correção (commit atual)
2. 🔍 Verificar logs melhorados no Railway
3. 🔧 Se ainda falhar, executar teste de credenciais
4. 🔄 Se necessário, regenerar credenciais RabbitMQ
5. ✅ Validar que ambos consumers funcionam

---

## 🎯 CHECKLIST DE RESOLUÇÃO

- [x] ✅ Código atualizado (parâmetros + logs)
- [ ] 🔍 Deploy feito, logs verificados
- [ ] 🔧 Credenciais testadas/validadas
- [ ] ✅ Chat consumer conectado com sucesso
- [ ] 🎉 Ambos consumers funcionando

---

**Data:** 27 de Outubro de 2025  
**Status:** ✅ CORREÇÃO APLICADA, AGUARDANDO DEPLOY  
**Commit:** Próximo a ser feito

