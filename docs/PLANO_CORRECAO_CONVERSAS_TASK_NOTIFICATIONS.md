# Plano de correção – conversas duplicadas (task notifications)

**Objetivo:** Corrigir a criação de conversas em formato diferente do restante do sistema, evitando duplicatas para o mesmo contato, **sem quebrar ou parar** nenhum fluxo.

**Revisão:** Inclui correção de falhas identificadas (normalização quando já existe duplicata, race condition) e melhorias (import, save em lote, canonical vazio, guardas, contact_name, rollback). Última passada: defensivos (contact_phone não-string, contact_name None), log na recuperação da race, rollback explícito e validação rápida em produção.

---

## 1. Contexto do problema

- **Onde:** `get_or_create_conversation()` em `backend/apps/contacts/services/task_notifications.py`.
- **Causa:** A função **cria** conversas com `contact_phone = 5511999999999@s.whatsapp.net`, enquanto webhook, API start e campanhas usam `+5511999999999` (E.164). O banco permite as duas formas (são valores diferentes), gerando duas conversas para o mesmo contato.
- **Chamadores (todos já passam E.164):**
  - `send_task_notification_to_contacts` (linha ~89)
  - `send_task_reminder_to_contacts` (linha ~306)
  - `send_daily_summary_to_user` (linha ~527)

Nenhum outro arquivo chama essa função. Ou seja: a alteração fica contida em um único módulo.

---

## 2. Princípios da correção

1. **Só alterar** `get_or_create_conversation`; não mexer em webhook, start, campanhas nem front.
2. **Busca primeiro, criação depois:** ampliar a busca para sempre achar conversa existente (qualquer formato); na criação, usar só formato canônico.
3. **Formato canônico único:** usar a mesma função do resto do app: `normalize_phone_for_search` de `apps.contacts.signals`.
4. **Compatibilidade com dados atuais:** continuar buscando pelos formatos antigos (`@s.whatsapp.net` e sem `+`) para não “perder” conversas já salvas.
5. **Não mexer em duplicatas já existentes:** não fazer merge nem delete; apenas evitar novas duplicatas e, opcionalmente, normalizar o `contact_phone` quando a conversa for encontrada.

---

## 3. Alterações em `get_or_create_conversation`

### 3.1 Import

- **Recomendado:** importar `normalize_phone_for_search` **dentro da função** (ex.: no início do `try`), a partir de `apps.contacts.signals`. Assim evita-se qualquer risco de import circular no carregamento do módulo.
- Se a equipe preferir import no topo do arquivo, validar antes que não há ciclo (task_notifications → signals → … → task_notifications).

### 3.2 Guarda inicial e telefone canônico

- **Primeira linha do `try` (obrigatório):** Se `contact_phone` for `None` ou string vazia, fazer `return None` e logar (ex.: warning). Isso evita `AttributeError` na linha que faz `contact_phone.replace('+', '').strip()` (cálculo de `phone_normalized` no passo 3.3) e deixa o contrato da função claro.
- **Defensivo (opcional):** Se `contact_phone` não for `None` e não for `str` (ex.: número inteiro vindo do chamador), fazer `contact_phone = str(contact_phone)` antes de seguir; assim `normalize_phone_for_search(contact_phone)` não quebra com `AttributeError`.
- Em seguida, **antes** da lógica atual de normalização:
  - Chamar `canonical_phone = normalize_phone_for_search(contact_phone)`.
  - Se `canonical_phone` ficar vazio (None ou string vazia), usar `contact_phone` como fallback.
  - **Recomendado:** Se após o fallback o valor continuar vazio, fazer `return None` e logar um warning, em vez de criar conversa com telefone inválido (evita poluir o banco e erro ao criar, já que `contact_phone` no modelo é `CharField` sem `null=True`).

**Ordem importante:** este bloco (guarda + canonical + eventual return) deve ser executado **antes** de qualquer uso de `contact_phone` em expressões como `.replace(...)` (item 3.3), para que não se chegue a `phone_normalized = contact_phone.replace(...)` com `contact_phone` None.

