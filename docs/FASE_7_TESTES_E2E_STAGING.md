# Fase 7 – Testes E2E e Staging (Evolution + Meta)

Checklist para validar a Fase 7 e o fluxo completo no staging.

## 1. Read receipt (mark as read) – Meta

- [ ] **Instância Meta:** Abrir uma conversa que recebeu mensagem do contato; aguardar ~2,5s (frontend chama `POST /chat/conversations/{id}/mark_as_read/`).
- [ ] **Backend:** Verificar nos logs que o read receipt foi enviado via Meta (ex.: `[READ RECEIPT] Meta: confirmação de leitura enviada`).
- [ ] **WhatsApp do contato:** Confirmar que a mensagem aparece com ✓✓ azul (lida).
- [ ] **Instância Evolution:** Repetir com conversa Evolution e confirmar que o check azul continua funcionando (Evolution API `markMessageAsRead`).

## 2. Edição de mensagem desabilitada – Meta

- [ ] **Conversa Meta:** Abrir conversa de instância com integração “API oficial Meta”; clicar com o botão direito em uma mensagem **enviada por nós** (outgoing).
- [ ] **Menu de contexto:** A opção **“Editar”** não deve aparecer (ou deve estar desabilitada).
- [ ] **Conversa Evolution:** Em conversa Evolution, a opção **“Editar”** deve aparecer para mensagens enviadas (dentro do prazo e sem anexo).

## 3. Testes gerais no staging

- [ ] **Conexões:** Criar/editar instância Evolution (QR) e instância Meta (Phone Number ID + Token); Validar Meta.
- [ ] **Recebimento:** Enviar mensagem do celular para o número Meta; verificar que a mensagem aparece no chat e que a conversa usa `integration_type: 'meta_cloud'` (ex.: na resposta da API de conversas).
- [ ] **Envio:** Enviar texto em conversa Meta (dentro da janela 24h); enviar template em conversa Meta fora da janela 24h.
- [ ] **Campanhas:** Campanha com instância Meta exige template; enviar campanha e confirmar uso de template.
- [ ] **Read receipt:** Conferir ✓✓ azul para Evolution e para Meta após abrir a conversa.

## 4. Observações

- **Token Meta:** Em staging, usar System User (token permanente) para evitar expiração em 24h (ver `docs/STAGING_RAILWAY.md`).
- **Webhook:** URL do webhook Meta deve estar configurada no Meta Business Suite e apontando para o servidor de staging.
