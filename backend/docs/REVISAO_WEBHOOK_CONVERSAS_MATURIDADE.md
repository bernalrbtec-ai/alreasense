# Revisão de maturidade – Webhook conversas e troca de instância

## Escopo revisado

- `apps/chat/webhooks.py`: busca/reuso de conversa, fallbacks por telefone, troca de instância.
- `apps/connections/webhook_views.py`: log seguro do `messages.upsert`, fallback quando instância não é encontrada.

---

## Garantias e correções aplicadas

### 1. Nunca atribuir `None` a `instance_friendly_name`

- `Conversation.instance_friendly_name` é `CharField(blank=True)` sem `null=True`; atribuir `None` pode causar erro em alguns backends.
- **Correção:** Em todos os blocos que setam `instance_friendly_name` (órfã, passo 4, último fallback), a expressão termina com `or ""` e usa `getattr(wa_instance, "instance_name", None) or ""` quando usa `instance_name`, garantindo string nunca `None`.

### 2. Conjuntos de instâncias válidas (órfã) sem valor `"None"`

- Se no banco `instance_name` / `evolution_instance_name` / `phone_number_id` forem `NULL`, `str(None)` vira `"None"` e polui os sets.
- **Correção:** Só adicionar ao set quando o valor não é `None` e, após `str(...).strip()`, não é vazio: `if row[i] is not None and str(row[i]).strip(): ...`.

### 3. Defesa contra `instance_name` vazio no último fallback

- Uso de `(instance_name or "").strip()` ao atualizar e logar no bloco “qualquer_conv”, evitando exceção se `instance_name` vier vazio em algum caminho.

### 4. Variáveis sempre definidas antes do uso

- No `else` (sem conversa nos passos 1–4): se o fallback “qualquer_conv” encontrar conversa, `conversation` e `created = False` são setados; caso contrário, o bloco `if not existing_conversation` cria a conversa e seta `conversation` e `created`. O código que usa `conversation` e `created` (logs, `needs_update`) só roda depois, com variáveis definidas.

### 5. Multi-instância protegida

- Último fallback (“qualquer_conv”) só roda quando `WhatsAppInstance.objects.filter(tenant=tenant, is_active=True).count() == 1`, evitando juntar conversas de Comercial/Suporte quando o tenant tem mais de uma instância ativa.

### 6. Preferência por conversa mais antiga

- Passo 1: busca por `instance_name` com `.order_by("created_at", "id")` para, em caso de duplicatas (ex.: nova vazia vs antiga com histórico), preferir a mais antiga.
- “Mais antiga” no passo 1: se existir outra conversa (mesmo tenant+phone) mais antiga que a encontrada por instância, reutilizamos a mais antiga e atualizamos nela o `instance_name` / `instance_friendly_name`.

### 7. UnboundLocalError evitado

- Nos blocos que usam o modelo de instância (órfã e passo 4), usa-se `from apps.notifications.models import WhatsAppInstance as _WAInstance` e `_WAInstance` no mesmo bloco, evitando conflito com o import de `WhatsAppInstance` mais abaixo na função.

### 8. Log do webhook à prova de payload malformado

- Extração de `remote_jid` para log em `try/except`; em falha usa `remote_jid = ''` e o handler segue normalmente.

### 9. Fallback por telefone (dígitos) seguro

- Uso de `digits_only[2:]` apenas quando `len(digits_only) >= 12` e `digits_only.startswith('55')`, reduzindo risco de falso positivo com números de outros países.
- Condição `if digits_only` antes de `Q(contact_phone='+' + digits_only)` (redundante com o `if` externo, mas defensivo).

---

## Edge cases considerados

| Cenário | Comportamento |
|--------|----------------|
| Duas conversas mesmo (tenant, phone), uma nova vazia e uma antiga | Passo 1 prefere a mais antiga e atualiza nela o `instance_name`. |
| Tenant com 2+ instâncias ativas (Comercial/Suporte) | Último fallback “qualquer_conv” não roda; não há junção indevida. |
| Instância “órfã” (instance_name que não existe mais) | Fallback órfã reutiliza a conversa e atualiza `instance_name` / `instance_friendly_name`. |
| `wa_instance` ou `correct_friendly_name` ausente | Uso de `getattr(..., None) or ""` e `(x or "").strip()`; nunca se atribui `None` a `instance_friendly_name`. |
| Webhook com `data` lista vazia ou formato inesperado | Log com `remote_jid` em try/except; processamento segue com `message_data` tratado mais abaixo. |
| Grupos | Fallback por dígitos e último fallback “qualquer_conv” não se aplicam (`not is_group`); busca por `base_filter` continua correta para grupos. |

---

## Pontos de atenção (não alterados)

- **Race na criação:** Continua tratado pelo `except IntegrityError` ao criar conversa (busca e reuso em caso de constraint único).
- **Multi-tenant:** `tenant` é sempre o da instância/conexão que recebeu o webhook; não há reuso entre tenants.
- **correct_friendly_name com status 'connecting':** A busca por `correct_wa_instance` usa `status='active'`; se a instância estiver `connecting`, `correct_friendly_name` pode ficar vazio; o fluxo segue com string vazia.

---

## Checklist final

- [x] Nenhum `instance_friendly_name = None` possível.
- [x] Sets de instâncias válidas sem valor `"None"` por NULL no banco.
- [x] `conversation` e `created` definidos em todos os caminhos antes do uso.
- [x] Último fallback só com 1 instância ativa no tenant.
- [x] Passo 1 ordenado por `created_at` e reuso da conversa mais antiga quando aplicável.
- [x] Imports com alias `_WAInstance` nos blocos que precisam, evitando UnboundLocalError.
- [x] Log do webhook com try/except em torno da extração de `remote_jid`.
- [x] Fallback por dígitos restrito a Brasil (55 + len >= 12) e com checagem de `digits_only`.
- [x] Linter sem erros nos arquivos alterados.
