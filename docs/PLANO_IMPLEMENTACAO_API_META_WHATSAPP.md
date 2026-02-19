# Plano: Evolution (como está) + API oficial Meta na mesma aplicação

**Arquivo de instrução para implementação.** Este documento é a referência única para o agente que implementar a integração com a API oficial da Meta (WhatsApp Cloud API).

---

## Contexto

- **Hoje:** Toda a integração WhatsApp passa pela Evolution API (Baileys). Envio, recebimento, conexão (QR), mídia e status dependem de endpoints Evolution e do webhook em `/webhooks/evolution/`.
- **Objetivo:** Manter esse fluxo intacto e, em paralelo, permitir que **instâncias oficiais** usem a **API Cloud da Meta** diretamente (sem Evolution), com chat funcionando para os dois tipos.

## Pré-requisito: Staging

- **Branch:** `feature/meta-official-api`. Todo código deve ser feito neste branch (deploy apenas no staging).
- **Banco:** As colunas `integration_type`, `phone_number_id`, `access_token` (e opcionais) **já existem** na tabela `notifications_whatsapp_instance` (SQL já foi aplicado). **Não criar migrations Django.** Não rodar o script SQL de novo.
- **Guia staging:** [docs/STAGING_RAILWAY.md](STAGING_RAILWAY.md).

---

## Ordem de implementação (Fases 1 a 7)

Implementar **nesta ordem**. Cada fase depende da anterior.

| # | Fase | O que fazer |
|---|------|-------------|
| 1 | **Modelo e config** | Adicionar no **model Python** `WhatsAppInstance` ([backend/apps/notifications/models.py](backend/apps/notifications/models.py)) os campos: `integration_type` (default `'evolution'`), `phone_number_id`, `access_token`, `business_account_id`, `app_id`, `access_token_expires_at` (tipos e null/blank alinhados ao schema já existente no banco). Adicionar em `settings` leitura de `WHATSAPP_CLOUD_VERIFY_TOKEN` e `WHATSAPP_CLOUD_APP_SECRET`. **Sem migrations.** |
| 2 | **Webhook Meta** | Criar rota `/webhooks/meta/` (GET verificação + POST). GET: retornar `hub.challenge` se `hub.verify_token` == config. POST: validar assinatura `X-Hub-Signature-256`; parser `entry[].changes[].value`; helper `get_whatsapp_instance_for_meta(phone_number_id)`; idempotência por `wamid`; criar Conversation (instance_name = phone_number_id em string) e Message; mídia via URL da Meta (não usar getBase64FromMediaMessage). Em erro, logar e retornar 200. |
| 3 | **Providers de envio** | Criar módulo de providers (ex.: `backend/apps/chat/providers/` ou `backend/apps/notifications/whatsapp_providers/`): interface (ABC) com `send_text`, `send_media`, `send_audio_ptt`, `send_reaction`, `send_location`; `EvolutionProvider` (encapsular chamadas atuais); `MetaCloudProvider` (Graph API v21.0, Bearer token); `get_sender(instance)` que valida campos e retorna o provider conforme `integration_type`. |
| 4 | **Integração do provider** | Substituir chamadas diretas à Evolution por `get_sender(instance)` em: [backend/apps/chat/tasks.py](backend/apps/chat/tasks.py), campanhas (services, views, rabbitmq_consumer, apps), notificações (views, services), [backend/apps/chat/api/views.py](backend/apps/chat/api/views.py) (transfer), [backend/apps/proxy/services.py](backend/apps/proxy/services.py). Em `generate_qr_code`, `check_connection_status`, `disconnect`, `logout` do model WhatsAppInstance: se `integration_type == 'meta_cloud'`, retornar cedo (no-op). Em health e proxy: filtrar por `integration_type='evolution'` onde listar instâncias. **Atenção:** Fase de maior risco (muitos arquivos); implementar **log verboso** em `get_sender`/provider: em toda resolução registrar `instance_id`, `integration_type`, provider retornado; em erros, logar contexto completo. |
| 5 | **Frontend conexões** | Em [frontend/src/pages/ConnectionsPage.tsx](frontend/src/pages/ConnectionsPage.tsx) e ConfigurationsPage: seleção "Evolution (QR)" vs "API oficial Meta"; se Meta, mostrar campos Phone Number ID, Access Token (e opcional Business Account ID), botão Validar; sem QR. |
| 6 | **Templates e 24h** | Modelo e CRUD de templates (ex.: WhatsAppTemplate); verificação de janela 24h (apenas **inbound** do contato; ver edge cases na seção “Revisões e atenções especiais”, incluindo **race: webhook atrasado + resposta do agente antes do commit**); no envio Meta, se fora da janela usar template; campanhas para instância Meta só com template. Incluir nos testes da Fase 6 o cenário de race (webhook atrasado, resposta antes da inbound persistida). |
| 7 | **Ajustes e E2E** | Read receipt Meta no provider; desabilitar edição de mensagem no frontend para conversas de instância Meta; testes. |

---

## Regras obrigatórias

