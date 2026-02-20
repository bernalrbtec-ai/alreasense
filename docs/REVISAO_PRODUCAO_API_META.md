# Revisão para produção – Integração API Meta (WhatsApp)

Resumo do que foi revisado e ajustado para uso em produção.

## 1. Segurança – Webhook Meta

- **Antes:** Se `WHATSAPP_CLOUD_APP_SECRET` não estivesse configurado, a assinatura era ignorada e o POST era aceito (qualquer um poderia enviar payloads falsos).
- **Agora:** Se o header `X-Hub-Signature-256` estiver presente e o `WHATSAPP_CLOUD_APP_SECRET` não estiver configurado, o POST **não é processado** (retorna 200 para não gerar retentativas da Meta, mas não persiste nada). Em produção, configure sempre `WHATSAPP_CLOUD_APP_SECRET`.

## 2. Logs – Menos PII e menos ruído

- **Meta provider:** Removido log que incluía parte do número de telefone (`to[:4]***`). Envio de texto agora loga apenas em DEBUG (`instance_id`).
- **get_sender:** Logs de “provider=meta/evolution” passaram de INFO para DEBUG para não encher o log a cada mensagem em produção.

## 3. Performance – Serializer de conversas

- **get_integration_type:** Passou a usar cache de 2 minutos (`conv_integration_type:{tenant_id}:{instance_name}`) para evitar N+1 ao listar muitas conversas. O frontend continua recebendo `integration_type` para esconder “Editar” em conversas Meta.

## 4. Robustez – Envio e read receipt

- **tasks.py (template fora da janela 24h):** Validação de `wa_template_id` do metadata: se não for um UUID válido, a mensagem é marcada como falha com “Template inválido (ID inválido)” em vez de deixar o filtro do ORM falhar ou retornar vazio sem mensagem clara.
- **send_read_receipt (Evolution):** Quando `connection_state` for `None` (ex.: instância que nunca atualizou estado), o envio do read receipt é **tentado** em vez de bloqueado. Antes, `None not in ('open', 'connected')` fazia sempre pular o envio.

## 5. Documentação

- **FASE_7_TESTES_E2E_STAGING.md:** Texto ajustado para produção: checklist genérico, observações de produção (webhook, token, APP_SECRET) e remoção de referências exclusivas a staging.

## Pontos de atenção em produção

| Ponto | Ação |
|-------|------|
| **WHATSAPP_CLOUD_APP_SECRET** | Obrigatório se receber webhooks Meta; sem ele, POSTs assinados são rejeitados. |
| **WHATSAPP_CLOUD_VERIFY_TOKEN** | Necessário para o GET de verificação do webhook no Meta Business. |
| **Token Meta** | Preferir System User (token permanente). Token de usuário expira; renovação ainda é manual. |
| **Templates** | Campanhas e notificações de tarefas com instância Meta exigem pelo menos um template ativo (WhatsApp Templates). |
| **Janela 24h** | Fora da janela, só é possível enviar com template; o frontend precisa enviar `wa_template_id` no metadata da mensagem quando o usuário escolher um template. |

## Possíveis falhas a monitorar

- **401/403 do Graph API:** Token expirado ou revogado; verificar logs do provider Meta e alertar.
- **429 (rate limit):** Meta limita envios; backoff já existe no código; monitorar se ocorre com frequência.
- **Instância não encontrada no webhook:** Log “Instância não encontrada para phone_number_id”; em produção, pode indicar número desvinculado ou `phone_number_id` errado no cadastro.
- **Read receipt Meta:** Se `message_id` (wamid) estiver vazio na mensagem recebida, o read receipt é pulado; normalmente toda mensagem do webhook tem `id`.
