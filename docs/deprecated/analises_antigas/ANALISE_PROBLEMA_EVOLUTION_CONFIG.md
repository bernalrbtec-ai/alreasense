# 🔍 ANÁLISE: Problema na Tela Servidor de Instância

**Data:** 27 de Outubro de 2025  
**Problema Reportado:**
1. ❌ Vem erro na informação de conexão
2. ❌ Não vem os dados da instância

---

## 📊 ANÁLISE DE COMPATIBILIDADE

### ✅ Backend → Frontend (COMPATÍVEL)

**Backend retorna:**
```json
{
  "status": "error" | "active" | "inactive",
  "last_check": "2025-10-27T14:30:00Z",
  "last_error": "Mensagem de erro aqui",
  "webhook_url": "https://...railway.app/webhooks/evolution/",
  "statistics": {
    "total": 0,
    "connected": 0,
    "disconnected": 0
  },
  "instances": []
}
```

**Frontend espera:**
```typescript
interface EvolutionStats {
  status: 'active' | 'inactive' | 'error'
  last_check: string
  last_error?: string | null
  webhook_url: string
  statistics: { total, connected, disconnected }
  instances: InstanceData[]
}
```

**Conclusão:** ✅ **COMPATÍVEL** - Estruturas são idênticas!

---

## 🚨 CAUSAS PROVÁVEIS DO ERRO

### 🔴 Causa #1: Variáveis de Ambiente NÃO CONFIGURADAS

**Código Backend (views.py:40-41):**
```python
base_url = settings.EVOLUTION_API_URL  # Busca de EVO_BASE_URL
api_key = settings.EVOLUTION_API_KEY    # Busca de EVO_API_KEY
```

**Código Backend (views.py:51-64):**
```python
if not base_url or not api_key:
    return Response({
        'status': 'inactive',
        'last_error': 'Configuração não encontrada no .env (EVOLUTION_API_URL ou EVOLUTION_API_KEY)',
        'webhook_url': webhook_url,
        'statistics': { 'total': 0, 'connected': 0, 'disconnected': 0 },
        'instances': [],
    })
```

**Verificação no Railway:**
```bash
# Verificar se essas variáveis EXISTEM:
EVO_BASE_URL=https://evo.rbtec.com.br
EVO_API_KEY=SUA-CHAVE-AQUI
```

**Se NÃO EXISTIREM → Frontend mostrará:**
- Status: ⚪ Desconectado
- Erro: "Configuração não encontrada no .env"
- Instâncias: 0 (array vazio)

---

### 🟡 Causa #2: API KEY INCORRETA (401)

**Código Backend (views.py:114-117):**
```python
elif response.status_code == 401:
    connection_status = 'error'
    last_error = 'Erro de autenticação (401) - Verifique EVOLUTION_API_KEY no .env'
```

**Se API Key estiver ERRADA → Frontend mostrará:**
- Status: 🔴 Erro de Conexão
- Erro: "Erro de autenticação (401) - Verifique EVOLUTION_API_KEY no .env"
- Instâncias: 0 (array vazio)

---

### 🟠 Causa #3: Estrutura da Resposta Evolution API MUDOU

**Código Backend (views.py:93-105):**
```python
for inst in instances:
    # Assume estrutura: { "instance": { "instanceName": "...", "status": "..." } }
    instance_name = inst.get('instance', {}).get('instanceName', 'Unknown')
    instance_status = inst.get('instance', {}).get('status', 'unknown')
```

**Estrutura ESPERADA da Evolution API:**
```json
[
  {
    "instance": {
      "instanceName": "RBTec",
      "status": "open"
    }
  }
]
```

**Se a estrutura for DIFERENTE:**
```json
[
  {
    "instanceName": "RBTec",  // ❌ Direto no root, não em "instance"
    "status": "open"
  }
]
```

**Resultado:** Todas as instâncias apareceriam como "Unknown" com status "unknown".

---

### 🔵 Causa #4: Evolution API NÃO RESPONDE / TIMEOUT

**Código Backend (views.py:123-126):**
```python
except requests.exceptions.Timeout:
    connection_status = 'error'
    last_error = 'Timeout na conexão com Evolution API (10s)'
```

**Se Evolution API não responder em 10s → Frontend mostrará:**
- Status: 🔴 Erro de Conexão
- Erro: "Timeout na conexão com Evolution API (10s)"
- Instâncias: 0

---

## 🔎 COMO DIAGNOSTICAR

### 1️⃣ Verificar Variáveis de Ambiente

```bash
# No Railway → Backend → Variables
# Procurar por:
EVO_BASE_URL
EVO_API_KEY

# Se NÃO EXISTIREM → ESSE É O PROBLEMA!
```

