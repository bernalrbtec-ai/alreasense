# N8N - Como Usar Business Hours na Secretária IA

## Problema

Quando o tenant usa um prompt personalizado (`TenantSecretaryProfile.prompt`), o N8N pode não estar incluindo as instruções de `business_hours`, fazendo com que a IA ignore o horário de atendimento.

## Solução: Sempre Incluir Business Hours

O N8N deve **SEMPRE** adicionar instruções de `business_hours` ao prompt, mesmo quando há prompt personalizado.

## Código Recomendado para o Node "Montar prompt e modelo"

```javascript
const raw = $input.first().json;
const body = raw.body && typeof raw.body === 'object' ? raw.body : raw;

const isSecretary = (body.action === 'secretary' || body.agent_type === 'secretary');

// Prompt personalizado (se houver)
const promptFromBody = body.prompt || (body.metadata && body.metadata.prompt) || '';

// ✅ CRÍTICO: Extrair business_hours do payload
const bh = body.business_hours || {};
const isOpen = bh.is_open === true;
const nextOpen = (bh.next_open_time || '').trim();
const statusText = bh.status_text || (isOpen ? 'ABERTA' : 'FECHADA');
const statusMessage = bh.status_message || '';

// ✅ CRÍTICO: Construir instrução de business_hours SEMPRE
let businessHoursInstrucao = '';
if (isSecretary) {
  if (!isOpen) {
    // Empresa FECHADA
    businessHoursInstrucao = '\n\n⚠️ HORÁRIO DE ATENDIMENTO (OBRIGATÓRIO):\n';
    businessHoursInstrucao += 'A empresa está FECHADA no momento.\n';
    if (nextOpen) {
      businessHoursInstrucao += `Retornamos em: ${nextOpen}\n`;
    } else {
      businessHoursInstrucao += 'Retornamos em breve.\n';
    }
    businessHoursInstrucao += '\nREGRAS QUANDO FECHADA:\n';
    businessHoursInstrucao += '1. Avise LOGO NO CONTATO INICIAL que estamos fechados e quando reabrimos.\n';
    businessHoursInstrucao += '2. Ofereça registrar um retorno (anotar contato e assunto).\n';
    businessHoursInstrucao += '3. Se o cliente quiser retorno: CONFIRME o assunto e o departamento antes de registrar.\n';
    businessHoursInstrucao += '4. Ao registrar retorno, use comandos em linhas separadas no final:\n';
    businessHoursInstrucao += '   REGISTRAR_RETORNO\n';
    businessHoursInstrucao += '   ASSUNTO_RETORNO: <resumo>\n';
    businessHoursInstrucao += '   DEPARTAMENTO_RETORNO: <uuid>\n';
    businessHoursInstrucao += '   FECHAR_CONVERSA\n';
    businessHoursInstrucao += '5. NUNCA escreva esses comandos na mensagem visível ao cliente.\n';
  } else {
    // Empresa ABERTA
    businessHoursInstrucao = '\n\n✅ HORÁRIO DE ATENDIMENTO:\n';
    businessHoursInstrucao += 'A empresa está ABERTA no momento. Atenda normalmente.\n';
    businessHoursInstrucao += 'NÃO mencione horário de atendimento nas respostas.\n';
  }
}

// Prompt padrão (se não houver personalizado)
const defaultSecretaryPrompt = 'Você é a secretária virtual da empresa. Use o contexto abaixo (dados da empresa, histórico do contato e departamentos) para responder de forma cordial e objetiva. Quando o cliente relatar problema ou pedir ajuda, responda com empatia e seriedade; evite risadas no texto (ahahaha, kkk, hahaha) para não parecer que está debochando.';

// ✅ CRÍTICO: Combinar prompt personalizado + instrução de business_hours
let systemPrompt = '';
if (promptFromBody && String(promptFromBody).trim()) {
  // Há prompt personalizado: usar ele + adicionar business_hours
  systemPrompt = String(promptFromBody).trim();
  // Adicionar instrução de business_hours ao final
  systemPrompt += businessHoursInstrucao;
} else if (isSecretary) {
  // Sem prompt personalizado: usar padrão + business_hours
  systemPrompt = defaultSecretaryPrompt + businessHoursInstrucao;
} else {
  // Não é secretária
  systemPrompt = 'Você é um assistente prestativo.';
}

// Instrução sobre áudio (sempre adicionar)
const audioInstrucao = '\n\n📢 MENSAGENS DE ÁUDIO:\nMensagens de áudio do usuário chegam como "[Áudio] <transcrição>" ou "[Áudio em processamento]" quando a transcrição ainda não está pronta. Responda com naturalidade.';
systemPrompt += audioInstrucao;

// Resto do código (knowledge_items, memory_items, departments, etc.)
const knowledgeItems = Array.isArray(body.knowledge_items) ? body.knowledge_items : [];
const contextParts = [];
if (knowledgeItems.length > 0) {
  contextParts.push(knowledgeItems.map(i => '## ' + (i.title || 'Documento') + '\n' + (i.content || '')).join('\n\n'));
}
if (isSecretary && Array.isArray(body.memory_items) && body.memory_items.length > 0) {
  contextParts.push('Histórico relevante do contato:\n' + body.memory_items.map(m => '- ' + (m.content || '')).join('\n'));
}
if (isSecretary && Array.isArray(body.departments) && body.departments.length > 0) {
  contextParts.push('Departamentos para encaminhamento (id, nome, palavras-chave):\n' + body.departments.map(d => '- ' + d.id + ': ' + d.name + ' (' + (d.routing_keywords || []).join(', ') + ')').join('\n'));
}

const context = contextParts.filter(Boolean).join('\n\n');
const model = (body.metadata && body.metadata.model) ? String(body.metadata.model).trim() : (body.model ? String(body.model).trim() : 'llama3.2');
const knowledgeItemsCount = knowledgeItems.length;

function uuid() { 
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/x/g, () => Math.floor(Math.random()*16).toString(16)).replace('y', () => ((Math.floor(Math.random()*4)+8).toString(16))); 
}
const requestId = body.request_id || body.metadata?.request_id || uuid();
const traceId = body.trace_id || body.metadata?.trace_id || uuid();

const useChat = Array.isArray(body.messages) && body.messages.length > 0;

if (useChat) {
  const systemContent = [systemPrompt, context ? 'Contexto para consulta:\n' + context : ''].filter(Boolean).join('\n\n');
  const messages = [
    { role: 'system', content: systemContent },
    ...body.messages.map(m => {
      const role = (m.role || (m.direction === 'incoming' ? 'user' : 'assistant')).toLowerCase();
      const content = normalizarConteudo(m);
      return { role: role === 'user' || role === 'assistant' ? role : 'user', content };
    })
  ];
  return [{ json: { useChat: true, model, messages, knowledgeItemsCount, isSecretary, requestId, traceId } }];
}

const userMessage = normalizarConteudo(body.message || {});
const fullPrompt = [
  systemPrompt,
  context ? 'Contexto para consulta:\n' + context : '',
  'Mensagem do usuário: ' + userMessage
].filter(Boolean).join('\n\n');

return [{ json: { useChat: false, model, fullPrompt, knowledgeItemsCount, isSecretary, requestId, traceId } }];
```

## Pontos Críticos

1. **SEMPRE verificar `business_hours`** mesmo quando há prompt personalizado
2. **SEMPRE adicionar** instrução de `business_hours` ao final do prompt (personalizado ou padrão)
3. **Usar `is_open`** para determinar comportamento (não inventar)
4. **Incluir `next_open_time`** quando fechada

## Exemplo de Prompt Final (com prompt personalizado)

```
Você é uma secretária que faz o encaminhamento...

[resto do prompt personalizado]

⚠️ HORÁRIO DE ATENDIMENTO (OBRIGATÓRIO):
A empresa está FECHADA no momento.
Retornamos em: Segunda-feira, 09:00

REGRAS QUANDO FECHADA:
1. Avise LOGO NO CONTATO INICIAL que estamos fechados...
[...]
```

## Teste

Para testar se está funcionando:

1. Configure um tenant com prompt personalizado
2. Configure `BusinessHours` para estar fechado
3. Envie uma mensagem no Inbox
4. Verifique se a resposta menciona que está fechada e quando reabre

---

**Última Atualização:** 10/02/2026
