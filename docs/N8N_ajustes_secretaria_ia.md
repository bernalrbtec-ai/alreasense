# Ajustes no N8N para Secretária IA

O fluxo **Sense - Gateway IA (teste com prompt e RAG)** já atende o teste de IA. Para a **Secretária IA** (mensagens no Inbox com `action: "secretary"`), basta adaptar o que o backend envia e o que o N8N devolve.

---

## 1. O que o backend envia na Secretária

O Sense faz **POST** no mesmo webhook com:

- `action`: `"secretary"`
- `agent_type`: `"secretary"`
- `tenant`, `conversation`, `message`, `messages` (igual ao teste)
- `knowledge_items` (RAG dos “Dados da empresa”)
- `memory_items` (histórico do contato, últimos 12 meses)
- `departments` (lista com `id`, `name`, `routing_keywords`)
- `business_hours`: `{ is_open, next_open_time }`

**Não** envia `prompt` customizado; o N8N deve usar um prompt fixo de secretária quando `action === 'secretary'`.

---

## 2. Ajuste no node “Montar prompt e modelo1”

Objetivo: quando `action === 'secretary'`, usar prompt de secretária e montar contexto com `knowledge_items`, `memory_items` e `departments`.

Substitua o **jsCode** do node **Montar prompt e modelo1** por:

```javascript
const raw = $input.first().json;
const body = raw.body && typeof raw.body === 'object' ? raw.body : raw;

const isSecretary = (body.action === 'secretary' || body.agent_type === 'secretary');

const promptFromBody = body.prompt || (body.metadata && body.metadata.prompt) || '';
const systemPrompt = (promptFromBody && String(promptFromBody).trim())
  ? String(promptFromBody).trim()
  : isSecretary
    ? `Você é a secretária virtual da empresa. Use o contexto abaixo (dados da empresa, histórico do contato e departamentos) para responder de forma cordial e objetiva. Se o assunto for claramente de um departamento específico, ao final da resposta você pode indicar em uma linha: SUGERIR_DEPARTAMENTO: <uuid do departamento> e RESUMO_PARA_DEPARTAMENTO: <resumo em uma frase>. Caso contrário, apenas responda normalmente.`
    : 'Você é um assistente prestativo.';

const knowledgeItems = Array.isArray(body.knowledge_items) ? body.knowledge_items : [];
const contextParts = [knowledgeItems.map(i => `## ${i.title || 'Documento'}\n${i.content || ''}`).join('\n\n')];

if (isSecretary && Array.isArray(body.memory_items) && body.memory_items.length > 0) {
  contextParts.push('Histórico relevante do contato:\n' + body.memory_items.map(m => `- ${m.content || ''}`).join('\n'));
}
if (isSecretary && Array.isArray(body.departments) && body.departments.length > 0) {
  contextParts.push('Departamentos para encaminhamento (id, nome, palavras-chave):\n' + body.departments.map(d => `- ${d.id}: ${d.name} (${(d.routing_keywords || []).join(', ')})`).join('\n'));
}

const context = contextParts.filter(Boolean).join('\n\n');
const model = (body.metadata && body.metadata.model) ? String(body.metadata.model).trim() : (body.model ? String(body.model).trim() : 'llama3.2');
const knowledgeItemsCount = knowledgeItems.length;

const useChat = Array.isArray(body.messages) && body.messages.length > 0;

if (useChat) {
  const systemContent = [systemPrompt, context ? `Contexto para consulta:\n${context}` : ''].filter(Boolean).join('\n\n');
  const messages = [
    { role: 'system', content: systemContent },
    ...body.messages.map(m => ({ role: (m.role || (m.direction === 'incoming' ? 'user' : 'assistant')).toLowerCase(), content: String(m.content || '') }))
  ];
  return [{ json: { useChat: true, model, messages, knowledgeItemsCount, isSecretary, body } }];
}

