# Cancelamento de migrations em produção (Sense)

**Fora de uso.** Este documento não é utilizado no projeto. O escopo de fluxos utiliza apenas o [Plano de canvas de fluxos](PLANO_CANVAS_FLUXO.md). O texto abaixo permanece como referência histórica.

---

Estratégia para reverter ou “cancelar” migrations em produção com segurança. **Cancelar** pode significar (1) desfazer de fato o esquema no banco ou (2) apenas ajustar o estado do Django (metadados) sem rodar SQL.

---

## 1. Duas formas de “cancelar”

### A. Rollback real (unapply)

- **O quê:** Executar o SQL de reversão (ou o que o Django gera ao voltar uma migration) e voltar o banco a um estado anterior.
- **Como:** `python manage.py migrate <app> <migration_anterior>` (ex.: `migrate chat 0016` para desfazer a 0017). O Django executa `reverse_sql` / operações reversas.
- **Risco:** Alto em produção. Pode apagar tabelas/colunas e dados. Só use com backup e em janela de manutenção.

### B. Apenas ajustar estado (--fake)

- **O quê:** Dizer ao Django que uma migration “não está aplicada” (ou que “está aplicada”) **sem rodar SQL**.
- **Como:** `python manage.py migrate <app> <migration_alvo> --fake`.
- **Uso típico:** O banco já foi alterado manualmente (ex.: rodou os scripts em [docs/sql/](sql/)) e você quer alinhar a tabela `django_migrations` ao estado real. Ou você quer “desmarcar” uma migration no Django mas **manter o banco como está**.
- **Risco:** Baixo, desde que o banco e o estado fake estejam consistentes. Não remove dados.

Em produção, prefira **B** sempre que o objetivo for só alinhar estado ou “cancelar” no Django sem mudar o banco.

---

## 2. Estratégia em produção (passo a passo)

### Passo 1 – Backup

- Fazer **backup completo** do banco (dump + snapshot, se possível) antes de qualquer reversão ou alteração de migrations.
- Garantir que há plano para restaurar esse backup em caso de falha.

### Passo 2 – Analisar impacto por app

Para cada app cuja migration você quer cancelar, verificar:

- Se a migration cria tabelas/colunas que **já têm dados em produção** (rollback real = perda de dados).
- Se outras migrations (no mesmo app ou em outros) **dependem** dela (grafo em [MIGRATIONS_SQL_MAPEAMENTO.md](MIGRATIONS_SQL_MAPEAMENTO.md)).
- Se a migration usa **RunSQL sem reverse_sql** (ex.: noop) → rollback real não desfaz o DDL; o banco fica como está.

### Passo 3 – Definir alvo de rollback

- Decidir **até qual migration** cada app pode voltar sem quebrar a aplicação.
- Exemplo: em `chat`, voltar para `0016` remove as tabelas de fluxo (0017); só faça rollback real se não houver uso em produção ou se for janela combinada.

### Passo 4 – Escolher abordagem

**Se for rollback real:**

1. Testar em **staging** com cópia recente do banco de produção.
2. Em produção, em **janela de manutenção**:
   - Rodar o SQL de reversão manualmente (scripts `.down.sql` em [docs/sql/](sql/)) **ou** `migrate <app> <target>`.
   - Confirmar que o esquema e a aplicação ficaram consistentes.
3. Ter plano de “rollback do rollback”: em caso de problema, restaurar o backup e refazer o estado das migrations (incl. `--fake` se necessário).

**Se for só ajustar estado (--fake):**

1. Garantir que o banco está no estado desejado (ex.: já aplicou os scripts `.up.sql` manualmente, ou não quer desfazer nada).
2. Rodar `migrate <app> <target> --fake` para que a tabela `django_migrations` reflita esse estado.
3. Não é necessário rollback de dados; apenas metadados do Django mudam.

---

## 3. Recomendações práticas

- **Nunca** fazer rollback destrutivo em produção sem:
  - Backup completo.
  - Teste prévio em staging com dump de produção.
  - Janela de manutenção definida.
  - Plano para restaurar backup se algo der errado.
- Se o objetivo for só **documentar** ou ter scripts SQL para auditoria/provisionamento: **não reverter** em produção; usar `--fake` apenas quando for preciso alinhar estado.
- Migrations que têm **apenas state_operations** (ex.: authn 0003 e chat 0001 com SeparateDatabaseAndState): “cancelá-las” com `--fake` não altera o banco; só o registro em `django_migrations`. O DDL já foi aplicado por RunPython/RunSQL em outra operação.

---

## 4. Exemplo: “cancelar” a migration 0017 (chat) em produção

**Cenário:** Desfazer a criação das tabelas de fluxo (chat_flow, chat_flow_node, chat_flow_edge, chat_conversation_flow_state).

**Opção 1 – Rollback real (só se não houver dados importantes nessas tabelas):**

1. Backup do banco.
2. Rodar o script de reversão: [docs/sql/chat/0017_flow_schema.down.sql](sql/chat/0017_flow_schema.down.sql).
3. Marcar a 0017 como não aplicada: `python manage.py migrate chat 0016 --fake` (para alinhar estado ao banco).

**Opção 2 – Só desmarcar no Django (banco continua com as tabelas):**

1. `python manage.py migrate chat 0016 --fake`.
2. O Django passa a considerar que a 0017 não está aplicada; o banco não é alterado. Útil para “esconder” a feature de fluxo no Django sem dropar tabelas.

---

## 5. Referência rápida

| Objetivo | Ação |
|----------|------|
| Desfazer DDL no banco | Rodar `.down.sql` (quando existir) ou `migrate <app> <target>`; depois `--fake` se necessário para alinhar. |
| Só alinhar Django ao banco | `migrate <app> <target> --fake`. |
| Provisionar banco manualmente e marcar como migrado | Rodar os `.up.sql` na ordem; depois `migrate --fake-initial` ou `migrate --fake` por app. |

Scripts SQL disponíveis: [docs/sql/README.md](sql/README.md). Mapeamento completo das migrations: [MIGRATIONS_SQL_MAPEAMENTO.md](MIGRATIONS_SQL_MAPEAMENTO.md).

---

## 6. Particularidades do projeto Sense

- **authn 0003_add_departments:** O DDL (authn_department, authn_user_departments) é aplicado por **RunPython**; o **SeparateDatabaseAndState** só adiciona o modelo Department ao estado. “Cancelar” essa migration com `--fake` não altera o banco; apenas o registro em `django_migrations`. Não existe reverse_sql/reverse_code que desfaça o RunPython (reversão é noop).
- **chat 0001_initial:** O DDL (chat_conversation, chat_message, chat_messageattachment) é aplicado por **RunSQL** inline na migration; o **SeparateDatabaseAndState** só atualiza o estado. O SQL real está no próprio `.py`. Reversão da migration é noop; não há script `.down.sql` para 0001.
- **chat 0017_flow_schema:** Única migration de fluxo com **reverse_sql** explícito (DROP TABLE). Scripts em [docs/sql/chat/0017_flow_schema.up.sql](sql/chat/0017_flow_schema.up.sql) e [0017_flow_schema.down.sql](sql/chat/0017_flow_schema.down.sql). Em produção, rodar o `.down.sql` remove as quatro tabelas de fluxo; use só com backup e se não houver dados a preservar.
- **tenancy 0001, billing 0003:** RunSQL lê de arquivo; reversão é noop. Não há script de rollback para essas migrations; “cancelar” no Django com `--fake` não desfaz o esquema.
