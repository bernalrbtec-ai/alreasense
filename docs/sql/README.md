# Scripts SQL das migrations (Sense)

Estrutura dos scripts SQL equivalentes às migrations do Django, para **auditoria e provisionamento manual** de banco. O projeto não utiliza cancelamento de migrations em produção; o escopo de fluxos segue apenas o [Plano de canvas de fluxos](../PLANO_CANVAS_FLUXO.md).

## Organização

- **Raiz:** `docs/sql/`
- **Por app:** subpasta com o nome do app (ex.: `tenancy`, `chat`, `billing`).
- **Arquivos:** `<numero>_<nome_migration>.up.sql` (aplicar) e, quando existir reversão, `<numero>_<nome_migration>.down.sql` (desfazer).

Ordem de aplicação deve respeitar as dependências entre apps (ver [MIGRATIONS_SQL_MAPEAMENTO.md](../MIGRATIONS_SQL_MAPEAMENTO.md)).

## Scripts já gerados (RunSQL a partir de arquivo)

| App     | Migration              | Up | Down |
|---------|------------------------|----|------|
| tenancy | 0001_initial           | [tenancy/0001_initial.up.sql](tenancy/0001_initial.up.sql) | — (noop) |
| chat    | 0017_flow_schema       | [chat/0017_flow_schema.up.sql](chat/0017_flow_schema.up.sql) | [chat/0017_flow_schema.down.sql](chat/0017_flow_schema.down.sql) |
| chat    | 0018_flow_node_media_url (canvas) | [chat/0018_flow_node_media_url.up.sql](chat/0018_flow_node_media_url.up.sql) | — (opcional: remover coluna manualmente) |
| billing | 0003_billing_api_initial | [billing/0003_billing_api_initial.up.sql](billing/0003_billing_api_initial.up.sql) | — (noop) |
| billing | 0004_plan_product_limit_secondary | [billing/0004_plan_product_limit_secondary.up.sql](billing/0004_plan_product_limit_secondary.up.sql) | [billing/0004_plan_product_limit_secondary.down.sql](billing/0004_plan_product_limit_secondary.down.sql) |

## Como gerar o SQL das demais migrations

Para migrations que usam `CreateModel`, `AddField`, `AlterField`, etc.:

```bash
cd backend
python manage.py sqlmigrate <app_label> <migration_name>
```

Exemplo: `python manage.py sqlmigrate authn 0001_initial`. Salve a saída em `docs/sql/<app>/<migration_name>.sql` ou `<migration_name>.up.sql`.

Para migrations com **RunSQL** inline (SQL dentro do `.py`), extraia o conteúdo do argumento `sql` (e `reverse_sql` se houver) do arquivo de migration e salve em `.up.sql` e `.down.sql` aqui.

## Uso

- **Novo ambiente (banco vazio):** rodar os `.up.sql` na ordem das dependências (billing 0001 → tenancy 0001 → authn → chat → …). Depois, marcar as migrations como aplicadas: `python manage.py migrate --fake`.
- **Rollback:** só rodar `.down.sql` quando existir e quando for seguro (ver [CANCELAMENTO_MIGRATIONS_PRODUCAO.md](../CANCELAMENTO_MIGRATIONS_PRODUCAO.md)).
