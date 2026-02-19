# Revisão Fases 1–4: Integração API oficial Meta (WhatsApp Cloud API)

**Referência:** `docs/PLANO_IMPLEMENTACAO_API_META_WHATSAPP.md`  
**Data da revisão:** 2025-02-19

---

## 1. Checklist: conforme vs não conforme

### Fase 1 — Modelo e config

| Item | Status | Observação |
|------|--------|------------|
| Campos no model `WhatsAppInstance`: `integration_type`, `phone_number_id`, `access_token`, `business_account_id`, `app_id`, `access_token_expires_at` | ✅ Conforme | Tipos e null/blank alinhados ao schema (CharField/TextField/DateTimeField). |
| `integration_type` default `'evolution'` | ✅ Conforme | `default=INTEGRATION_TYPE_EVOLUTION`. |
| Settings: `WHATSAPP_CLOUD_VERIFY_TOKEN` e `WHATSAPP_CLOUD_APP_SECRET` | ✅ Conforme | Lidos via `config()` em `alrea_sense/settings.py`. |
| Nenhuma migration Django criada | ✅ Conforme | Nenhum novo arquivo em `notifications/migrations/` para esses campos. |

### Fase 2 — Webhook Meta

| Item | Status | Observação |
|------|--------|------------|
| Rota `/webhooks/meta/` (GET + POST) | ✅ Conforme | Registrada em `alrea_sense/urls.py`; também `/webhooks/meta` sem barra. |
| GET: retornar `hub.challenge` se `hub.verify_token` == config | ✅ Conforme | `meta_webhook_view` compara token e retorna challenge. |
| POST: validar assinatura `X-Hub-Signature-256` | ✅ Conforme | `_verify_meta_signature()` com HMAC SHA256. |
| Parser `entry[].changes[].value`; `get_whatsapp_instance_for_meta(phone_number_id)` | ✅ Conforme | Implementado em `meta_webhook.py`. |
| Idempotência por `wamid` antes de criar Message | ✅ Conforme | `Message.objects.filter(message_id=wamid).exists()` antes de `create`. |
| Criar Conversation (instance_name = phone_number_id) e Message | ✅ Conforme | `_get_or_create_conversation_meta`, depois `Message.objects.create`. |
| Mídia via URL da Meta (não getBase64FromMediaMessage) | ✅ Conforme | Apenas `meta_media_id` no metadata; download via Graph API. |
| Em erro ou instância não encontrada: logar e retornar 200 | ✅ Conforme | Try/except e `continue`/return sempre com `HttpResponse(status=200)`. |
| Message persistida **antes** de notificar WebSocket | ⚠️ Parcial | Message é criada e não há broadcast de nova mensagem no webhook Meta. Quando for adicionado `broadcast_message_received`, deve ser **apenas após** `Message.objects.create`. Hoje não há notificação em tempo real para mensagens Meta (só para nova conversa). |

### Fase 3 — Providers

| Item | Status | Observação |
|------|--------|------------|
| Interface (ABC) com `send_text`, `send_media`, `send_audio_ptt`, `send_reaction`, `send_location` | ✅ Conforme | `WhatsAppSenderBase` em `whatsapp_providers/base.py`. |
| EvolutionProvider encapsulando chamadas atuais | ✅ Conforme | `whatsapp_providers/evolution.py`; usa endpoints Evolution. |
| MetaCloudProvider com Graph API v21.0 e Bearer token | ✅ Conforme | `GRAPH_API_BASE = "https://graph.facebook.com/v21.0"`; header `Authorization: Bearer`. |
| `get_sender(instance)` valida campos e retorna provider conforme `integration_type` | ✅ Conforme | Validação de `phone_number_id`/`access_token` (Meta) e `api_url`/`instance_name` (Evolution). |
| Meta: tratar 401/403/429 | ✅ Conforme | `_request` em `meta_cloud.py` trata esses status. |

### Fase 4 — Integração do provider

