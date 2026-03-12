# Design: Open WebUI por tenant (minha LLM no Sense)

> **Status:** Backlog / outro momento. Este doc descreve a integração quando for prioridade; não faz parte do escopo atual (fluxo arrastar-e-soltar, agentes no fluxo, etc.).

## Objetivo

Permitir que cada **tenant** configure sua própria instância do **Open WebUI** (ex.: `ghcr.io/open-webui/open-webui:main` rodando no Docker). Quando configurado, a IA do tenant (Secretária/Bia e, no futuro, agentes do fluxo) usa essa LLM em vez de depender apenas do n8n. O tenant “constrói e conecta” sua própria LLM.

## Open WebUI (referência)

- **API:** OpenAI-compatible em `POST /api/chat/completions`.
- **Auth:** `Authorization: Bearer <API_KEY>` (API key em Settings > Account no Open WebUI).
- **Exemplo:** `curl -X POST http://localhost:8080/api/chat/completions -H "Authorization: Bearer KEY" -H "Content-Type: application/json" -d '{"model":"llama3.1","messages":[{"role":"user","content":"..."}]}'`

## Estado atual no Sense

- **TenantAiSettings:** `n8n_ai_webhook_url`, `agent_model`, `secretary_model`. A Secretária monta o contexto (RAG + memória) no Sense e envia **um POST** para o webhook n8n; o n8n chama o modelo (Ollama, OpenAI, etc.) e devolve a resposta; o Sense envia ao WhatsApp.
- Não existe hoje “URL + API key” de um backend LLM direto por tenant.

## Proposta: Open WebUI opcional por tenant

### 1. Campos no tenant (TenantAiSettings)

- **open_webui_base_url** (URLField, blank=True): URL base do Open WebUI (ex.: `http://open-webui:8080` ou `https://meu-open-webui.empresa.com`). Sem barra no final.
- **open_webui_api_key** (CharField ou TextField, blank=True): API key do Open WebUI (Settings > Account). Em produção considerar criptografia em repouso; mínimo: não logar nem expor em serializers completos.

Quando **ambos** estiverem preenchidos, o Sense usa o Open WebUI como backend de chat para esse tenant (Secretária e, futuramente, nós “Agente” do fluxo). Quando um dos dois estiver vazio, mantém o comportamento atual (n8n).

### 2. Backend: serviço OpenAI-compatible

- **Novo módulo** (ex.: `apps/ai/open_webui_client.py` ou `apps/ai/llm_client.py`):
  - Função que recebe: `base_url`, `api_key`, `model`, `messages` (lista de `{role, content}`), opcional `system`.
  - Monta o body no formato OpenAI Chat Completions e faz `POST {base_url}/api/chat/completions` com `Authorization: Bearer {api_key}`.
  - Retorna o texto da resposta (e opcionalmente tokens/usage se o Open WebUI devolver).
  - Timeout configurável (ex.: 60s); tratamento de erro (rede, 4xx/5xx).

### 3. Integração com a Secretária

- Em **secretary_service.py**, onde hoje se monta o `body` e chama `requests.post(n8n_url, ...)`:
  - Se o tenant tiver `open_webui_base_url` e `open_webui_api_key` preenchidos:
    - Montar `messages` no mesmo formato que já existe (system com contexto RAG + memória, histórico da conversa).
    - Chamar o novo cliente Open WebUI com `tenant.ai_settings.open_webui_base_url`, `open_webui_api_key`, `secretary_model` ou `agent_model`, e `messages`.
    - Usar a resposta como “resposta da assistente” e seguir o fluxo atual (enviar mensagem, triagem, etc.).
  - Caso contrário: manter o fluxo atual (POST para `n8n_ai_webhook_url`).

Assim o tenant pode “trocar” o backend da Secretária para a própria instância Open WebUI sem mudar n8n.

### 3.1 Conexão com o RAG do Sense

Ao chamar o Open WebUI, o Sense **já envia o contexto completo** que monta hoje para o n8n, incluindo o **RAG do tenant**:

- **RAG (base de conhecimento):** o que a Secretária usa hoje vem de `get_secretary_rag_context` (tenant): perfil da empresa / `TenantSecretaryProfile.form_data`, documentos em `AiKnowledgeDocument` com `source=secretary`, e opcionalmente resumos aprovados. Esse bloco é montado em `_build_secretary_context` e vai dentro do system / contexto.
- **Memória por contato:** `get_secretary_memory_for_contact` (fatos, resumos, ações por contato) também entra no contexto enviado.
- **Histórico da conversa:** mensagens recentes já são parte do mesmo contexto.