Assim, qualquer pequena variação que o chamador passar (com/sem `+`, com espaços, etc.) vira um único formato para busca e criação.

### 3.3 Busca (encontrar conversa existente)

- **Manter** o cálculo de `phone_normalized` e `phone_with_suffix` como hoje (para seguir encontrando conversas no formato antigo).
- **Montar a lista de candidatos para busca** de forma que não haja duplicatas (ex.: usar um set e converter para lista):
  - `canonical_phone`
  - `phone_with_suffix` (ex.: `5511999999999@s.whatsapp.net`)
  - `phone_normalized` (ex.: `5511999999999`)
  - `contact_phone` (valor original recebido)
- Remover da lista valores vazios/None antes de filtrar. **Importante:** em Django, `contact_phone__in=[]` devolve nenhum resultado; se após a remoção a lista ficar vazia, não chamar o `filter` com lista vazia — fazer `return None` (ou pular para o create só se houver ao menos um candidato). Na prática, se o passo 3.2 foi respeitado e `canonical_phone` está preenchido, a lista terá ao menos esse valor.
- **Busca:** manter exatamente como hoje:  
  `Conversation.objects.filter(tenant=tenant, contact_phone__in=<lista>, conversation_type='individual').first()`  
  só trocando a lista pelo novo conjunto de candidatos. Manter a lista em uma variável (ex.: `candidate_list`) para reutilizar no tratamento de IntegrityError (item 3.5).

Com isso, você acha conversa existente tanto em E.164 quanto no formato antigo; nada deixa de ser encontrado.

### 3.4 Quando encontrar conversa existente

- **Comportamento atual:** atualizar `contact_name` se diferente e retornar. Manter isso.
- **Opcional (recomendado):** Se `conversation.contact_phone` contiver `@s.whatsapp.net`, **só então** atualizar para o canônico, **desde que** não exista outra conversa no mesmo tenant com `contact_phone == canonical_phone`:
  - Consultar: existe `Conversation.objects.filter(tenant=tenant, contact_phone=canonical_phone).exclude(id=conversation.id).exists()`?
  - Se **não** existir: aí sim fazer `conversation.contact_phone = canonical_phone` e incluir `'contact_phone'` no `save(update_fields=[...])`.
  - Se **existir:** não atualizar (há duplicata; atualizar geraria IntegrityError por violar a unique em `(tenant_id, contact_phone)`).
- **Melhoria:** montar uma única lista `update_fields` com os campos que de fato forem alterados (ex.: `'contact_name'`, `'contact_phone'`); fazer um único `save(update_fields=...)` só se a lista não estiver vazia. Assim evita-se duas idas ao banco quando ambos mudam e evita-se chamar `save` sem necessidade quando nada mudar.

### 3.5 Quando não encontrar (criar nova conversa)

- **Troca única obrigatória:** onde hoje está  
  `contact_phone=phone_with_suffix`  
  usar  
  `contact_phone=canonical_phone`  
  (ou, se tiver usado fallback, o valor que definiu para “canônico”).
