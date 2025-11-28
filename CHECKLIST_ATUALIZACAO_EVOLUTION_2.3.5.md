# ✅ Checklist de Atualização Evolution API 2.3.3 → 2.3.5

## 📋 Pré-Atualização

- [ ] Fazer backup do banco de dados
- [ ] Documentar versão atual (2.3.3)
- [ ] Verificar logs atuais funcionando

## 🔄 Durante a Atualização

- [ ] Atualizar imagem Docker: `atendai/evolution-api:latest` ou `evoapicloud/evolution-api:latest`
- [ ] Reiniciar containers
- [ ] **REAUTORIZAR WhatsApp** (gerar novo QR Code e escanear)
- [ ] Verificar se instâncias estão conectadas

## ✅ Testes Pós-Atualização

### 1. Envio de Mensagens Básicas
- [ ] Enviar mensagem de texto simples
- [ ] Enviar mensagem com anexo (imagem)
- [ ] Enviar mensagem com anexo (vídeo)
- [ ] Enviar mensagem com anexo (áudio)
- [ ] Enviar mensagem com anexo (documento)

### 2. Reply (Resposta) - ⚠️ CRÍTICO
- [ ] Responder mensagem recebida (individual)
- [ ] Responder mensagem recebida (grupo)
- [ ] Responder mensagem enviada por nós
- [ ] Verificar se aparece como reply no WhatsApp
- [ ] Verificar se `participant` está correto nos logs

### 3. Forward (Encaminhar) - ⚠️ CRÍTICO
- [ ] Encaminhar mensagem de texto
- [ ] Encaminhar mensagem com anexo
- [ ] Encaminhar para conversa diferente
- [ ] Verificar se anexos são copiados corretamente

### 4. Delete (Apagar) - ⚠️ CRÍTICO
- [ ] Marcar mensagem como apagada (local)
- [ ] Receber webhook `messages.delete` quando mensagem é apagada no WhatsApp
- [ ] Verificar se UI atualiza corretamente

### 5. Webhooks
- [ ] Receber `messages.upsert` (nova mensagem)
- [ ] Receber `messages.update` (status: sent/delivered/read)
- [ ] Receber `messages.delete` (mensagem apagada)
- [ ] Receber `chats.update` (atualização de chat)
- [ ] Receber `contacts.update` (atualização de contato)

### 6. Grupos
- [ ] Enviar mensagem em grupo
- [ ] Menções em grupo funcionando
- [ ] Reply em grupo funcionando
- [ ] Buscar participantes do grupo

### 7. Status de Mensagens
- [ ] Verificar status `pending` → `sent` → `delivered` → `seen`
- [ ] Verificar se timestamps estão corretos

## 🔍 Endpoints Usados (Verificar se continuam funcionando)

### Envio de Mensagens
- `POST /message/sendText/{instance}` - Envio de texto
- `POST /message/reply/{instance}` - Reply (pode não existir, usar fallback)
- `POST /message/sendMedia/{instance}` - Envio de mídia
- `POST /message/sendWhatsAppAudio/{instance}` - Envio de áudio PTT

### Outros
- `DELETE /chat/deleteMessageForEveryone/{instance}` - Apagar mensagem (pode não funcionar)
- `GET /group/getParticipants/{instance}` - Buscar participantes
- `GET /group/findGroupInfos/{instance}` - Info do grupo

## ⚠️ Possíveis Problemas Conhecidos

1. **QR Code não gera**: Verificar se `CONFIG_SESSION_PHONE_VERSION` está comentada no `.env`
2. **Reautorização necessária**: Sempre necessário após atualização
3. **Endpoints podem mudar**: Verificar documentação oficial

## 📝 Logs para Monitorar

Após atualização, monitorar logs para:
- Erros 404 em endpoints
- Erros de autenticação
- Webhooks não chegando
- Mensagens não sendo enviadas

## 🔗 Documentação

- [Evolution API Docs](https://doc.evolution-api.com/)
- [GitHub Issues](https://github.com/EvolutionAPI/evolution-api/issues)

## 📞 Se Algo Quebrar

1. Verificar logs do backend (`apps.chat.tasks`, `apps.chat.webhooks`)
2. Verificar logs da Evolution API
3. Comparar formato de payloads antes/depois
4. Verificar se endpoints mudaram na documentação

