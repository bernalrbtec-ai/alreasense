# 🗑️ Como Limpar o Histórico do Chat no Railway

## Método 1: Via Railway Dashboard (Recomendado)

1. Acesse o **Railway Dashboard**
2. Vá no serviço **backend**
3. Clique em **Settings** → **Shell**
4. Execute o comando:
   ```bash
   cd backend && python clear_chat_history.py
   ```

## Método 2: Via Railway CLI Local

Se você tiver o Railway CLI configurado:

```bash
# Entrar no shell do Railway
railway shell

# Dentro do shell, execute:
cd backend && python clear_chat_history.py
```

## Método 3: SQL Direto (Mais Rápido)

Se preferir executar SQL direto no banco Railway:

```sql
-- 1. Deletar anexos
DELETE FROM chat_messageattachment;

-- 2. Deletar mensagens
DELETE FROM chat_message;

-- 3. Deletar conversas
DELETE FROM chat_conversation;

-- 4. Verificar
SELECT 
    (SELECT COUNT(*) FROM chat_conversation) as conversas,
    (SELECT COUNT(*) FROM chat_message) as mensagens,
    (SELECT COUNT(*) FROM chat_messageattachment) as anexos;
```

## ✅ Resultado Esperado

```
🗑️  LIMPEZA COMPLETA DO HISTÓRICO DO CHAT
==================================================================

📊 Estado atual:
   📁 Conversas: X
   💬 Mensagens: Y
   📎 Anexos: Z

🗑️  Iniciando limpeza...

1️⃣  Deletando Z anexos...
   ✅ Anexos deletados

2️⃣  Deletando Y mensagens...
   ✅ Mensagens deletadas

3️⃣  Deletando X conversas...
   ✅ Conversas deletadas

✅ LIMPEZA CONCLUÍDA COM SUCESSO!

📝 Verificando estado final...
   📁 Conversas: 0
   💬 Mensagens: 0
   📎 Anexos: 0
```

## 📝 Notas

- ✅ Ação **IRREVERSÍVEL** - todo histórico será perdido
- ✅ Não afeta outros módulos (campanhas, contatos, etc)
- ✅ Perfeito para testes limpos
- ✅ O script detecta Railway automaticamente e não pede confirmação

