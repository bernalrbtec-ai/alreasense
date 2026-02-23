# Workflow n8n: Gateway IA teste (assíncrono)

Workflow para importar no n8n quando o Sense usa **fluxo assíncrono** (`GATEWAY_TEST_USE_ASYNC=true`).

## Importar

- No n8n: menu (três pontos) → **Import from File** → selecione `n8n_gateway_ia_teste_async.json`.
- Ou copie o conteúdo do JSON e use **Import from Clipboard** (Ctrl+V no editor).

## O que o workflow faz

1. **Webhook** (`POST /gateway-ia`): recebe o payload do Sense (com `job_id`, `callback_url`, `request_id`, `trace_id` quando async).
2. **Router**: se existir `job_id` e `callback_url` → fluxo **deferred**; senão → fluxo **síncrono** (resposta direta).
3. **Fluxo deferred**  
   - Responde **na hora** com `{ "deferred": true, "job_id": "..." }`.  
   - Em seguida: monta prompt → chama Ollama (chat ou generate) → formata resposta → **POST no callback_url** com o resultado (header `X-Gateway-Callback-Token` e body `job_id`, `status`, `request_id`, `trace_id`, `response`).
4. **Fluxo síncrono**  
   - Monta prompt → Ollama → formata → **Respond to Webhook** com a resposta (comportamento atual).

## Configuração obrigatória

1. **URL do Ollama**  
   Nos nós "Ollama chat (async)", "Ollama generate (async)", "Ollama chat (sync)", "Ollama generate (sync)" troque `http://172.16.20.66:11434` pela URL da sua instância (ou use credencial n8n).

2. **Token do callback**  
   No nó **"POST callback Sense"**, no header `X-Gateway-Callback-Token`, substitua o valor placeholder pelo **mesmo valor** da variável `GATEWAY_TEST_CALLBACK_TOKEN` configurada no Sense.  
   (No n8n você pode usar variável de ambiente ou credencial em vez de texto fixo.)

3. **Path do webhook**  
   O workflow usa o path `gateway-ia`. A URL completa do webhook no n8n deve ser a mesma que está em **Sense → Configurações > IA > Webhook da IA** (e em `GATEWAY_TEST_CALLBACK_BASE_URL` para o callback).

## Callback em caso de erro

Se a chamada à IA falhar, o workflow atual **não** chama o callback com `status: "error"`. Para não deixar o frontend em “Deixe-me pensar...” para sempre, você pode:

- Adicionar um nó **Catch** / **Error Trigger** que, em caso de falha, faça um POST no `callback_url` com `{ "job_id": "...", "status": "error", "error_message": "..." }`, usando o mesmo header de token.

## Substituir o workflow atual

Se você já tem o workflow “Sense - Gateway IA (teste e Secretária)” no mesmo path `gateway-ia`:

- Ou **substitua** pelo import deste JSON (path continua `gateway-ia`).  
- Ou **desative** o antigo e **ative** este; mantenha o mesmo path para o Sense não precisar de mudança de URL.
