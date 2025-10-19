-- Adicionar campo instance_name no modelo Conversation
ALTER TABLE chat_conversation
ADD COLUMN IF NOT EXISTS instance_name VARCHAR(255) DEFAULT '';

-- Criar índice para melhor performance
CREATE INDEX IF NOT EXISTS chat_conversation_instance_name_idx 
ON chat_conversation(instance_name);