### 2️⃣ Verificar Logs Backend

```bash
railway logs backend --tail
```

**Procurar por:**

```
# Se variáveis não configuradas:
⚠️ [EVOLUTION CONFIG] Variáveis de ambiente não configuradas

# Se tudo ok:
🔍 [EVOLUTION CONFIG] Buscando instâncias em: https://evo.rbtec.com.br
✅ [EVOLUTION CONFIG] 3 instâncias encontradas

# Se erro 401:
❌ [EVOLUTION CONFIG] Erro de autenticação (401) - Verifique EVOLUTION_API_KEY

# Se timeout:
❌ [EVOLUTION CONFIG] Timeout na conexão com Evolution API (10s)
```

### 3️⃣ Testar API Manualmente

```bash
# No seu terminal ou Postman:
curl -X GET https://evo.rbtec.com.br/instance/fetchInstances \
  -H "apikey: SUA-CHAVE-AQUI"
```

**Response esperada:**
```json
[
  {
    "instance": {
      "instanceName": "RBTec",
      "status": "open"
    }
  }
]
```

---

## 📋 CHECKLIST DE VERIFICAÇÃO

- [ ] ✅ Variável `EVO_BASE_URL` existe no Railway?
- [ ] ✅ Variável `EVO_API_KEY` existe no Railway?
- [ ] ✅ `EVO_BASE_URL` está correto? (https://evo.rbtec.com.br)
- [ ] ✅ `EVO_API_KEY` está válida? (testar com curl)
- [ ] ✅ Evolution API está online e respondendo?
- [ ] ✅ Estrutura da resposta está correta?
- [ ] ✅ Logs backend mostram sucesso?

---

## 🎯 SOLUÇÃO MAIS PROVÁVEL

### 🚨 95% de chance: VARIÁVEIS NÃO CONFIGURADAS

O commit `13a9967` mudou de:
```python
# ANTES
EVOLUTION_API_URL = config('EVOLUTION_API_URL', ...)
EVOLUTION_API_KEY = config('EVOLUTION_API_KEY', ...)
```

Para:
```python
# DEPOIS
EVOLUTION_API_URL = config('EVO_BASE_URL', ...)  # ← Mudou o nome!
EVOLUTION_API_KEY = config('EVO_API_KEY', ...)    # ← Mudou o nome!
```

**MAS:** Se as variáveis `EVO_BASE_URL` e `EVO_API_KEY` **NÃO EXISTEM** no Railway, o backend vai retornar erro!

---

## ✅ SOLUÇÃO IMEDIATA (SEM CODAR)

### Opção 1: Adicionar Variáveis no Railway

```bash
# Railway → Backend → Variables → Add Variable

EVO_BASE_URL=https://evo.rbtec.com.br
EVO_API_KEY=SUA-CHAVE-EVOLUTION-API-AQUI
```

### Opção 2: Verificar se já existem com OUTRO NOME

Se no Railway existem:
```
EVOLUTION_API_URL=https://evo.rbtec.com.br
EVOLUTION_API_KEY=SUA-CHAVE
```

Mas o código busca:
```
EVO_BASE_URL  # ← Nome diferente!
EVO_API_KEY   # ← Nome diferente!
```

**Solução:** Criar as variáveis com os nomes corretos ou ajustar o código.

---

## 📊 TABELA DE SINTOMAS vs CAUSAS

| SINTOMA NO FRONTEND | CAUSA MAIS PROVÁVEL |
|---------------------|---------------------|
| ⚪ Desconectado + "Configuração não encontrada" | Variáveis `EVO_*` não existem |
| 🔴 Erro + "401 - autenticação" | `EVO_API_KEY` incorreta |
| 🔴 Erro + "Timeout" | Evolution API offline ou lento |
| 🔴 Erro + "HTTP 500" | Evolution API com problema |
| ✅ Conectado mas 0 instâncias | Estrutura da resposta mudou |
| ✅ Conectado mas instâncias "Unknown" | Estrutura da resposta mudou |

---

## 🔧 PRÓXIMOS PASSOS

1. **Verificar logs Railway** (passo 2️⃣)
2. **Verificar variáveis de ambiente** (passo 1️⃣)
3. **Se variáveis não existem:** Adicionar `EVO_BASE_URL` e `EVO_API_KEY`
4. **Se variáveis existem mas ainda falha:** Testar API manualmente (passo 3️⃣)
5. **Enviar resultado dos logs** para ajuste fino

---

**Status:** 📋 **ANÁLISE COMPLETA SEM CODAR**  
**Próxima Ação:** Verificar logs e variáveis Railway

