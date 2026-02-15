# Secretária IA - Horário de Atendimento

## Problema Identificado

A secretária IA estava "perdida" em relação ao horário de atendimento:
- Não estava usando a informação de `business_hours` enviada pelo sistema
- Considerava sempre a empresa como fechada ou baseava-se apenas no que o usuário dizia
- Não informava corretamente quando a empresa reabre

## Solução Implementada

### 1. Melhorias no Backend (`secretary_service.py`)

O backend agora envia `business_hours` de forma mais explícita:

```python
business_hours_info = {
    "is_open": True/False,  # Status claro
    "next_open_time": "Segunda-feira, 09:00",  # Quando reabre (se fechada)
    "status_text": "ABERTA" ou "FECHADA",  # Texto explícito
    "status_message": "A empresa está ABERTA no momento..."  # Mensagem formatada
}
```

### 2. Melhorias no Prompt (`prompt_secretaria_bia.txt`)

O prompt foi atualizado para deixar **muito claro** como usar o horário:

- **CRÍTICO:** A IA deve SEMPRE verificar `business_hours.is_open` antes de responder
- Instruções explícitas sobre o que fazer quando `is_open === true` vs `is_open === false`
- Obrigatório informar `next_open_time` quando estiver fechada
- Não inventar horários baseado no que o usuário diz

### 3. Como o N8N Deve Usar

O código do N8N já está preparado para usar `business_hours`:

```javascript
const bh = body.business_hours || {};
const isOpen = bh.is_open === true;
const nextOpen = (bh.next_open_time || '').trim();

if (isSecretary) {
  if (!isOpen) {
    businessHoursInstrucao = ' A empresa está FECHADA no momento...';
    if (nextOpen) businessHoursInstrucao += ' Próxima abertura: ' + nextOpen + '.';
  } else {
    businessHoursInstrucao = ' A empresa está ABERTA. Atenda normalmente.';
  }
}
```

**IMPORTANTE:** Se o tenant usar um prompt personalizado (`TenantSecretaryProfile.prompt`), o N8N deve:
1. Usar o prompt personalizado como base
2. **SEMPRE adicionar** a instrução de `business_hours` ao final do prompt personalizado
3. Garantir que a IA tenha acesso claro ao status do horário

## Estrutura do Payload Enviado

```json
{
  "action": "secretary",
  "agent_type": "secretary",
  "business_hours": {
    "is_open": false,
    "next_open_time": "Segunda-feira, 09:00",
    "status_text": "FECHADA",
    "status_message": "A empresa está FECHADA no momento. Retornamos em: Segunda-feira, 09:00"
  },
  "conversation": {...},
  "message": {...},
  "messages": [...],
  "knowledge_items": [...],
  "memory_items": [...],
  "departments": [...],
  "prompt": "..." // Prompt personalizado (se houver)
}
```

## Comportamento Esperado

### Quando `is_open === true`:
- ✅ Atender normalmente
- ✅ Não mencionar horário de atendimento
- ✅ Pode sugerir departamento se necessário

### Quando `is_open === false`:
- ✅ **OBRIGATÓRIO:** Informar que está fechada na primeira ou segunda mensagem
- ✅ **OBRIGATÓRIO:** Informar quando reabre usando `next_open_time`
- ✅ Oferecer registro de retorno
- ✅ Se cliente quiser retorno: confirmar assunto e departamento antes de registrar
- ✅ Usar comandos `REGISTRAR_RETORNO`, `ASSUNTO_RETORNO`, `DEPARTAMENTO_RETORNO`, `FECHAR_CONVERSA` (em linhas separadas, removidas antes de enviar)

## Verificação

Para verificar se está funcionando:

1. **Logs do Backend:**
   ```
   [SECRETARY] Business hours check: is_open=True/False, next_open_time=...
   ```

2. **Payload enviado ao N8N:**
   - Verificar se `business_hours` está presente
   - Verificar se `is_open` está correto
   - Verificar se `next_open_time` está presente quando fechada

3. **Resposta da IA:**
   - Quando fechada: deve mencionar horário na primeira resposta
   - Quando aberta: não deve mencionar horário

## Troubleshooting

### Problema: IA sempre diz que está fechada
**Causa:** `BusinessHours` não configurado ou `is_active=False`
**Solução:** 
- Verificar se existe `BusinessHours` para o tenant
- Verificar se `is_active=True`
- Verificar logs: `[BUSINESS HOURS] Nenhum horário configurado...`

### Problema: IA não menciona quando reabre
**Causa:** `next_open_time` não está sendo calculado corretamente
**Solução:**
- Verificar logs: `[BUSINESS HOURS] Próximo horário: ...`
- Verificar se `BusinessHours` tem dias da semana habilitados
- Verificar timezone configurado

### Problema: IA inventa horários
**Causa:** Prompt não está instruindo claramente para usar `business_hours`
**Solução:**
- Verificar se o prompt personalizado inclui instruções sobre `business_hours`
- Garantir que o N8N adiciona instrução de `business_hours` mesmo com prompt personalizado

## Próximos Passos

1. ✅ Backend melhorado para enviar `business_hours` de forma explícita
2. ✅ Prompt atualizado com instruções claras
3. ⏳ Verificar se o N8N está usando corretamente (especialmente com prompt personalizado)
4. ⏳ Testar em produção
5. ⏳ Monitorar logs para garantir que está funcionando

---

**Última Atualização:** 10/02/2026
