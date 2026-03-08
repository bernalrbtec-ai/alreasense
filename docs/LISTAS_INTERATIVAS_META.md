# Listas interativas (Meta)

**Listas interativas:** apenas instâncias Meta (WhatsApp Cloud API), dentro da janela de 24h. Controlado por `allow_meta_interactive_buttons` por tenant (mesma flag dos botões de resposta).

- **Recebimento:** Meta já trata `list_reply`; Evolution trata `listMessage` e `listResponseMessage` (webhook).
- **Envio:** Disponível no composer do chat (ícone de lista) para conversas individuais Meta quando a flag do tenant está ligada. Fora da janela de 24h o envio falha com mensagem clara.
- **Rollback:** Desligar a flag no tenant desativa botões e listas para esse tenant.
