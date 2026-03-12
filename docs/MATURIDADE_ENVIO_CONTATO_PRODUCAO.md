# Maturidade: Envio de contato (vCard) para produção

Análise da feature **Compartilhar contato** (envio de vCard pelo chat) para decisão de deploy em produção.

---

## 1. Resumo executivo

| Aspecto              | Status   | Nota |
|---------------------|----------|------|
| Segurança / tenant  | ✅ OK    | Mesmo modelo de acesso que outras mensagens |
| Validação / edge cases | ✅ OK | Helper centralizado, sanitização, rejeições explícitas |
| Observabilidade     | ⚠️ Parcial | Logs e métricas no fluxo geral; sem métrica específica de contato |
| Testes automatizados| ❌ Ausente | Nenhum teste unitário/integração para contact_message |
| Documentação        | ⚠️ Parcial | Plano e este doc; sem doc de API pública |
| UX / compatibilidade| ✅ OK    | SharedContactCard e MessageList já tratam exibição |

**Recomendação:** **Pode ir para produção** com baixo risco, desde que se aceite não ter testes automatizados no primeiro deploy. Recomenda-se adicionar testes e (opcional) métrica específica em seguida.

---

## 2. Segurança e isolamento

- **WebSocket (consumer):** Acesso à conversa via `check_conversation_access` (tenant + departamento). Criação de mensagem usa `Conversation.objects.get(id=..., tenant_id=self.user.tenant_id)`.
- **REST (MessageCreateSerializer):** `validate` exige que a conversa pertença ao tenant do usuário e respeita atribuição/departamento; `create` usa a mesma conversa validada.
- **Task:** A mensagem já está persistida e vinculada à conversa; o sender vem da instância da conversa (tenant-scoped). Não há caminho para enviar contato para conversa de outro tenant.
- **Dados do contato:** Nome e telefone sanitizados/truncados no helper; sem execução de conteúdo arbitrário. Telefone validado com `normalize_phone`.

**Conclusão:** Alinhado ao restante do chat; adequado para produção do ponto de vista de segurança e tenant.

---

## 3. Validação e casos de borda

- **Helper único** `extract_contacts_list` + `normalize_contact_for_provider`: uma única definição do que é “contact_message” e do formato normalizado (task, consumer e serializer usam o mesmo helper onde aplicável).
- **Rejeições explícitas:** Lista vazia, nenhum contato válido após normalizar, conflito com template/botões/lista/anexos, provider sem `send_contact` — todos tratados com mensagem de erro e, quando aplicável, log (ex.: warning quando “nenhum contato válido” na task).
- **Resposta da API:** Evolution e Meta tratam resposta 200 com corpo não-JSON como falha (`INVALID_RESPONSE`).
- **Frontend:** conversationId obrigatório, lista não vazia, telefone manual com ≥10 dígitos, modal fecha ao trocar de conversa, `aria-busy` no envio.

**Conclusão:** Casos de borda cobertos; adequado para produção.

---

## 4. Observabilidade

- **Logs:** Sucesso (“Contato enviado”), falha (erro do provider, “Nenhum contato válido”), e warning quando há `contact_message` mas nenhum contato válido (com `message_id`).
- **Métricas:** O envio de contato roda dentro de `handle_send_message`; `record_latency('send_message_total', ...)` e `record_error('send_message', ...)` cobrem o fluxo inteiro. Não há tag ou métrica específica “send_contact” (ex.: contador ou latência só de contato).
- **Rastreio:** Não há trace/span específico para “contact”; depende do que já existir para a mensagem.

**Sugestão pós-deploy:** Adicionar contador ou latência com tag `message_type=contact` se quiser analisar uso e performance só de contatos.

---

## 5. Testes automatizados

- **Situação atual:** Nenhum teste em `*test*` cobre `contact_message`, `send_contact`, `normalize_contact_for_provider` ou `extract_contacts_list`.
- **Referência:** Features como lista interativa (Meta) têm testes em `test_interactive_list.py` (validações de provider, parsing, etc.).

**Recomendação:** Para maior confiança em mudanças futuras:

1. Testes unitários para `extract_contacts_list` e `normalize_contact_for_provider` (formatos de entrada, telefone inválido, nome vazio, sanitização).
2. Testes de provider (Evolution/Meta) para `send_contact`: lista vazia, phone vazio, rejeição da API, resposta 200 com corpo inválido (mock de `requests`).
3. (Opcional) Teste de integração: consumer recebe payload com `contact_message` e mensagem é criada com metadata correta.

Não é bloqueante para o primeiro deploy, mas reduz risco em refators e novas integrações.

---

## 6. Documentação e contrato

- **Interno:** Plano em `.cursor/plans/enviar_contato_whatsapp_eca5c459.plan.md` e este documento.
- **API REST:** O campo `metadata.contact_message` não está documentado em nenhum “API docs” público (OpenAPI/Swagger) com formato e exemplos.
- **WebSocket:** Formato do payload `contact_message` (lista vs `{ contacts: [...] }`) está implícito no código e no plano.

**Sugestão:** Adicionar em documentação de API (se existir): exemplo de `POST /api/chat/messages/` com `metadata: { contact_message: { contacts: [{ display_name, phone }] } }` e nota de que não pode ser combinado com template/botões/lista/anexos.

---

## 7. Compatibilidade e exibição

- **Envio:** Evolution e Meta: apenas o primeiro contato é enviado (v1); quoted/context suportados.
- **Recepção (webhook):** `webhooks.py` já trata contato recebido (Evolution), preenche `metadata.contact_message` e `content` no formato esperado.
- **Frontend:** `MessageList` e `SharedContactCard` tratam `metadata.contact_message` (um contato como objeto, vários em `contacts[]`); fallback a partir do texto quando metadata incompleto.

**Conclusão:** Fluxo de ida e volta e exibição consistentes; adequado para produção.

---

## 8. Checklist pré-produção

- [x] Validação e sanitização de entrada (backend e frontend)
- [x] Isolamento por tenant em WS, REST e task
- [x] Tratamento de erro e mensagens de falha para o usuário
- [x] Log de falhas e caso “nenhum contato válido”
- [x] Resposta inesperada da API (não-JSON) tratada como falha
- [x] Conflito com template/botões/lista/anexos rejeitado
- [ ] Testes automatizados para helper e providers (recomendado pós-deploy)
- [ ] Métrica/tag específica para envio de contato (opcional)
- [ ] Documentação de API com exemplo de `contact_message` (se houver API docs)

---

## 9. Conclusão

A feature está **pronta para produção** do ponto de vista de segurança, validação, edge cases e integração com o resto do chat. Os principais gaps são a **ausência de testes automatizados** e a **falta de documentação explícita da API** para `contact_message`. Recomenda-se:

1. **Liberar em produção** com monitoramento normal do chat (logs, métricas de send_message, erros).
2. **Em seguida:** adicionar testes para o helper e para `send_contact` nos providers.
3. **Opcional:** métrica “send_contact” e pequena seção em docs de API para `metadata.contact_message`.
