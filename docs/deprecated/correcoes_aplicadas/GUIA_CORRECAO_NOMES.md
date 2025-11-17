# 🔧 GUIA DE CORREÇÃO - Nomes de Contatos Errados

## 🐛 PROBLEMA IDENTIFICADO

**Sintoma:** Conversas mostram SEU nome (Paulo Bernal) ao invés do nome do contato.

**Causa:** Bug no webhook - quando VOCÊ envia a primeira mensagem para um contato, o sistema salvava seu nome (`pushName`) ao invés de buscar o nome correto do contato via API.

**Status:** ✅ **BUG CORRIGIDO** - Novas conversas agora funcionarão corretamente.

---

## 📋 PASSO A PASSO

### **Opção 1: Começar do Zero (Recomendado)** 🔥

Se você quer começar limpo, sem conversas antigas:

```bash
# 1. Ver estatísticas antes de deletar
python reset_conversations.py --dry-run

# 2. Resetar TODAS as conversas (IRREVERSÍVEL!)
python reset_conversations.py --all

# 3. Ou resetar apenas 1 tenant (modo interativo)
python reset_conversations.py
```

**✅ Vantagens:**
- Sistema zerado e limpo
- Sem dados incorretos
- Todas as novas conversas terão nomes/fotos corretos

**❌ Desvantagens:**
- Perde histórico de mensagens
- Perde conversas antigas

---

### **Opção 2: Corrigir Conversas Existentes** 🔧

Se você quer MANTER as conversas e apenas corrigir os nomes:

```bash
# 1. Ver o que seria corrigido (dry-run)
python fix_contact_names.py --dry-run

# 2. Corrigir de verdade
python fix_contact_names.py

# 3. Ou corrigir apenas 1 tenant
python fix_contact_names.py --tenant-id UUID_DO_TENANT
```

**✅ Vantagens:**
- Mantém histórico de mensagens
- Mantém conversas antigas
- Corrige apenas os nomes errados

**❌ Desvantagens:**
- Conversas antigas continuam lá (mesmo se vazias)
- Pode ter dados inconsistentes

---

### **Opção 3: Diagnosticar Primeiro** 🔍

Se você quer ver o estado atual antes de decidir:

```bash
# Ver estatísticas completas
python diagnose_duplicates.py
```

**O que mostra:**
- Total de conversas por tenant
- Contatos duplicados (se houver)
- Conversas por tipo (individual/grupo)
- Conversas por status (open/pending/closed)
- Conversas órfãs (sem instância)

---

## 🚀 RECOMENDAÇÃO

Para seu caso específico, recomendo:

```bash
# 1. Ver o estado atual
python diagnose_duplicates.py

# 2. Se tiver poucas conversas importantes: RESETAR TUDO
python reset_conversations.py --all

# 3. Se tiver muitas conversas importantes: CORRIGIR
python fix_contact_names.py

# 4. (Opcional) Desconectar e reconectar instâncias para recomeçar fresh
```

---

## 🔒 SEGURANÇA

**Todos os scripts têm proteções:**
- ✅ `--dry-run` para ver antes de fazer
- ✅ Confirmação obrigatória para deletar
- ✅ Transações atômicas (tudo ou nada)
- ✅ Logs detalhados do que está acontecendo

---

## 🐞 O QUE FOI CORRIGIDO NO CÓDIGO

### **Backend - `webhooks.py`**

**ANTES (❌ Bug):**
```python
defaults = {
    'contact_name': push_name,  # ← Salvava quem ENVIOU
}
```

**DEPOIS (✅ Correto):**
```python
# Só usar pushName se mensagem veio do contato
contact_name_to_save = push_name if not from_me else ''

defaults = {
    'contact_name': contact_name_to_save,  # ← Vazio se você enviou
}

# Depois busca o nome correto via API Evolution
# Endpoint: POST /chat/whatsappNumbers/{instance}
# Body: {"numbers": ["5517999999999"]}
```

---

## 📊 COMPORTAMENTO AGORA

### **Cenário 1: Contato envia primeira mensagem**
1. Webhook recebe `pushName` = nome do contato ✅
2. Sistema salva o nome corretamente
3. Busca foto via API
4. Tudo OK! 🎉

### **Cenário 2: VOCÊ envia primeira mensagem**
1. Webhook recebe `pushName` = SEU nome
2. Sistema **ignora** o pushName ✅
3. Busca nome correto via API Evolution
4. Busca foto via API
5. Salva nome e foto corretos
6. Tudo OK! 🎉

### **Cenário 3: Grupos**
1. Sempre ignora `pushName` (é de quem enviou no grupo)
2. Busca nome e foto via `/group/findGroupInfos`
3. Salva "Grupo WhatsApp" enquanto busca
4. Atualiza com nome/foto reais
5. Tudo OK! 🎉

---

## 🧪 TESTAR APÓS DEPLOY

### **Teste 1: Criar conversa nova enviando mensagem**
1. Escolha um contato que NÃO tem conversa ainda
2. Envie mensagem pelo WhatsApp
3. Verifique no Flow Chat se o nome está CORRETO (não seu nome)

### **Teste 2: Receber mensagem de contato novo**
1. Peça para alguém te enviar mensagem
2. Verifique se nome e foto aparecem corretos

### **Teste 3: Grupo novo**
1. Entre em um grupo novo
2. Envie ou receba mensagem
3. Verifique se nome do grupo e foto aparecem

---

## 📞 SCRIPTS DISPONÍVEIS

| Script | Função | Reversível? |
|--------|--------|-------------|
| `reset_conversations.py` | Deleta TODAS as conversas | ❌ NÃO |
| `fix_contact_names.py` | Corrige nomes via API | ✅ SIM |
| `diagnose_duplicates.py` | Apenas visualiza estatísticas | ✅ SIM (read-only) |

---

## ✅ PRÓXIMOS PASSOS

1. **Executar um dos scripts acima**
2. **Fazer commit e deploy:**
   ```bash
   git add backend/apps/chat/webhooks.py
   git commit -m "fix: Corrigir nome de contatos - não usar pushName quando from_me=True"
   git push
   ```
3. **Testar no Railway depois do deploy**
4. **Monitorar logs para confirmar que está funcionando**

---

**🎯 Qual opção você quer seguir?**