| Item | Status | Observação |
|------|--------|------------|
| Substituir chamadas diretas à Evolution por `get_sender(instance)` em **tasks.py** | ✅ Conforme | Envio principal usa `get_sender(instance)` e provider (texto, mídia, áudio, localização). |
| Substituir em **campanhas** (services, views, rabbitmq_consumer, apps) | ✅ Conforme | Campanhas usam `get_sender(instance)` e provider em views, rabbitmq_consumer, services e apps (task notifications). Presence/health com no-op para Meta. |
| Substituir em **notificações** (views, services) | ✅ N/A | Notificações usam task `send_message_to_evolution` ou caminhos que já passam por tasks. |
| Substituir em **chat api views (transfer)** | ✅ Conforme | Transfer usa lookup unificado (instance_name / phone_number_id numérico) e `get_sender(wa_instance)` + `sender.send_text()` para mensagem automática. |
| Substituir em **proxy/services.py** | ✅ N/A | Proxy usa EvolutionAPIManager para rotação e notificação; não envia mensagem de chat via nosso model. Lista instâncias da API Evolution, não do nosso banco. |
| `generate_qr_code`, `check_connection_status`, `disconnect`: no-op para `integration_type == 'meta_cloud'` | ✅ Conforme | Early return em todos os três. |
| `logout`: no-op para Meta | ✅ N/A | Método `logout` não existe no model `WhatsAppInstance`. |
| Health e proxy: filtrar por `integration_type='evolution'` onde listar instâncias | ⚠️ Parcial | Health: adicionado `evolution_count` em `registered_instances`; não há “listagem” que exclua Meta. Proxy: lista vinda da API Evolution (só Evolution). |
| Log verboso em `get_sender`/provider (instance_id, integration_type, provider; em erros contexto completo) | ⚠️ Parcial | Providers logam `instance_id` e `provider=evolution|meta` em envio; **get_sender** não loga em **sucesso** (só em warning quando falha). Plano exige registrar em **toda** resolução. |

---

## 2. Gaps e desvios (com arquivo e trecho)

### 2.1 Campanhas ainda usam Evolution direto

- **Arquivos:**  
  - `backend/apps/campaigns/views.py` (por volta de 744–769): `send_reply_via_evolution` usa `EvolutionConnection`, `wa_instance.api_url`, `api_key`, POST para Evolution.  
  - `backend/apps/campaigns/rabbitmq_consumer.py` (por volta de 661–876): `_send_whatsapp_message_async` usa `instance.api_url`, `instance.instance_name`, `f"{instance.api_url}/message/sendText/{instance.instance_name}"`.  
  - `backend/apps/campaigns/services.py` (por volta de 354, 391, 631): URLs Evolution para sendText e connectionState.
- **Desvio:** Nenhum uso de `get_sender(instance)`; instâncias Meta quebravam ou seriam ignoradas (api_url vazio).
- **Recomendação:** Em campanhas, resolver instância (já feita) e, para envio de mensagem, usar `get_sender(instance)` e `provider.send_text` (e, na Fase 6, template quando fora da janela). Para status/connectionState, fazer no-op ou skip para `integration_type == 'meta_cloud'`.

### 2.2 Transfer (chat api views) usa Evolution direto

- **Arquivo:** `backend/apps/chat/api/views.py` (por volta de 3704–3748).
- **Trecho relevante:** Busca `wa_instance` e `evolution_server`, monta `base_url`/`api_key`/`instance_name` e chama `client.post(f"{base_url}/message/sendText/{instance_name}", ...)`.
- **Desvio:** Não verifica `integration_type`; não usa `get_sender(instance)`. Conversas Meta não receberiam mensagem de transferência ou usariam dados Evolution incorretos.
- **Recomendação:** Se `wa_instance.integration_type == 'meta_cloud'`, usar `get_sender(wa_instance)` e `sender.send_text(..., message=transfer_message_text)`; caso contrário, manter fluxo Evolution atual (ou também migrar para get_sender para um único caminho).

### 2.3 get_sender sem log em sucesso

