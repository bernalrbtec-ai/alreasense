# Scripts SQL – API oficial Meta (WhatsApp)

Execute no PostgreSQL na ordem abaixo. Use o mesmo banco do backend (ex.: conexão do Railway ou local).

---

## 1. Tabela `notifications_whatsapp_instance` (campos Meta)

**Só rode se as colunas ainda não existirem.** Para conferir:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'notifications_whatsapp_instance'
  AND column_name IN ('integration_type', 'phone_number_id', 'access_token');
```

Se retornar 3 linhas, **não execute** o bloco abaixo.

```sql
-- API oficial Meta: novos campos em notifications_whatsapp_instance
-- Idempotente (ADD COLUMN IF NOT EXISTS exige PostgreSQL 9.5+ para colunas; 15+ para IF NOT EXISTS em ADD COLUMN).

ALTER TABLE notifications_whatsapp_instance
  ADD COLUMN IF NOT EXISTS integration_type VARCHAR(20) NOT NULL DEFAULT 'evolution';

ALTER TABLE notifications_whatsapp_instance
  ADD COLUMN IF NOT EXISTS phone_number_id VARCHAR(50) NULL;

ALTER TABLE notifications_whatsapp_instance
  ADD COLUMN IF NOT EXISTS access_token VARCHAR(500) NULL;

ALTER TABLE notifications_whatsapp_instance
  ADD COLUMN IF NOT EXISTS business_account_id VARCHAR(100) NULL;

ALTER TABLE notifications_whatsapp_instance
  ADD COLUMN IF NOT EXISTS app_id VARCHAR(100) NULL;

ALTER TABLE notifications_whatsapp_instance
  ADD COLUMN IF NOT EXISTS access_token_expires_at TIMESTAMP WITH TIME ZONE NULL;

COMMENT ON COLUMN notifications_whatsapp_instance.integration_type IS 'evolution | meta_cloud';
COMMENT ON COLUMN notifications_whatsapp_instance.phone_number_id IS 'Meta Phone Number ID (webhook lookup)';
COMMENT ON COLUMN notifications_whatsapp_instance.access_token IS 'Meta access token (prefer encrypted at rest)';

CREATE INDEX IF NOT EXISTS idx_whatsapp_instance_integration_type
  ON notifications_whatsapp_instance(integration_type);

CREATE UNIQUE INDEX IF NOT EXISTS idx_whatsapp_instance_phone_number_id_meta
  ON notifications_whatsapp_instance(phone_number_id)
  WHERE integration_type = 'meta_cloud' AND phone_number_id IS NOT NULL;
```

---

## 2. Tabela `notifications_whatsapp_template` (Fase 6 – templates)

Só crie se a tabela ainda não existir. Para conferir:

```sql
SELECT 1 FROM information_schema.tables
WHERE table_schema = 'public' AND table_name = 'notifications_whatsapp_template';
```

Se retornar 1 linha, **não execute** o bloco abaixo.

```sql
-- Fase 6: Templates WhatsApp (Meta Cloud API)
CREATE TABLE IF NOT EXISTS notifications_whatsapp_template (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    wa_instance_id UUID NULL REFERENCES notifications_whatsapp_instance(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    template_id VARCHAR(100) NOT NULL,
    language_code VARCHAR(10) NOT NULL DEFAULT 'pt_BR',
    body_parameters_default JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT notifications_wa_template_tenant_id_lang_uniq
        UNIQUE (tenant_id, template_id, language_code)
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_template_tenant ON notifications_whatsapp_template(tenant_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_template_template_id ON notifications_whatsapp_template(template_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_template_is_active ON notifications_whatsapp_template(is_active);
```

**Reverter (apenas se precisar desfazer):**

```sql
DROP INDEX IF EXISTS idx_whatsapp_template_is_active;
DROP INDEX IF EXISTS idx_whatsapp_template_template_id;
DROP INDEX IF EXISTS idx_whatsapp_template_tenant;
DROP TABLE IF EXISTS notifications_whatsapp_template;
```

---

## Ordem recomendada

1. Conferir se as colunas do **script 1** já existem; se não, rodar o script 1.
2. Conferir se a tabela do **script 2** já existe; se não, rodar o script 2.

Se você aplicou o script 1 manualmente antes (como no staging), pule o script 1 e rode só o script 2 quando for usar templates (Fase 6).