- **Manter inalterados:** todos os outros campos do `Conversation.objects.create(...)` (tenant, conversation_type, status, department, metadata, etc.). **Defensivo:** para `contact_name`, usar `contact_name or ''` na chamada ao `create`, pois o campo no modelo é `CharField(blank=True)` sem `null=True` — passar `None` pode causar erro em alguns cenários; os chamadores hoje passam string, mas isso evita quebra se no futuro algum passar `None`.
- **Log:** ajustar a mensagem de log que hoje cita `phone_with_suffix` para citar o valor realmente usado (ex.: `canonical_phone`), para facilitar debug.
- **Condição de corrida (recomendado):** envolver **somente** a chamada `Conversation.objects.create(...)` em um `try/except` que capture `IntegrityError` (import: `from django.db import IntegrityError`). O bloco opcional de atualização ao encontrar conversa (item 3.4) **não** deve estar dentro desse `try` — só o `create`. Se der IntegrityError e a mensagem da exceção contiver `idx_chat_conversation_unique` (nome do índice unique em `chat_conversation`; em outros backends o texto pode variar — usar o nome da constraint/índice unique de `(tenant_id, contact_phone)`), outro processo (ex.: webhook ou outra task) criou a conversa no mesmo instante; então refazer a **busca** com a mesma lista de candidatos (a variável do passo 3.3): executar de novo `Conversation.objects.filter(tenant=tenant, contact_phone__in=candidate_list, conversation_type='individual').first()`. Se achar, **logar** (ex.: `logger.info` ou `logger.warning`) que a conversa foi encontrada após race, para visibilidade em operação; em seguida retornar a conversa. Se não achar, relançar a exceção (ou fazer `raise` da exceção original). Assim o chamador não recebe `None` por causa de race; o padrão já existe em `webhooks.py` (linhas ~1863–1885).

Assim, novas conversas criadas por task notifications ficam no mesmo formato do webhook e da API start; não surgem mais duplicatas por diferença de formato; e corrida entre duas criações simultâneas não resulta em falha para o segundo chamador.

### 3.6 Tratamento de erro

- Manter o `except` atual (genérico): retornar `None` e logar o erro. O tratamento específico de `IntegrityError` na criação (item 3.5) fica **dentro** do `try`, antes do `except` genérico; se for IntegrityError de unique, fazer a nova busca e retornar a conversa; caso contrário, relançar ou deixar o `except` genérico tratar.

### 3.7 Docstring (opcional)

- Após a implementação, atualizar a docstring da função: em *Args*, indicar que `contact_phone` pode ser E.164 ou outro formato e será normalizado internamente; e que novas conversas são criadas com `contact_phone` em formato E.164 (canonical).

---

## 4. Falhas identificadas e como o plano as trata

| Risco | O que aconteceria | Ajuste no plano |
|-------|-------------------|-----------------|
| **Normalizar conversa quando já existe duplicata** | Duas linhas: uma com `+55...`, outra com `55...@s.whatsapp.net`. Ao atualizar a segunda para `+55...`, duas linhas ficariam com o mesmo `contact_phone` → **IntegrityError** no `save`. | Item 3.4: só atualizar para canônico se **não** existir outra conversa no tenant com `contact_phone=canonical_phone`. |
| **Condição de corrida na criação** | Dois processos não encontram conversa e ambos chamam `create`; um ganha, o outro recebe IntegrityError e hoje retornaria `None` (mensagem não enviada). | Item 3.5: em caso de IntegrityError (unique), refazer a busca e retornar a conversa já criada. |
| **Import circular** | Import de `signals` no topo de `task_notifications` pode, em alguns cenários de carga, criar ciclo. | Item 3.1: import dentro da função. |
| **Canonical vazio** | Entrada estranha gera `canonical_phone` vazio; criar conversa com `contact_phone=''` polui o banco. | Item 3.2 (opcional): se após fallback continuar vazio, retornar `None` e logar. |
| **Dois saves ao encontrar conversa** | Atualizar nome e depois telefone = duas escritas no banco. | Item 3.4: um único `save(update_fields=[...])` quando ambos mudarem. |
| **contact_phone None ou vazio** | `contact_phone.replace('+', '')` com `contact_phone` None gera **AttributeError**; criar com `contact_phone=''` ou None pode violar o modelo (CharField sem null). | Item 3.2: guarda no início do `try` (return None se não houver contact_phone) e return opcional quando canonical continua vazio após fallback. |
| **contact_phone não é string** | Chamador passa int ou outro tipo; `normalize_phone_for_search(contact_phone)` ou `.replace` quebra com **AttributeError**. | Item 3.2 (opcional): converter com `str(contact_phone)` quando não for str. |
| **contact_name None no create** | Modelo `contact_name` é CharField sem `null=True`; passar None pode causar erro ao criar. | Item 3.5: usar `contact_name or ''` no `create`. |