- **Arquivo:** `backend/apps/notifications/whatsapp_providers/get_sender.py`.
- **Desvio:** Plano (e “Revisões e atenções especiais”) exige: em toda chamada a `get_sender(instance)` registrar `instance_id`, `integration_type` e provider escolhido (`evolution`|`meta`). Hoje só há log em falha (warning).
- **Recomendação:** Ao retornar provider (Evolution ou Meta), logar em nível info: `instance_id`, `integration_type`, `provider='evolution'|'meta'`.

### 2.4 Webhook Meta não notifica nova mensagem via WebSocket

- **Arquivo:** `backend/apps/connections/meta_webhook.py`.
- **Desvio:** Após `Message.objects.create` não há chamada a `broadcast_message_received` (ou equivalente). Novas mensagens Meta não aparecem em tempo real no frontend; só nova conversa é notificada (`broadcast_conversation_updated` em nova Conversation).
- **Recomendação:** Para Fase 6 (e consistência com Evolution), após persistir a Message, chamar `broadcast_message_received(new_msg)` **depois** do `create`, garantindo ordem “persistir → depois notificar” para evitar race.

### 2.5 Transfer não considera conversa Meta (instance_name numérico)

- **Arquivo:** `backend/apps/chat/api/views.py` (lookup de instância na transfer).
- **Desvio:** Uso de `WhatsAppInstance.objects.filter(tenant=..., is_active=True, status='active').first()` não considera `conversation.instance_name` como `phone_number_id` (lookup por instância da conversa). Para conversas Meta, `instance_name` é o phone_number_id; o plano exige esse lookup.
- **Recomendação:** Na transfer, resolver instância como em tasks: se `conversation.instance_name` estiver preenchido, buscar por `instance_name`/`evolution_instance_name` ou, se numérico, por `phone_number_id` + `integration_type='meta_cloud'`; depois usar `get_sender(wa_instance)` para enviar.

---

## 3. Ajustes recomendados (antes da Fase 5)

### Obrigatórios

1. **get_sender — log em sucesso**  
   Em `get_sender`, ao retornar `EvolutionProvider` ou `MetaCloudProvider`, logar (info): `instance_id`, `integration_type`, `provider='evolution'|'meta'`.  
   **✅ Aplicado:** log info com `provider=meta|evolution`, `instance_id`, `integration_type`; warning em ValueError com contexto completo.

2. **Transfer — usar get_sender e considerar Meta**  
   Em `chat/api/views.py` (transfer):  
   - Resolver instância a partir da conversa (instance_name / phone_number_id quando numérico).  
   - Se `integration_type == 'meta_cloud'`, não usar Evolution; usar `get_sender(wa_instance)` e `sender.send_text(...)` para a mensagem de transferência.  
   - Manter envio Evolution para instâncias Evolution (ou unificar tudo via get_sender).

3. **Campanhas — usar get_sender para envio**  
   Em campanhas (views, rabbitmq_consumer, services): onde hoje se monta URL Evolution e envia texto (ou mídia), passar a usar `get_sender(instance)` e o método correspondente do provider. Para health/connectionState de instância, fazer no-op ou filtrar para `integration_type='evolution'`.

### Recomendados (podem ser Fase 5 ou 6)

4. **Webhook Meta — broadcast após criar Message**  
   Em `_process_meta_value`, após `Message.objects.create`, chamar `broadcast_message_received(new_msg)` para atualizar o chat em tempo real (sempre **depois** do create, para evitar race na Fase 6).

5. **Lookup de instância na transfer**  
   Alinhar o lookup de `wa_instance` na transfer ao usado em tasks: por `conversation.instance_name` (e, se numérico, por `phone_number_id` + `integration_type='meta_cloud'`).

---

## 4. Resumo

- **Fase 1 e 3:** Implementação alinhada ao plano; apenas enriquecer log em `get_sender`.  
- **Fase 2:** Alinhada; garantir que qualquer notificação WebSocket futura seja feita **após** persistir a Message.  
- **Fase 4:** tasks.py e no-ops no model estão conformes; **campanhas** e **transfer** ainda usam Evolution direto e devem migrar para `get_sender(instance)` e considerar Meta; log verboso em `get_sender` em sucesso deve ser adicionado.

Aplicando em seguida o ajuste de **log verboso em get_sender (sucesso)**.
