# 🔧 PASSO A PASSO - CONFIGURAR S3 NO RAILWAY

**Problema:** Backend não consegue acessar MinIO (erro 403)  
**Causa:** Faltam variáveis de ambiente S3_* no serviço Backend  
**Solução:** Adicionar 5 variáveis no Railway

---

## 📋 CHECKLIST

### ✅ Etapa 1: Acessar Railway Dashboard

1. Acesse https://railway.app/
2. Faça login
3. Selecione o projeto "alreasense"

---

### ✅ Etapa 2: Ir para o Serviço Backend

1. Clique no serviço **"Backend"** (o que roda Django)
2. Clique na aba **"Variables"**

---

### ✅ Etapa 3: Adicionar Variáveis

Clique em **"New Variable"** e adicione CADA uma destas (copie e cole):

#### Variável 1:
```
Nome: S3_ENDPOINT_URL
Valor: https://bucket-production-8fb1.up.railway.app
```

#### Variável 2:
```
Nome: S3_ACCESS_KEY
Valor: u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL
```

#### Variável 3:
```
Nome: S3_SECRET_KEY
Valor: zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti
```

#### Variável 4:
```
Nome: S3_BUCKET
Valor: alrea-media
```

#### Variável 5:
```
Nome: S3_REGION
Valor: us-east-1
```

---

### ✅ Etapa 4: Deploy Automático

Após adicionar as 5 variáveis:
1. Railway vai fazer **deploy automático** (~2-3 minutos)
2. Aguarde aparecer "Deployed" (bolinha verde)

---

### ✅ Etapa 5: Verificar Logs

No Railway, vá em **"Deployments"** → Clique no último deploy → **"View Logs"**

**Procure por:**
```
✅ [S3] Bucket 'alrea-media' já existe
```

**OU (se bucket não existir ainda):**
```
⚠️ [S3] Bucket 'alrea-media' não existe, tentando criar...
✅ [S3] Bucket 'alrea-media' criado com sucesso
```

---

### ✅ Etapa 6: Testar Upload

1. Abra o chat no Alrea Sense
2. Tente enviar uma imagem
3. ✅ **Deve funcionar sem erro 403!**

---

## 🚨 TROUBLESHOOTING

### Ainda aparecer erro 403?

**Verificar:**
1. S3_ACCESS_KEY e S3_SECRET_KEY estão **exatamente iguais** ao MinIO
2. MinIO está rodando (railway ps)
3. Aguardar 2-3 minutos após adicionar variáveis (deploy pode demorar)

**Comando para verificar variáveis no Railway:**
```bash
railway variables list
```

---

### Erro 404 (Bucket não encontrado)?

**Solução:**
- O bucket será criado automaticamente na primeira vez
- Aguarde 1-2 minutos
- Tente enviar arquivo novamente

---

### Erro de conexão?

**Verificar:**
- S3_ENDPOINT_URL está correto: `https://bucket-production-8fb1.up.railway.app`
- MinIO está respondendo: Abra a URL no navegador
- Se abrir console do MinIO = funcionando ✅

---

## 📊 RESULTADO ESPERADO

### Antes (❌):
```
❌ [S3] Erro ao verificar bucket: 403
❌ [S3] Não foi possível garantir que o bucket existe
```

### Depois (✅):
```
✅ [S3] Bucket 'alrea-media' já existe
📎 [S3] Gerando presigned URL para upload...
✅ [S3] Presigned URL gerada com sucesso
```

---

## 🎯 RESUMO

| Variável | Valor |
|----------|-------|
| S3_ENDPOINT_URL | https://bucket-production-8fb1.up.railway.app |
| S3_ACCESS_KEY | u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL |
| S3_SECRET_KEY | zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti |
| S3_BUCKET | alrea-media |
| S3_REGION | us-east-1 |

**Total:** 5 variáveis para adicionar no serviço Backend

---

**Qualquer dúvida, me chame!** 🚀

