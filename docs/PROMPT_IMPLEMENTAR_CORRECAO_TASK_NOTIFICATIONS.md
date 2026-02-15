# Prompt para agente: implementar correção de conversas duplicadas (task notifications)

Use o texto abaixo ao chamar outro agente (ou sessão) para implementar a correção.

---

## Prompt (copiar e colar)

```
Implemente a correção descrita no plano abaixo. O escopo é **apenas** a função `get_or_create_conversation` no arquivo `backend/apps/contacts/services/task_notifications.py`. Não altere webhook, API start, campanhas nem front.

**Documento obrigatório:** leia e siga o plano em `docs/PLANO_CORRECAO_CONVERSAS_TASK_NOTIFICATIONS.md`, em especial:
- **Seção 3** – todas as alterações em `get_or_create_conversation` (3.1 a 3.7)
- **Seção 9** – ordem de execução dentro do `try` e checklist antes de considerar pronto

**Resumo do que fazer:**
1. Guarda no início do `try`: se `contact_phone` for None ou vazio, return None e log.
2. Importar `normalize_phone_for_search` de `apps.contacts.signals` (recomendado: dentro da função).
3. Calcular `canonical_phone = normalize_phone_for_search(contact_phone)`; fallback se vazio; opcionalmente return None se continuar vazio.
4. Manter o cálculo de `phone_normalized` e `phone_with_suffix`; montar lista de candidatos (canonical_phone, phone_with_suffix, phone_normalized, contact_phone), remover vazios/None, guardar em variável (ex.: `candidate_list`).
5. Buscar conversa com `contact_phone__in=candidate_list`; guardar resultado e a lista.
6. Se encontrou: atualizar `contact_name` se diferente; opcionalmente, se `contact_phone` contiver `@s.whatsapp.net`, só atualizar para `canonical_phone` se não existir outra conversa no tenant com `contact_phone=canonical_phone` (usar `.exclude(id=conversation.id).exists()`). Um único `save(update_fields=[...])` só se houver campos a atualizar.
7. Se não encontrou: envolver **somente** o `Conversation.objects.create(...)` em try/except de `IntegrityError`; criar com `contact_phone=canonical_phone` e `contact_name or ''`; em caso de IntegrityError com `idx_chat_conversation_unique`, refazer a busca com `candidate_list`, logar que encontrou após race, retornar a conversa (ou raise se não achar).
8. Ajustar o log de criação para citar `canonical_phone`.
9. Manter o `except Exception` genérico no final (return None e log).

Opcional: atualizar a docstring da função (item 3.7 do plano). Opcional: se `contact_phone` não for str, fazer `contact_phone = str(contact_phone)` antes de usar.

**Validação:** após implementar, confira o checklist da seção 9 do plano e rode os testes manuais sugeridos na seção 5 (conversa existente E.164, existente @s.whatsapp.net, contato novo). O script `scripts/sql/consultar_duplicatas_conversas.sql` pode ser usado antes/depois para conferir duplicatas (só leitura).
```

---

## Referências rápidas

| Recurso | Caminho |
|--------|---------|
| Plano completo | `docs/PLANO_CORRECAO_CONVERSAS_TASK_NOTIFICATIONS.md` |
| Arquivo a alterar | `backend/apps/contacts/services/task_notifications.py` |
| Função | `get_or_create_conversation` (linhas ~130–186) |
| Consulta de duplicatas | `scripts/sql/consultar_duplicatas_conversas.sql` |
| Função de normalização | `normalize_phone_for_search` em `backend/apps/contacts/signals.py` |
