# Maturidade e implantação: migrations + flow engine

## Escopo do que está pronto para implantar

| Componente | Alteração | Impacto |
|------------|-----------|---------|
| **authn 0003** | State: `CreateModel(Department)` via SeparateDatabaseAndState | Apenas estado do Django; banco já era criado pelo RunPython. |
| **chat 0001** | State: `CreateModel(Conversation, Message, MessageAttachment)` via SeparateDatabaseAndState | Apenas estado do Django; tabelas já eram criadas pelo RunSQL. |
| **flow_engine.py** | `process_flow_reply`: atomic + lock na mensagem, guards, log para departamento inexistente | Comportamento das transições mantido; menos race e mais robustez. |

**Não alterado:** 0017_flow_schema (continua igual). Banco que já rodou `flow_schema_complete.sql` não é alterado pelas migrations; o `migrate` só passa a conseguir **aplicar** 0017 sem ValueError.

---

## O que foi verificado

- **Migrations:** Ordem de dependências (authn 0003 → chat 0001 → chat 0017) e referências `authn.department`, `chat.conversation` conferidas. `migrate --plan` executado com sucesso (exit 0).
- **Flow engine:** Lógica de próximo nó, transferir e encerrar revisada; lock com `select_for_update`; idempotência com `flow_reply_processed`; tratamento de exceção; guards para `conversation`/`message`/`message.pk`; aviso quando departamento da aresta não existe.
- **Linter:** Sem erros nos arquivos alterados.
- **Reversão:** Migrations não alteram esquema em ambientes que já tinham as tabelas; flow_engine só adiciona comportamento defensivo (não remove caminhos existentes).

---

## Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|-------|----------------|-----------|
| `migrate` em banco novo falhar por ordem de apps | Baixa | Dependências 0003 → 0001 → 0017 e state_operations conferidos. |
| Processamento duplicado da mesma resposta (lista/botão) | Baixa | Lock na mensagem + `flow_reply_processed`; um worker por mensagem. |
| Aresta para departamento removido | Baixa | Log de warning; estado do fluxo removido; conversa não fica presa. |
| Falha de `state.save()` após envio do nó | Muito baixa | Rollback do atomic; retry pode reenviar uma vez; estado permanece consistente. |

Nenhum risco alto identificado para o escopo atual (migrations + flow engine).

---

## Checklist pré-implantação

- [ ] Backup do banco antes de rodar `migrate` (recomendado em produção).
- [ ] Em ambiente com banco já existente: tabelas `authn_department`, `chat_conversation`, `chat_flow`, etc. já existem; `migrate` só marcará 0017 como aplicada (e não reexecutará o RunSQL destrutivo).
- [ ] Dependências do projeto instaladas (incl. reportlab se usar campaigns); `python manage.py check` sem erros.
- [ ] Rodar `python manage.py migrate` (ou `migrate --plan` primeiro) e confirmar que termina sem ValueError.
- [ ] Após deploy: testar um fluxo (lista ou botões) de ponta a ponta: início, escolher opção, próximo nó e, se aplicável, transferir/encerrar.

---

## Maturidade e recomendação

### Maturidade: **alta para o escopo atual**

- **Migrations:** Ajuste apenas de **estado** (state_operations). Nenhuma mudança de DDL em bancos que já tenham as tabelas; em banco novo, o comportamento é o mesmo de antes, com o estado correto para 0017.
- **Flow engine:** Lógica já existente preservada; melhorias são defensivas (lock, idempotência, guards, log). Compatível com uso atual do fluxo (lista/botões, transferir, encerrar).

### Podemos implantar sem problemas?

**Sim**, para o que foi alterado (migrations + flow_engine), desde que:

1. O ambiente tenha as dependências instaladas e `manage.py check` passe (ou seja usado `--skip-checks` apenas se já for prática do ambiente).
2. Em produção, faça backup do banco antes do `migrate`.
3. Após o deploy, rode um teste rápido de fluxo (início → opção → próximo nó ou transferir/encerrar) para validar em runtime.

**Fora deste escopo:** O **plano** de canvas + edição sem JSON e editar/excluir fluxo é documentação para implementação futura; a implantação atual não inclui mudanças de frontend. Ou seja: pode implantar as alterações de backend/migrations com segurança; o frontend do fluxo segue como está até a implementação do plano.

---

## Resumo em uma frase

**As alterações em migrations (authn 0003, chat 0001) e no flow_engine estão maduras para implantação; o risco é baixo e as verificações e mitigações estão documentadas. Pode implantar seguindo o checklist acima.**