const userMessage = (body.message && body.message.content) ? String(body.message.content) : '';
const fullPrompt = [
  systemPrompt,
  context ? `Contexto para consulta:\n${context}` : '',
  userMessage ? `Mensagem do usuário: ${userMessage}` : ''
].filter(Boolean).join('\n\n');

return [{ json: { useChat: false, model, fullPrompt, knowledgeItemsCount, isSecretary, body } }];
```

Assim o mesmo node serve tanto ao **teste de IA** (com `prompt` e `knowledge_items`) quanto à **Secretária** (com `memory_items` e `departments` e prompt padrão de secretária).

---

## 3. Ajuste no node “Formatar resposta para o Sense1”

Objetivo: sempre devolver `reply_text`; quando for secretária, tentar extrair `SUGERIR_DEPARTAMENTO` e `RESUMO_PARA_DEPARTAMENTO` da última linha (opcional) e devolver `suggested_department_id` e `summary_for_department` no JSON.

Substitua o **jsCode** do node **Formatar resposta para o Sense1** por:

```javascript
const ollama = $input.first().json;
const prev = $('Montar prompt e modelo1').first().json;
const replyText = (ollama.message && ollama.message.content)
  ? String(ollama.message.content).trim()
  : (ollama.response && String(ollama.response).trim())
    ? String(ollama.response).trim()
    : '(Sem resposta do modelo.)';

const evalDurationNs = ollama.eval_duration || 0;
const latencyMs = evalDurationNs > 0 ? Math.round(evalDurationNs / 1e6) : 0;

const out = {
  reply_text: replyText,
  status: 'success',
  meta: {
    model: ollama.model || prev.model,
    latency_ms: latencyMs,
    rag_hits: prev.knowledgeItemsCount || 0
  }
};

// Secretária: tentar extrair suggested_department_id e summary_for_department da resposta
if (prev.isSecretary && replyText) {
  const lines = replyText.split('\n').map(l => l.trim()).filter(Boolean);
  let cleanReply = replyText;
  let suggested_department_id = null;
  let summary_for_department = null;
  for (const line of lines.slice(-3)) {
    const depMatch = line.match(/SUGERIR_DEPARTAMENTO:\s*([a-f0-9-]{36})/i);
    const sumMatch = line.match(/RESUMO_PARA_DEPARTAMENTO:\s*(.+)/i);
    if (depMatch) { suggested_department_id = depMatch[1].trim(); cleanReply = cleanReply.replace(line, '').trim(); }
    if (sumMatch) { summary_for_department = sumMatch[1].trim().slice(0, 2000); cleanReply = cleanReply.replace(line, '').trim(); }
  }
  if (suggested_department_id) out.suggested_department_id = suggested_department_id;
  if (summary_for_department) out.summary_for_department = summary_for_department;
  if (cleanReply !== replyText) out.reply_text = cleanReply.replace(/\n\n+/g, '\n\n').trim();
}

return [{ json: out }];
```

- Fluxo de **teste** continua igual: só `reply_text` + `meta`.
- Fluxo da **Secretária**: além disso, podem aparecer `suggested_department_id` e `summary_for_department`; o texto que vai no chat é o `reply_text` (já sem as linhas de SUGERIR/RESUMO, se tiver sido parseado).

---

## 4. Resumo

| Onde | O que fazer |
|------|-------------|
| **Montar prompt e modelo1** | Tratar `action === 'secretary'`: prompt fixo de secretária, incluir `memory_items` e `departments` no contexto, e passar `isSecretary` + `body` para o próximo node. |
| **Formatar resposta para o Sense1** | Se `prev.isSecretary`, opcionalmente parsear `SUGERIR_DEPARTAMENTO` e `RESUMO_PARA_DEPARTAMENTO` e devolver `reply_text`, `suggested_department_id`, `summary_for_department`. |

Não é necessário criar outro webhook: o mesmo **Webhook Sense IA** recebe tanto o teste (`action: "chat"` ou outro) quanto a Secretária (`action: "secretary"`). O backend da Secretária já chama o mesmo `n8n_ai_webhook_url` com o payload descrito acima.
