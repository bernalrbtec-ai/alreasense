# Prompt para agente: implementar API oficial Meta (WhatsApp Cloud API)

Use este texto para invocar outro agente que fará a implementação. Um revisor (ou você) revisará o código e corrigirá se necessário.

---

## Texto do prompt (copiar e colar)

```
Implemente a integração com a API oficial da Meta (WhatsApp Cloud API) neste projeto, seguindo rigorosamente o arquivo de instrução do repositório.

**Arquivo de instrução obrigatório:** Leia na íntegra e siga como referência principal:
- docs/PLANO_IMPLEMENTACAO_API_META_WHATSAPP.md

Se precisar de mais detalhes (diagramas, SQL completo, tabelas de risco), consulte também:
- .cursor/plans/api_oficial_meta_whatsapp_0fc416a3.plan.md (se disponível no seu contexto)

**Contexto já definido:**
- Trabalhe sempre no branch `feature/meta-official-api` (staging). Não altere produção (main).
- O schema do banco já foi alterado: as colunas `integration_type`, `phone_number_id`, `access_token` (e opcionais) já existem na tabela `notifications_whatsapp_instance`. Não crie migrations Django e não rode o script SQL novamente.
- Staging está no Railway; guia em docs/STAGING_RAILWAY.md.

**O que implementar (nessa ordem):**
1. **Fase 1:** Adicionar no model Python `WhatsAppInstance` os campos do plano (integration_type, phone_number_id, access_token, etc.) e variáveis de config para o webhook Meta.
2. **Fase 2:** Rota `/webhooks/meta/` (GET + POST), validação de assinatura, helper `get_whatsapp_instance_for_meta(phone_number_id)`, idempotência por wamid, criação de Conversation/Message e tratamento de mídia recebida (URL da Meta, sem getBase64FromMediaMessage).
3. **Fase 3:** Providers de envio (interface, EvolutionProvider, MetaCloudProvider, get_sender).
4. **Fase 4:** Trocar chamadas diretas à Evolution por get_sender(instance) em tasks, campanhas, notificações, transfer, proxy; no-op para Meta em generate_qr_code/check_connection_status; filtrar Meta em health e proxy.
5. **Fase 5:** Frontend de conexões com tipo Evolution vs API oficial Meta e campos/token/Validar para Meta.
6. **Fase 6:** Modelo e fluxo de templates; janela 24h; envio por template quando fora da janela.
7. **Fase 7:** Read receipt Meta, desabilitar edição para conversas Meta no frontend, e ajustes finais.

**Regras fixas (respeitar em todo o código):**
- Em qualquer uso de EvolutionConnection ou URLs Evolution (QR, status, proxy, health), checar `integration_type == 'meta_cloud'` e fazer no-op/early return para instâncias Meta.
- No webhook Meta: se instância não encontrada ou em erro, logar e retornar 200 (evitar retentativas infinitas da Meta).
- Sempre verificar idempotência por wamid antes de criar Message no webhook Meta.
- Incluir provider=evolution|meta nos logs de envio e webhook.

Ao terminar cada fase, deixe o código consistente e testável. Outro agente fará a revisão e correções se necessário.
```

---

## Uso

1. Abra um novo chat com o agente que fará a implementação.
2. Cole o conteúdo da seção **Texto do prompt** acima (entre as linhas com ```).
3. Opcional: anexe ou referencie `docs/PLANO_IMPLEMENTACAO_API_META_WHATSAPP.md` para garantir que o agente tenha o arquivo de instrução no contexto.
4. Após a implementação, use outro agente (ou você) para revisar e corrigir se necessário.
