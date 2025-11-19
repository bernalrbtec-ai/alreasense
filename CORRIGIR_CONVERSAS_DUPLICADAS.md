# 🔧 Corrigir Conversas Duplicadas (Número vs Contato)

## Problema Identificado

Quando uma conversa é iniciada diretamente no celular (não pela aplicação):

1. **Webhook cria conversa** com `contact_phone` = número (ex: "172546536251609")
2. **`contact_name`** pode ser o número formatado ou vazio
3. **Quando contato é criado depois**, o signal atualiza tags mas **NÃO atualiza `contact_name`**
4. **Resultado:** Conversa continua mostrando número ao invés do nome do contato

## Causa Raiz

O signal `update_conversations_on_contact_change` estava:
- ✅ Atualizando tags das conversas
- ✅ Fazendo broadcast via WebSocket
- ❌ **NÃO atualizando `contact_name`** das conversas

## Solução Implementada

### 1. Signal Atualizado (`backend/apps/contacts/signals.py`)

Agora o signal:
1. ✅ Busca conversas por telefone normalizado (encontra variações de formatação)
2. ✅ Atualiza `contact_name` com nome do contato
3. ✅ Atualiza `contact_phone` se houver diferença de formatação
4. ✅ Faz broadcast via WebSocket

### 2. Normalização de Telefone

Função `normalize_phone_for_search()`:
- Remove formatação (@s.whatsapp.net, espaços, hífens)
- Garante formato E.164 (+5517999999999)
- Encontra conversas mesmo com pequenas diferenças

### 3. Comando de Correção Manual

**Comando Django:** `python manage.py fix_conversation_names`

Corrige conversas existentes que estão com número ao invés de nome.

## Como Usar

### Correção Automática (Futuro)

Quando um contato for criado/atualizado, o signal já corrige automaticamente.

### Correção Manual (Conversas Existentes)

```bash
cd backend
python manage.py fix_conversation_names
```

Este comando:
- Busca todas as conversas individuais
- Para cada conversa, busca contato correspondente por telefone
- Atualiza `contact_name` se contato existir
- Mostra estatísticas de atualizações

## Verificação

Após executar o comando, verifique:

```sql
-- Ver conversas que ainda estão com número ao invés de nome
SELECT 
    c.id,
    c.contact_phone,
    c.contact_name,
    CASE 
        WHEN c.contact_name ~ '^[\d\s\(\)\-]+$' THEN 'Apenas número'
        ELSE 'Tem nome'
    END as status
FROM chat_conversation c
WHERE c.conversation_type = 'individual'
ORDER BY c.contact_name;
```

## Prevenção Futura

O signal agora garante que:
- ✅ Quando contato é criado → conversas são atualizadas automaticamente
- ✅ Quando contato é atualizado → conversas são atualizadas automaticamente
- ✅ Telefones são normalizados para comparação correta

---

**Última atualização:** 2025-01-20