**Nota:** Quando já existem duplicatas (duas conversas para o mesmo contato), `.first()` pode devolver qualquer uma das duas; qual delas é retornada não é garantido. O plano não altera isso; apenas evita criar novas duplicatas e evita quebrar ao normalizar.

### 4.1 Diagnóstico antes de aplicar (opcional)

Para ver **qual formato de `contact_phone` foi mais usado** no banco antes de começar a correção, rode uma das opções abaixo (no ambiente desejado: dev, staging ou produção, com cuidado em prod).

**Opção A – Django shell** (`python manage.py shell`):

```python
from apps.chat.models import Conversation

total = Conversation.objects.count()
# Formato criado por task notifications (o que vamos deixar de criar)
com_suffix = Conversation.objects.filter(contact_phone__iendswith='@s.whatsapp.net').count()
# Formato E.164 com + e sem @ (webhook, start, campanhas) – o canônico
e164_sem_arroba = Conversation.objects.filter(contact_phone__startswith='+').exclude(contact_phone__contains='@').count()
# Grupos (não são afetados por esta correção)
grupos = Conversation.objects.filter(contact_phone__iendswith='@g.us').count()

print('Total de conversas:', total)
print('Com @s.whatsapp.net (formato que task notifications usa hoje):', com_suffix)
print('E.164 com + e sem @ (formato webhook/start/campanhas):', e164_sem_arroba)
print('Grupos (@g.us):', grupos)
print('(Demais = outros formatos, ex. só dígitos)', total - com_suffix - e164_sem_arroba - grupos)
```

**Opção B – SQL direto** (ex.: `psql` ou cliente do banco):

```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE contact_phone ILIKE '%@s.whatsapp.net') AS com_suffix,
  COUNT(*) FILTER (WHERE contact_phone LIKE '+%' AND contact_phone NOT LIKE '%@%') AS e164_com_mais,
  COUNT(*) FILTER (WHERE contact_phone ILIKE '%@g.us') AS grupos
FROM chat_conversation;
```

Assim você vê quantas conversas estão no formato que a correção vai **deixar de criar** (`@s.whatsapp.net`) e quantas já estão no formato canônico (E.164 com `+`). Não altera nenhum dado; só consulta.

---

## 5. Ordem de implementação sugerida (para não quebrar)

1. **Implementar busca**
   - Import (dentro da função), `canonical_phone`, lista de candidatos (incluindo formatos antigos), mesma query com `.first()`.
2. **Implementar criação**
   - Trocar `contact_phone=phone_with_suffix` por `contact_phone=canonical_phone`, ajustar log, e adicionar tratamento de `IntegrityError` (refazer busca e retornar conversa existente).
3. **Testar em ambiente não produtivo**
   - Contato que já tem conversa em E.164 → deve ser encontrado; não deve criar outra.
   - Contato que só tem conversa em `@s.whatsapp.net` → deve ser encontrado.
   - Contato novo → deve criar uma conversa com `contact_phone` em E.164.
   - (Opcional) Dois requests simultâneos para o mesmo contato novo → um cria, o outro deve obter a mesma conversa (não retornar `None`).
4. **Opcional:** ativar a atualização de `contact_phone` quando encontrar conversa no formato antigo, **com a verificação** de que não existe outra conversa no tenant com `contact_phone=canonical_phone` (item 3.4).

---

## 6. O que não fazer (garantir que não quebre/não pare)

- **Não** alterar webhook, API start, campanhas, front ou listagem de conversas.
- **Não** fazer merge ou delete em duplicatas já existentes nesta correção; isso pode ser tratado depois, se desejar.
- **Não** remover `phone_with_suffix` e `phone_normalized` da lista de busca: eles garantem que conversas antigas continuem sendo encontradas.
- **Não** mudar assinatura de `get_or_create_conversation` nem o comportamento de retorno (Conversation ou None).
- **Não** alterar os chamadores: eles já passam E.164; a função continua aceitando o que recebe e normalizando por dentro.

