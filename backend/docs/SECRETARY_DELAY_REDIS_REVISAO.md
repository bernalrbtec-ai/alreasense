# Revisão: delay da BIA com Redis (uma única resposta)

Revisão da modificação sugerida para garantir uma única resposta após o delay, com melhorias, edge cases e garantia de não quebrar o fluxo atual.

---

## 1. Resumo da mudança

- **Problema:** Com múltiplos processos (web/workers), cada mensagem pode cair em um processo diferente; o timer do delay fica em memória por processo, então vários timers disparam e a BIA responde várias vezes.
- **Solução:** Estado do delay no Redis (chave `secretary_delay:{conversation_id}`, valor `run_at`). Um único executor (thread com lock Redis) varre as chaves vencidas e chama `_run_secretary_after_delay` uma vez por conversa.

---

## 2. Melhorias em relação ao plano original

### 2.1 Escrita no Redis: uma única SET (sem GET+max)

- **Plano original:** GET da chave, `run_at = max(existing, now + delay_seconds)`, SET.
- **Melhoria:** A cada mensagem fazer apenas `SET secretary_delay:{conv_id} = (now + delay_seconds)` e TTL = delay_seconds + margem. Isso implementa “reiniciar o delay a partir da última mensagem” e é atômico, evita race entre GET e SET e dispensa Lua para escrita.

### 2.2 Claim atômico no executor (evitar duas respostas)

- **Risco:** Dois processos seguram o lock em momentos diferentes; ambos veem a mesma chave vencida e ambos chamam `_run_secretary_after_delay` → duas respostas.
- **Mitigação:** “Claim” atômico da chave antes de rodar o worker:
  - **Opção A (Redis 6.2+):** `GETDEL key` — devolve o valor e apaga a chave numa operação. Quem receber valor não-nil e `run_at <= now` é o único que executa; os outros passam a ver chave inexistente.
  - **Opção B (qualquer Redis):** Script Lua: ler valor da chave; se existir e `run_at <= now`, apagar a chave e devolver o valor; senão devolver nil. Só quem recebe valor chama `_run_secretary_after_delay`.

Recomendação: usar **Lua** para compatibilidade com Redis mais antigo; alternativa GETDEL se a base for 6.2+.

### 2.3 Formato da chave e do valor

- **Chave:** `secretary_delay:{conversation_id}` com `conversation_id = str(conversation.id)` (UUID em string), igual ao que já é passado para `_run_secretary_after_delay`.
- **Valor:** `run_at` como número (Unix timestamp float) ou string numérica, para comparação `run_at <= time.time()`.
- **TTL:** `delay_seconds + 120` (ex.: delay 30 s → TTL 150 s) para a chave não ficar eternamente se o executor falhar; após executar, a chave é removida no claim.

### 2.4 Início do executor (evitar migrações e duplicar lógica)

- Iniciar a thread do executor em `AppConfig.ready()` do app `ai`, com as mesmas proteções do app campanhas:
  - Não iniciar se for script de migração/setup (verificar `sys.argv` por `migrate`, `fix_`, `create_`, etc.).
  - Respeitar `DISABLE_SCHEDULER=1` ou um flag específico `DISABLE_SECRETARY_DELAY_RUNNER=1` se quiserem desligar em algum ambiente.
- Lock Redis `secretary_delay_runner` com TTL curto (5 s): quem estiver com o lock faz a varredura; ao soltar, outro processo pode pegar. Assim só um “runner” ativo por vez, sem depender de Celery.

### 2.5 Fallback quando Redis indisponível

- Se `get_redis_client()` retornar `None` ou se `SET` falhar (timeout, conexão), usar o comportamento atual: timer em memória (`_pending_secretary_timers` + `threading.Timer`). Logar aviso para operação saber que o Redis está em fallback.
- Manter `_run_secretary_after_delay` inalterado: ele continua fazendo `_pending_secretary_timers.pop(conversation_id, None)`; no fluxo Redis esse pop é no-op (a chave não está no dict). Assim o mesmo callback serve para timer em memória e para o executor Redis.

---

## 3. Edge cases e mitigação

