-- Adiciona campo reply_to_groups na tabela chat_after_hours_message
-- Este campo controla se mensagens automáticas devem ser enviadas para grupos

ALTER TABLE chat_after_hours_message
ADD COLUMN IF NOT EXISTS reply_to_groups BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN chat_after_hours_message.reply_to_groups IS 
'Se habilitado, envia mensagem automática também para grupos. Se desabilitado, apenas para conversas individuais.';

