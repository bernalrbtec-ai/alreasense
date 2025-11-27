# 🚂 Configuração Railway - Documentação

## ⚠️ IMPORTANTE: Como o Railway Funciona

O Railway pode usar **configurações de 3 lugares diferentes** (em ordem de prioridade):

1. **Interface do Railway** (Settings → Build & Deploy) - **MAIOR PRIORIDADE**
2. **Arquivo `railway.json` na raiz do projeto**
3. **Arquivo específico do serviço** (`railway.frontend.json`, `railway.backend.json`)

**PROBLEMA:** Se você configurar na interface, os arquivos JSON são **IGNORADOS**!

## 📁 Estrutura de Arquivos

```
/
├── railway.json              # Configuração padrão (usado se não houver config na interface)
├── railway.frontend.json     # Configuração específica do frontend
├── railway.backend.json     # Configuração específica do backend
├── frontend/
│   └── Dockerfile           # Dockerfile do frontend
└── backend/
    └── Dockerfile           # Dockerfile do backend
```

## 🔧 Configuração Correta

### Frontend Service

**Na Interface do Railway:**
- Root Directory: `frontend`
- Build Command: (deixar vazio - usa Dockerfile)
- Start Command: `node serve.js`
- Dockerfile Path: `Dockerfile` (relativo ao root directory)

**OU usar `railway.frontend.json`:**
```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "node serve.js"
  }
}
```

### Backend Service

**Na Interface do Railway:**
- Root Directory: `.` (raiz do projeto)
- Build Command: (deixar vazio - usa Dockerfile)
- Start Command: (definido no Dockerfile)
- Dockerfile Path: `backend/Dockerfile`

**OU usar `railway.backend.json`:**
```json
{
  "build": {
    "builder": "DOCKERFILE",
    "context": ".",
    "dockerfilePath": "backend/Dockerfile"
  }
}
```

## ⚠️ REGRA DE OURO

**NUNCA configure na interface E nos arquivos JSON ao mesmo tempo!**

Escolha UMA abordagem:
- ✅ **Opção 1:** Configurar TUDO na interface do Railway (recomendado)
- ✅ **Opção 2:** Configurar TUDO nos arquivos JSON (deixar interface vazia)

## 🔍 Como Verificar

1. Acesse Railway Dashboard
2. Vá em Settings → Build & Deploy
3. Verifique se há configurações definidas
4. Se houver, elas têm PRIORIDADE sobre os arquivos JSON

## 🛠️ Solução de Problemas

### Build falha com "Dockerfile not found"

**Causa:** Root Directory não corresponde ao caminho do Dockerfile

**Solução:**
- Frontend: Root = `frontend`, Dockerfile = `Dockerfile`
- Backend: Root = `.`, Dockerfile = `backend/Dockerfile`

### Configuração muda sozinha

**Causa:** Alguém alterou na interface do Railway

**Solução:** Documentar qual abordagem usar e não misturar

