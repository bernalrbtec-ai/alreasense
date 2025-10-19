-- Adicionar campo profile_pic_url na tabela chat_conversation

ALTER TABLE chat_conversation 
ADD COLUMN IF NOT EXISTS profile_pic_url VARCHAR(500) NULL;

-- Verificar
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'chat_conversation' 
AND column_name = 'profile_pic_url';

-- ✅ Pronto! Campo adicionado.