Ou seja: **não** é "só mandar a pergunta" para o Open WebUI. O Sense monta **RAG + memória + histórico** e envia tudo (por exemplo em uma mensagem de sistema ou no início das mensagens). A LLM do tenant (Open WebUI) recebe a mesma "base de conhecimento" que o n8n receberia — o RAG fica **conectado** porque o Sense injeta esse contexto em toda chamada ao Open WebUI.

- **Implementação:** ao usar o ramo Open WebUI na Secretária, reutilizar o mesmo `_build_secretary_context`; transformar o `body` resultante em `messages` no formato OpenAI (system com RAG + instruções, user/assistant com histórico + última mensagem) e enviar para `/api/chat/completions`. Nenhuma fonte de RAG nova: usar exatamente as que já alimentam o n8n.
- **Futuro (agentes do fluxo):** quando existir o nó "Agente" com RAG por agente/departamento (DESIGN_LLM_AGENTES_FLUXO), o contexto RAG desse agente será montado no Sense e enviado da mesma forma para o Open WebUI do tenant.

### 4. Frontend (Configurações / Integração IA)

- Na tela onde já se configuram webhooks n8n e modelo (ex.: Integração ou Configurações > IA):
  - Nova seção **“Sua LLM (Open WebUI)”**:
    - Campo **URL do Open WebUI** (ex.: `http://open-webui:8080`).
    - Campo **API Key** (tipo password; hint: “Em Open WebUI: Configurações > Conta > API Key”).
  - Opcional: botão **“Testar conexão”** que chama um endpoint no Sense; o backend faz um `POST /api/chat/completions` com uma mensagem de teste e retorna sucesso/falha (sem gravar nada).
- Persistir em `TenantAiSettings` (open_webui_base_url, open_webui_api_key). Só o tenant dono (ou admin) edita.

### 5. Segurança e boas práticas

- Não logar a API key; não retornar a API key no serializer de leitura (apenas mascarada ou omitida).
- Em produção: validar URL (esquema, host) para evitar SSRF; timeout e tamanho máximo de resposta.
- CORS: irrelevante para chamadas backend→Open WebUI; o Open WebUI precisa estar acessível pela rede onde o Sense roda (mesma rede Docker, ou URL pública com HTTPS).

### 6. Futuro: agentes do fluxo (DESIGN_LLM_AGENTES_FLUXO)

- Quando existir o nó “Agente” no fluxo e o modelo **LLMAgent**, cada agente pode usar por padrão o **Open WebUI do tenant** (se configurado): mesma função do cliente, com system_prompt e RAG do agente.
- Opcional depois: permitir “usar Open WebUI do tenant” vs “usar outro backend” por agente.

### 7. Ordem de implementação sugerida

1. Migration: adicionar `open_webui_base_url` e `open_webui_api_key` em `TenantAiSettings`.
2. Cliente: `open_webui_client.py` (ou `llm_client.py`) com função de chat OpenAI-compatible.
3. Secretary: em `secretary_service.py`, ramo “se tenant tem Open WebUI configurado → chamar cliente; senão → n8n”.
4. API de configuração: serializer e PATCH de ai_settings incluindo os dois campos; endpoint opcional “testar conexão Open WebUI”.
5. Frontend: seção Open WebUI na tela de integração/IA e teste de conexão.

---

## Resumo

- **Open WebUI no Docker:** o tenant já tem a imagem rodando; falta o Sense “apontar” para ela.
- **Por tenant:** URL + API key em `TenantAiSettings`; quando preenchidos, Secretária (e depois agentes) usam `POST /api/chat/completions` nessa instância.
- **RAG conectado:** em toda chamada ao Open WebUI o Sense envia o mesmo contexto que usa para o n8n: RAG do tenant (perfil da empresa, AiKnowledgeDocument, resumos), memória por contato e histórico da conversa. A LLM do tenant recebe a base de conhecimento do Sense; não é só “pergunta e resposta” solta.
- **Compatível com o que existe:** se o tenant não configurar Open WebUI, tudo segue via n8n como hoje. Assim o tenant pode construir e conectar sua própria LLM (com RAG do Sense) sem substituir o restante do fluxo.
