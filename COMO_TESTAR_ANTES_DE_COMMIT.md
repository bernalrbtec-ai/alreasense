# 🧪 Como Testar ANTES de Fazer Commit

## ⚠️ REGRA CRÍTICA

> **"Sempre criar scripts de teste e executar simulações locais ANTES de fazer commit/push de mudanças no código. Nunca subir código sem testar primeiro."**

---

## 🚀 Uso Rápido

### Antes de QUALQUER commit, execute:

```bash
python pre_commit_validation.py
```

Se tudo passar ✅ → **PODE FAZER COMMIT**  
Se algo falhar ❌ → **CORRIJA ANTES DE COMMITAR**

---

## 🔍 O que é Validado?

### 1. ✅ Backend
- **Django System Check** - Verifica configurações e models
- **Migrations Pendentes** - Detecta mudanças não migradas
- **Endpoints de Billing** - Testa todas as 6 APIs
- **Imports Python** - Valida imports não utilizados

### 2. ✅ Frontend  
- **TypeScript** - Validação de tipos
- **Imports** - Detecta paths incorretos (`./api` vs `../lib/api`)
- **Array Methods** - Verifica se usa `Array.isArray()` antes de `.filter()` e `.map()`
- **Estados** - Detecta `useState` faltantes

### 3. ✅ Database
- **Estrutura** - Verifica se tabelas estão alinhadas com models
- **Colunas** - Detecta colunas faltantes ou extras
- **Relacionamentos** - Valida foreign keys

---

## 📊 Exemplo de Saída

```
================================================================================
                      🚀 VALIDAÇÃO PRE-COMMIT - ALREA SENSE                      
================================================================================

Regra: Sempre testar ANTES de commit/push

================================================================================
                              VALIDANDO BACKEND                                 
================================================================================

ℹ️  Executando: Django System Check
✅ Django System Check - OK

ℹ️  Executando: Verificar se há migrations pendentes
✅ Verificar se há migrations pendentes - OK

ℹ️  Executando: Testar endpoints de billing
✅ Testar endpoints de billing - OK

                           Resultados dos Testes                           
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Endpoint                    ┃ Status ┃ Descrição          ┃ Resultado    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ /api/billing/products/      │ ✅     │ Lista de produtos  │ 3 itens      │
│ /api/billing/plans/         │ ✅     │ Lista de planos    │ 4 itens      │
└─────────────────────────────┴────────┴────────────────────┴──────────────┘

================================================================================
                              RESUMO DA VALIDAÇÃO                               
================================================================================

✅ Backend: APROVADO
✅ Frontend: APROVADO  
✅ Database: APROVADO

================================================================================
                      ✅ TODAS AS VALIDAÇÕES PASSARAM!                         
                       SEGURO PARA FAZER COMMIT E PUSH                          
================================================================================
```

---

## 🎯 Fluxo de Trabalho Correto

### ❌ ERRADO (Antes):
```bash
git add .
git commit -m "mudanças"
git push
# 💥 Erro em produção!
```

### ✅ CORRETO (Agora):
```bash
# 1. Fazer alterações no código
# 2. TESTAR ANTES
python pre_commit_validation.py

# 3. Se tudo passar:
git add .
git commit -m "mudanças validadas"
git push

# 4. Se falhar: CORRIGIR e testar novamente
```

---

## 🔧 Scripts de Teste Disponíveis

### Backend
- `test_billing_endpoints.py` - Testa APIs de billing
- `review_and_fix_database.py` - Valida banco
- `check_*.py` - Verificações específicas

### Validação Completa
- `pre_commit_validation.py` - **USAR SEMPRE**

---

## 💡 Problemas que Este Sistema Previne

### ✅ Detecta ANTES do commit:
- ❌ Campos que não existem no banco (`is_enterprise`, `is_addon_available`)
- ❌ Endpoints 404 (`/billing/info/`)
- ❌ Estados faltantes (`isSaving`)
- ❌ Imports incorretos (`./api` vs `../lib/api`)
- ❌ Métodos em null/undefined (`.filter()` sem validação)
- ❌ Migrations não aplicadas
- ❌ Erros de tipo TypeScript

---

## 🎓 Integração com Git Hooks (Opcional)

Para automatizar ainda mais, crie `.git/hooks/pre-commit`:

```bash
#!/bin/bash
echo "🔍 Validando mudanças antes do commit..."
python pre_commit_validation.py

if [ $? -ne 0 ]; then
    echo "❌ Validação falhou! Commit bloqueado."
    exit 1
fi

echo "✅ Validação passou! Prosseguindo com commit..."
```

Torne executável:
```bash
chmod +x .git/hooks/pre-commit
```

Agora o Git **bloqueia automaticamente** commits com erros!

---

## 📝 Checklist Manual Adicional

Antes de commit/push, sempre verificar:

- [ ] Docker rodando sem erros
- [ ] Testes passando (`python pre_commit_validation.py`)
- [ ] Endpoints testados manualmente
- [ ] Frontend carrega sem erros no console
- [ ] Dados no banco consistentes
- [ ] Migrations aplicadas

---

**Moral da história:** 
🧪 **TESTE ANTES, COMMIT DEPOIS!** 🚀

