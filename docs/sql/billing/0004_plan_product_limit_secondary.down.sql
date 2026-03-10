-- Reversão: remove limite secundário de billing_plan_product

ALTER TABLE billing_plan_product
  DROP COLUMN IF EXISTS limit_value_secondary;

ALTER TABLE billing_plan_product
  DROP COLUMN IF EXISTS limit_unit_secondary;
