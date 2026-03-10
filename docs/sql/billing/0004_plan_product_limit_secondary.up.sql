-- PlanProduct: limite secundário (ALREA Chat = instâncias + usuários)
-- Tabela: billing_plan_product
-- Equivalente à migration 0004_plan_product_limit_secondary (use este script em vez de migrations, se preferir)

ALTER TABLE billing_plan_product
  ADD COLUMN IF NOT EXISTS limit_value_secondary INTEGER NULL;

ALTER TABLE billing_plan_product
  ADD COLUMN IF NOT EXISTS limit_unit_secondary VARCHAR(50) NULL;

COMMENT ON COLUMN billing_plan_product.limit_value_secondary IS 'Limite secundário (ex: número de usuários)';
COMMENT ON COLUMN billing_plan_product.limit_unit_secondary IS 'Unidade do limite secundário (ex: usuários)';
