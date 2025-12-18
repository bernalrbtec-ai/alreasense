-- Migration: Adiciona campos faltantes em BillingConfig
-- Data: 2025-01-XX

-- Adiciona campos em billing_api_config
ALTER TABLE billing_api_config
ADD COLUMN IF NOT EXISTS api_rate_limit_per_hour INTEGER DEFAULT 100,
ADD COLUMN IF NOT EXISTS api_enabled BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS max_retry_attempts INTEGER DEFAULT 3,
ADD COLUMN IF NOT EXISTS retry_delay_minutes INTEGER DEFAULT 5,
ADD COLUMN IF NOT EXISTS max_batch_size INTEGER DEFAULT 1000,
ADD COLUMN IF NOT EXISTS notify_on_instance_down BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS notify_on_resume BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS close_conversation_after_send BOOLEAN DEFAULT TRUE;

-- Adiciona constraints
ALTER TABLE billing_api_config
ADD CONSTRAINT billing_api_config_max_retry_attempts_check 
    CHECK (max_retry_attempts >= 0 AND max_retry_attempts <= 10);

ALTER TABLE billing_api_config
ADD CONSTRAINT billing_api_config_retry_delay_minutes_check 
    CHECK (retry_delay_minutes >= 1);

ALTER TABLE billing_api_config
ADD CONSTRAINT billing_api_config_max_batch_size_check 
    CHECK (max_batch_size >= 1 AND max_batch_size <= 10000);

-- Comentários
COMMENT ON COLUMN billing_api_config.api_rate_limit_per_hour IS 'Máximo de requisições API por hora (0 = ilimitado)';
COMMENT ON COLUMN billing_api_config.api_enabled IS 'API de Billing habilitada para este tenant';
COMMENT ON COLUMN billing_api_config.max_retry_attempts IS 'Máximo de tentativas de retry';
COMMENT ON COLUMN billing_api_config.retry_delay_minutes IS 'Delay entre tentativas (em minutos)';
COMMENT ON COLUMN billing_api_config.max_batch_size IS 'Máximo de contatos por campanha';
COMMENT ON COLUMN billing_api_config.notify_on_instance_down IS 'Notificar quando instância cair';
COMMENT ON COLUMN billing_api_config.notify_on_resume IS 'Notificar quando instância voltar';
COMMENT ON COLUMN billing_api_config.close_conversation_after_send IS 'Fechar conversa automaticamente após envio';

