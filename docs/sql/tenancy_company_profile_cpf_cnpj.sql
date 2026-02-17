-- Suporte a CPF/CNPJ e busca BrasilAPI
-- Executar no Postgres. Tabela tenancy_company_profile já deve existir.

-- Novo modelo: documento (CPF ou CNPJ) + tipo_pessoa + nome_fantasia
ALTER TABLE tenancy_company_profile ADD COLUMN IF NOT EXISTS tipo_pessoa VARCHAR(2) DEFAULT 'PJ';
ALTER TABLE tenancy_company_profile ADD COLUMN IF NOT EXISTS documento VARCHAR(18);
ALTER TABLE tenancy_company_profile ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(200);

-- Migrar CNPJ existente para documento (para registros que já têm cnpj)
UPDATE tenancy_company_profile
SET documento = REPLACE(REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '/', ''), '-', ''), ' ', ''),
    tipo_pessoa = 'PJ'
WHERE cnpj IS NOT NULL AND cnpj != '' AND (documento IS NULL OR documento = '');