---

## 7. Verificação pós-deploy

- Conferir logs: novas conversas criadas por task notifications devem aparecer com `contact_phone` em formato `+55...`.
- Para um contato que já tinha conversa (E.164 ou antiga), disparar uma notificação de tarefa e confirmar que a conversa existente é reutilizada e que a mensagem aparece nela.
- **Validação rápida em produção:** disparar uma única notificação de tarefa (ou lembrete) para um contato de teste; em seguida, conferir no banco ou na UI que a conversa foi criada/encontrada e que o campo `contact_phone` está em E.164 (ex.: `+5511...`). Isso confirma que o fluxo está correto sem impacto amplo.
- Não é necessário parar ou agendar janela de manutenção; a mudança é compatível com o comportamento atual e só unifica o formato na criação e melhora a busca.

---

## 8. Resumo em uma frase

**Unificar formato de `contact_phone` em `get_or_create_conversation`: buscar com formato canônico + formatos antigos (para achar qualquer conversa existente) e criar sempre com o formato canônico E.164 (`normalize_phone_for_search`), sem alterar mais nenhum fluxo do sistema.**

---

## 9. Revisão final – ordem de execução e checklist

**Ordem obrigatória dentro do `try`:**
1. Guarda: se não `contact_phone`, return None e log.
2. Import de `normalize_phone_for_search` (se for dentro da função).
3. `canonical_phone = normalize_phone_for_search(contact_phone)`; fallback; opcionalmente return None se vazio.
4. Calcular `phone_normalized` e `phone_with_suffix` (usa `contact_phone` — já garantido não None).
5. Montar lista de candidatos (set/list), remover vazios/None; se lista vazia, return None.
6. Busca com `contact_phone__in=<lista>`; guardar resultado e a lista em variáveis.
7. Se encontrou: montar lista de campos a atualizar (nome e/ou telefone, com verificação de duplicata para telefone); se a lista não for vazia, um único `save(update_fields=...)`; return.
8. Try/except **somente** em volta de `Conversation.objects.create(..., contact_phone=canonical_phone, ...)`; em caso de IntegrityError com `idx_chat_conversation_unique`, refazer busca com a mesma lista, return conversa ou raise.
9. Log de criação e return conversa.
10. `except Exception` genérico: log e return None.

**Checklist antes do deploy:**  
□ Guarda para None/vazio no início.  
□ Lista de candidatos inclui canonical, phone_with_suffix, phone_normalized, contact_phone; lista sem duplicatas e sem None/vazios.  
□ Create usa `contact_phone=canonical_phone` e `contact_name or ''`.  
□ IntegrityError só em volta do create; refazer busca com mesma lista; logar quando recuperar da race.  
□ Ao normalizar conversa encontrada (3.4), verificar com `.exclude(id=conversation.id)` que não existe outra com `contact_phone=canonical_phone`.  
□ Um único save quando atualizar nome e telefone.  
□ Docstring atualizada (opcional).

---

## 10. Rollback e tranquilidade

- **Escopo da mudança:** apenas a função `get_or_create_conversation` em um único arquivo. Nenhuma migração de banco, nenhuma alteração em API, webhook ou front.
- **Se algo der errado:** reverter o commit que alterou `task_notifications.py` e fazer redeploy. O comportamento volta ao anterior (criação com `@s.whatsapp.net`). Não é necessário rodar migração reversa nem limpar dados.
- **Rollback rápido:** ter o diff ou o patch da alteração guardado permite reaplicar o “estado anterior” em minutos se for preciso voltar atrás.
- **Tranquilidade:** a função continua retornando `Conversation` ou `None`; os chamadores não mudam; o pior caso é voltar a criar conversas no formato antigo (que já acontece hoje), sem perda de mensagens nem quebra de outros fluxos.