| Edge case | Mitigação |
|-----------|-----------|
| Conversa deletada durante o delay | `_run_secretary_after_delay` já trata: `Conversation.objects.filter(id=...).first()` → None, return. |
| Conversa transferida durante o delay (já tem outgoing visível) | Revalidação em `_run_secretary_after_delay`: `conversation.messages.filter(direction='outgoing', is_internal=False).exists()` → return. Não responde. |
| Secretary desativada ou configuração alterada durante o delay | Revalidação no callback: `secretary_enabled`, `profile.is_active`, `n8n_ai_webhook_url`, grupo WhatsApp. Se algo mudou, return sem responder. |
| Redis indisponível no deploy | Fallback para timer em memória; log de aviso. Comportamento igual ao atual (podem haver múltiplas respostas se houver vários processos). |
| Executor demora mais que o TTL do lock | Lock de 5 s; se a varredura passar disso, outro processo pode pegar o lock. O claim atômico (GETDEL ou Lua) garante que cada chave vencida seja “claimada” por um único processo. |
| `delay_seconds` muito grande (ex.: 120) | TTL da chave = delay_seconds + 120; valor armazenado é numérico; executor compara com `time.time()`. Sem problema. |
| Muitas chaves `secretary_delay:*` | SCAN em vez de KEYS para não bloquear Redis; processar em batches (ex.: 100 chaves por iteração). |
| Exceção ao chamar `_run_secretary_after_delay(conv_id)` | try/except por conversation_id; logar e continuar para as demais chaves. Já é o padrão no código atual. |
| conversation_id inválido (não UUID) na chave | Ao extrair da chave usar prefixo fixo `secretary_delay:`; passar o resto para `_run_secretary_after_delay`. Django filter por id inválido retorna nenhum resultado; `conversation` fica None e o callback retorna cedo. |

---

## 4. O que não mudar (garantir que nada quebre)

- **Chamadas a `dispatch_secretary_async`:** Mantidas (webhooks, meta_webhook, triage_service). A assinatura continua `(conversation, message)`; só a implementação interna do ramo “delay ativo” passa a usar Redis quando disponível.
- **`_run_secretary_after_delay(conversation_id: str)`:** Não alterar assinatura nem lógica de revalidação e chamada ao worker. Só garantir que seja chamada pelo executor quando a chave for claimada.
- **`_secretary_worker(conversation, message)` e `_build_secretary_context`:** Sem mudança. O contexto continua vindo de `conversation.messages` (mensagens recentes); todas as mensagens recebidas durante o delay já estão na conversa.
- **Fluxo sem delay (`delay_seconds <= 0` ou não primeira interação):** Continua disparando o worker na hora em thread; nenhum uso de Redis nem de timer.
- **Compatibilidade de `conversation.id`:** Usar sempre `str(conversation.id)` ao gravar no Redis e ao passar para `_run_secretary_after_delay`; o modelo Conversation usa UUID e o Django aceita string em `filter(id=...)`.

---

## 5. Checklist de implementação

- [ ] Constantes: prefixo `secretary_delay:`, lock `secretary_delay_runner`, TTL do lock 5 s, TTL da chave `delay_seconds + 120`.
- [ ] No ramo de delay em `dispatch_secretary_async`: obter Redis; se disponível, `SET key run_at` e TTL; senão, fallback para timer em memória (código atual).
- [ ] Executor: thread em loop (ex.: a cada 2–3 s), adquirir lock `secretary_delay_runner` (SET NX + TTL 5); se adquirido, SCAN `secretary_delay:*`, para cada chave fazer claim atômico (Lua ou GETDEL); se claimado e `run_at <= now`, chamar `_run_secretary_after_delay(conv_id)`; try/except por conv_id.
- [ ] Iniciar thread do executor em `AiConfig.ready()`, com checagem de migração/setup e flag opcional de disable.
- [ ] Import de `get_redis_client` atrasado (dentro da função que usa) para evitar import circular; `webhook_cache` não importa `apps.ai`.
- [ ] Testes manuais: um processo → uma resposta; vários processos (ou vários requests) → uma resposta; Redis down → fallback e log; conversa transferida durante delay → sem resposta.

---

## 6. Exemplo de script Lua (claim atômico)

```lua
-- KEYS[1] = secretary_delay:{conversation_id}
-- ARGV[1] = current unix time (float as string)
local v = redis.call('GET', KEYS[1])
if v and tonumber(v) <= tonumber(ARGV[1]) then
  redis.call('DEL', KEYS[1])
  return v
end
return nil
```

Quem recebe um valor não-nil do script é o único que deve chamar `_run_secretary_after_delay(conversation_id)` para essa conversa.