- **Nunca** criar migrations Django para estas alterações de schema.
- **Sempre** checar `integration_type == 'meta_cloud'` antes de usar EvolutionConnection ou URLs Evolution (QR, connectionState, fetchInstances, proxy, health).
- **Webhook Meta:** Se instância não encontrada por `phone_number_id`, logar e retornar 200 (não 4xx/5xx). Idempotência por `wamid` antes de criar Message.
- **Lookup de instância a partir de conversa:** Se `Conversation.instance_name` for numérico (só dígitos), tentar `WhatsAppInstance.objects.filter(phone_number_id=..., integration_type='meta_cloud')`; senão lookup atual por `instance_name`/`evolution_instance_name`.
- **Logs:** Incluir `provider=evolution|meta` e `instance_id` nos logs de envio e webhook.

---

## Revisões e atenções especiais

- **Fase 6 (templates e janela 24h)** — É a mais complexa e subestimada. Regra: janela 24h baseada **só em mensagens inbound** do contato (última com `created_at` &gt; agora − 24h). Edge cases: (1) **Última mensagem = template nosso:** mensagem de saída não abre/renova a janela; a verificação deve considerar apenas mensagens **incoming** do contato. (2) **Status atrasado da Meta:** não depender de delivered/read para “dentro da janela”; usar apenas a existência da mensagem inbound no banco. (3) **Webhook atrasado + race condition (crítico):** o contato envia mensagem, o webhook da Meta chega com atraso e o processamento entra em fila; se o agente tentar responder **enquanto** esse processamento ainda não persistiu a Message no banco, a verificação “dentro da janela” pode não ver a nova inbound e forçar template (ou rejeitar texto livre) indevidamente. **Mitigação:** garantir que a decisão “dentro da janela” use sempre uma leitura consistente do banco (ex.: a tarefa do webhook persiste a Message antes de notificar o frontend/WebSocket, para que ao abrir a conversa e enviar a resposta a mensagem já exista); ou serializar por conversa (processar webhook antes de permitir envio na mesma conversa). **Testes Fase 6:** incluir cenário explícito “webhook atrasado, agente responde antes do commit da inbound” e validar que a resposta não é incorretamente forçada a template.
- **Token em staging** — Token temporário (24h) expira no meio dos testes. **Recomendação:** configurar **System User** com token permanente (long-lived / nunca expira na prática) **antes** de começar os testes de verdade no staging; caso contrário, o token de 24h será dor de cabeça constante.
- **Fase 4 (integração do provider)** — É a mais arriscada pelo volume de arquivos (tasks, campanhas, notificações, proxy). Um `get_sender(instance)` retornando o provider errado pode quebrar coisas sem erro aparente. **Obrigatório:** log **bem verboso** na camada de provider: em toda chamada a `get_sender(instance)` registrar `instance_id`, `integration_type`, provider escolhido (`evolution`|`meta`); em falhas de validação ou envio, logar contexto completo (conversation_id, instance_id, provider, erro).
- **Renovação do token (access_token_expires_at)** — O plano inclui o campo `access_token_expires_at` mas **nenhuma fase** implementa renovação automática do token. **Decisão:** tratar como **manual por enquanto**; renovação automática fica **fora do escopo inicial**. Para evitar expiração em produção/staging, usar **System User** com token permanente quando possível; quando for token de usuário/long-lived (60 dias), documentar no STAGING_RAILWAY ou no painel que o token deve ser renovado manualmente (e opcionalmente usar `access_token_expires_at` para alertar ou exibir “token expira em X dias” na UI).

---

## Referências no código

- Envio Evolution atual: [backend/apps/chat/tasks.py](backend/apps/chat/tasks.py), [backend/apps/common/services/evolution_api_service.py](backend/apps/common/services/evolution_api_service.py).
- Webhook Evolution: [backend/apps/connections/webhook_views.py](backend/apps/connections/webhook_views.py), [backend/apps/chat/webhooks.py](backend/apps/chat/webhooks.py).
- Modelo WhatsAppInstance: [backend/apps/notifications/models.py](backend/apps/notifications/models.py).
- Meta: [Webhooks](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/reference/messages/), [Send messages](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages/).

---

## Checklists detalhados (seção 11 do plano completo)

- **Webhook Meta:** GET (hub.verify_token, hub.challenge); POST (assinatura HMAC, entry/changes/value, phone_number_id, get_whatsapp_instance_for_meta, idempotência wamid, criar Conversation/Message, statuses); em exceção retornar 200.
- **Provider Meta:** Validar phone_number_id e access_token no construtor; POST Graph API com Bearer; tratar 401/403/429; reação, read receipt, mídia (upload Media API depois envio por id).
- **Pontos de falha:** Instância não encontrada → 200; token expirado → tratar 401; não duplicar mensagem (wamid); EvolutionConnection no-op para Meta; proxy/health filtrar Evolution; mídia Meta não usar getBase64FromMediaMessage.

O plano completo (com diagramas, SQL, tabelas de risco e todos os checklists) está em `.cursor/plans/api_oficial_meta_whatsapp_0fc416a3.plan.md`; use este documento como instrução principal e consulte o plano completo em caso de dúvida sobre detalhes.
