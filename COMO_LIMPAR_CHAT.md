# 🗑️ COMO LIMPAR TODOS OS DADOS DO CHAT

## ✅ PRÉ-REQUISITO

**OBRIGATÓRIO:** Desconectar as instâncias WhatsApp ANTES de limpar!

1. Acesse o painel do Evolution API
2. Delete ou desconecte todas as instâncias
3. OU desative no banco: `UPDATE connections_evolutionconnection SET is_active = false;`

---

## 🎯 DUAS OPÇÕES DISPONÍVEIS

### **Opção 1: Script Python (RECOMENDADO)** ⭐

**Vantagens:**
- ✅ Mais seguro (usa Django ORM)
- ✅ Respeita foreign keys automaticamente
- ✅ Transação atômica (tudo ou nada)
- ✅ Confirmação dupla obrigatória
- ✅ Mostra estatísticas antes e depois
- ✅ Modo dry-run disponível

**Uso:**
```bash
# 1. Ver estatísticas sem deletar
python clear_chat_database.py --dry-run

# 2. Limpar de verdade
python clear_chat_database.py

# Será pedido confirmação DUAS VEZES:
# - Digite "DELETAR"
# - Digite "SIM TENHO CERTEZA"
```

---

### **Opção 2: SQL Direto**

**Vantagens:**
- ✅ Mais rápido
- ✅ Pode usar em qualquer cliente SQL

**Desvantagens:**
- ⚠️ Menos seguro
- ⚠️ Precisa descomentar as linhas manualmente
- ⚠️ Sem confirmação automática

**Uso:**
```bash
# PostgreSQL local
psql -U postgres -d nome_do_banco -f clear_chat_database.sql

# Railway (via CLI)
railway run psql -f clear_chat_database.sql

# Ou copiar e colar no pgAdmin/DBeaver
```

**ATENÇÃO:** Você precisa descomentar as linhas de DELETE no arquivo SQL!

---

## 📊 O QUE SERÁ DELETADO

### ✅ Dados que SERÃO deletados:
- ✅ Todas as conversas (`chat_conversation`)
- ✅ Todas as mensagens (`chat_message`)
- ✅ Todos os anexos (`chat_attachment`)
- ✅ Relação de participantes (`chat_conversation_participants`)

### ❌ Dados que NÃO serão afetados:
- ✅ Usuários (`authn_user`)
- ✅ Departamentos (`authn_department`)
- ✅ Tenants (`tenancy_tenant`)
- ✅ Instâncias WhatsApp (`connections_evolutionconnection`)
- ✅ Produtos ativos (`products_*`)
- ✅ Configurações do sistema

---

## 🔢 ORDEM DE EXECUÇÃO

A ordem correta (respeitando foreign keys):

```
1. chat_attachment (anexos)
   ↓
2. chat_message (mensagens)
   ↓
3. chat_conversation_participants (many-to-many)
   ↓
4. chat_conversation (conversas)
```

Ambos os scripts respeitam essa ordem automaticamente.

---

## 🧪 TESTANDO ANTES

### **Script Python:**
```bash
# Apenas ver estatísticas
python clear_chat_database.py --dry-run
```

### **SQL:**
```sql
-- Ver estatísticas (execute apenas esta parte)
SELECT 
    'Anexos' as tabela,
    COUNT(*) as total
FROM chat_attachment
UNION ALL
SELECT 
    'Mensagens' as tabela,
    COUNT(*) as total
FROM chat_message
UNION ALL
SELECT 
    'Conversas' as tabela,
    COUNT(*) as total
FROM chat_conversation;
```

---

## 🚀 PASSO A PASSO COMPLETO

### **1. Desconectar instâncias WhatsApp**
```sql
-- Via SQL
UPDATE connections_evolutionconnection 
SET is_active = false 
WHERE is_active = true;

-- OU via Evolution API dashboard
```

### **2. Ver estatísticas atuais**
```bash
python clear_chat_database.py --dry-run
```

### **3. Fazer backup (OPCIONAL mas recomendado)**
```bash
# Backup apenas tabelas do chat
pg_dump -U postgres -d nome_do_banco \
  -t chat_conversation \
  -t chat_message \
  -t chat_attachment \
  -t chat_conversation_participants \
  > backup_chat_$(date +%Y%m%d_%H%M%S).sql
```

### **4. Limpar dados**
```bash
python clear_chat_database.py
# Digite "DELETAR"
# Digite "SIM TENHO CERTEZA"
```

### **5. Fazer deploy do código corrigido**
```bash
git add .
git commit -m "fix: Corrigir nomes de contatos e grupos no webhook"
git push
```

### **6. Reconectar instâncias WhatsApp**
- Acesse Evolution API
- Crie/reconecte as instâncias
- Configure webhooks
- Escaneie QR codes

---

## ⚠️ TROUBLESHOOTING

### **Erro: "permission denied"**
```bash
# Conectar como superuser
psql -U postgres -d nome_do_banco
```

### **Erro: "violates foreign key constraint"**
```bash
# O script Python resolve isso automaticamente
# Se usar SQL, verifique a ordem: anexos → mensagens → conversas
```

### **Erro: "database is locked"**
```bash
# Desconectar instâncias e parar workers
# Railway: railway down
```

---

## 📋 CHECKLIST PÓS-LIMPEZA

Depois de limpar e fazer deploy:

- [ ] Verificar estatísticas (deve estar zerado)
- [ ] Reconectar instâncias WhatsApp
- [ ] Enviar mensagem de teste para você mesmo
- [ ] Verificar se nome aparece correto
- [ ] Verificar se foto aparece
- [ ] Testar grupo novo
- [ ] Verificar logs do webhook

---

## 💡 DICA

Use o script Python (`clear_chat_database.py`) - é mais seguro e tem confirmações múltiplas para evitar acidentes! 😉

---

## 🎯 RESUMO RÁPIDO

```bash
# MODO SEGURO (recomendado):
python clear_chat_database.py --dry-run    # Ver antes
python clear_chat_database.py              # Limpar

# Depois:
git add .
git commit -m "fix: Corrigir webhook + limpar chat"
git push
```

**Pronto! Sistema zerado e corrigido! 🎉**

