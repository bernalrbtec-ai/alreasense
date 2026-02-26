-- Adiciona campos para importação assíncrona CSV + VCF (ContactImport)
-- Tabela: contacts_import
-- Execute manualmente se não usar Django migrate.

-- import_type: 'csv' ou 'vcf'
ALTER TABLE contacts_import
ADD COLUMN IF NOT EXISTS import_type VARCHAR(10) NOT NULL DEFAULT 'csv';

-- import_options: JSON para column_mapping/delimiter (CSV) ou {} (VCF)
ALTER TABLE contacts_import
ADD COLUMN IF NOT EXISTS import_options JSONB NOT NULL DEFAULT '{}';

-- Comentários (opcional)
COMMENT ON COLUMN contacts_import.import_type IS 'Tipo do arquivo importado: csv ou vcf';
COMMENT ON COLUMN contacts_import.import_options IS 'Opções: para CSV {column_mapping, delimiter}; para VCF {}';
