# 🔧 Solução: Erro de Build do Frontend no Railway

## ❌ Erro Encontrado

```
Build Failed: build daemon returned an error < failed to solve: failed to read dockerfile: open frontend/Dockerfile: no such file or directory >
```

## 🔍 Causa do Problema

O Railway está procurando `frontend/Dockerfile` a partir da raiz do projeto, mas a configuração pode estar incorreta. Existem duas possibilidades:

1. **Railway configurado na interface** com Root Directory errado
2. **Arquivo `railway.frontend.json` não está sendo usado** (Railway ignora se houver config na interface)

## ✅ Soluções

### Solução 1: Configurar na Interface do Railway (RECOMENDADO)

1. Acesse o Railway Dashboard
2. Vá no serviço do **Frontend**
3. Clique em **Settings → Build & Deploy**
4. Configure:
   - **Root Directory:** `frontend`
   - **Dockerfile Path:** `Dockerfile` (relativo ao root directory)
   - **Start Command:** `node serve.js`
   - **Build Command:** (deixar vazio - usa Dockerfile)

### Solução 2: Usar arquivo `railway.frontend.json`

O arquivo `railway.frontend.json` já foi criado na raiz do projeto com a configuração correta:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "context": "frontend",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "startCommand": "node serve.js"
  }
}
```

**IMPORTANTE:** Se você configurar na interface, o arquivo JSON será **IGNORADO**. Escolha UMA abordagem!

### Solução 3: Verificar se o Dockerfile está no Git

Execute:
```bash
git ls-files frontend/Dockerfile
```

Se não aparecer nada, o arquivo não está sendo commitado. Adicione:
```bash
git add frontend/Dockerfile
git commit -m "fix: add frontend Dockerfile to git"
git push
```

## 🎯 Configuração Correta

### Backend (já configurado)
- Root Directory: `.` (raiz)
- Dockerfile Path: `backend/Dockerfile`

### Frontend (precisa configurar)
- Root Directory: `frontend`
- Dockerfile Path: `Dockerfile`
- Start Command: `node serve.js`

## 📋 Checklist

- [ ] Verificar se `frontend/Dockerfile` existe e está no Git
- [ ] Configurar Root Directory = `frontend` na interface OU usar `railway.frontend.json`
- [ ] Verificar se não há configurações conflitantes na interface
- [ ] Fazer commit e push do `railway.frontend.json` (se usar essa abordagem)
- [ ] Tentar build novamente no Railway

## 🚨 Se Ainda Não Funcionar

1. **Limpar configuração na interface:**
   - Remover TODAS as configurações de Build & Deploy na interface
   - Deixar apenas o arquivo JSON

2. **Ou limpar arquivo JSON:**
   - Deletar `railway.frontend.json`
   - Configurar TUDO na interface

3. **Verificar logs completos:**
   - Railway Dashboard → Deployments → View Logs
   - Procurar por erros específicos

## 📚 Referências

- Ver `RAILWAY_CONFIG.md` para documentação completa
- Ver `railway.backend.json` como exemplo de configuração do backend

