# 📋 COPIAR E COLAR - VARIÁVEIS S3 (RAILWAY)

## 🎯 PASSO 1: Verificar Nome do Serviço MinIO

No Railway Dashboard, veja o nome EXATO do serviço MinIO.

**Possibilidades:**
- `Minio` (com M maiúsculo)
- `minio` (tudo minúsculo)
- `MinIO`

---

## 📝 PASSO 2: Copiar e Colar (Use o correto para seu caso)

### ✅ SE O SERVIÇO SE CHAMA "Minio" (copie estas 5 linhas):

```
S3_ENDPOINT_URL=${{Minio.MINIO_PRIVATE_ENDPOINT}}
S3_ACCESS_KEY=${{Minio.MINIO_ROOT_USER}}
S3_SECRET_KEY=${{Minio.MINIO_ROOT_PASSWORD}}
S3_BUCKET=alrea-media
S3_REGION=us-east-1
```

### ✅ SE O SERVIÇO SE CHAMA "minio" (copie estas 5 linhas):

```
S3_ENDPOINT_URL=${{minio.MINIO_PRIVATE_ENDPOINT}}
S3_ACCESS_KEY=${{minio.MINIO_ROOT_USER}}
S3_SECRET_KEY=${{minio.MINIO_ROOT_PASSWORD}}
S3_BUCKET=alrea-media
S3_REGION=us-east-1
```

### ✅ SE O SERVIÇO SE CHAMA "MinIO" (copie estas 5 linhas):

```
S3_ENDPOINT_URL=${{MinIO.MINIO_PRIVATE_ENDPOINT}}
S3_ACCESS_KEY=${{MinIO.MINIO_ROOT_USER}}
S3_SECRET_KEY=${{MinIO.MINIO_ROOT_PASSWORD}}
S3_BUCKET=alrea-media
S3_REGION=us-east-1
```

---

## 🔧 PASSO 3: Adicionar no Railway

### Via UI (Mais Fácil):

1. Railway Dashboard → Serviço "Backend"
2. Aba "Variables"
3. Clique "New Variable"
4. **Para cada linha:**
   - Antes do `=` → Nome da variável
   - Depois do `=` → Valor
5. Clique "Add" para cada uma
6. Aguarde deploy (2-3 min)

### Exemplo:
```
Nome: S3_ENDPOINT_URL
Valor: ${{Minio.MINIO_PRIVATE_ENDPOINT}}
```

---

## ⚠️ SE DER ERRO COM VARIABLE REFERENCES

Use valores diretos (menos recomendado):

```
S3_ENDPOINT_URL=https://bucket-production-8fb1.up.railway.app
S3_ACCESS_KEY=u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL
S3_SECRET_KEY=zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti
S3_BUCKET=alrea-media
S3_REGION=us-east-1
```

---

## ✅ VERIFICAR SE FUNCIONOU

Após deploy, abra logs do Backend:

**Procure por:**
```
✅ [S3] Bucket 'alrea-media' já existe
```

**Se aparecer:**
```
⚠️ [S3] Bucket 'alrea-media' não existe, tentando criar...
✅ [S3] Bucket 'alrea-media' criado com sucesso
```

**Perfeito!** Bucket foi criado automaticamente.

---

## 🎉 TESTE FINAL

1. Abra o chat
2. Tente enviar uma imagem
3. ✅ Deve funcionar sem erro 403!

---

**Dúvidas? Me chame!** 🚀

