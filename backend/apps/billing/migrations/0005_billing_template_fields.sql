-- Migration: Adiciona campos faltantes em BillingTemplate e BillingTemplateVariation
-- Data: 2025-01-XX

-- Adiciona campos em billing_api_template
ALTER TABLE billing_api_template
ADD COLUMN IF NOT EXISTS total_uses INTEGER DEFAULT 0;

-- Adiciona campos em billing_api_template_variation
ALTER TABLE billing_api_template_variation
ADD COLUMN IF NOT EXISTS name VARCHAR(100) DEFAULT 'Variação',
ADD COLUMN IF NOT EXISTS times_used INTEGER DEFAULT 0;

-- Atualiza variações existentes sem nome
-- Nota: "order" é palavra reservada, precisa estar entre aspas duplas
UPDATE billing_api_template_variation
SET name = 'Variação ' || "order"::text
WHERE name IS NULL OR name = 'Variação';

-- Comentários
COMMENT ON COLUMN billing_api_template.total_uses IS 'Total de vezes que este template foi usado';
COMMENT ON COLUMN billing_api_template_variation.name IS 'Nome da variação (ex: "Variação 1")';
COMMENT ON COLUMN billing_api_template_variation.times_used IS 'Quantas vezes esta variação foi usada';

