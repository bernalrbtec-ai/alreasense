-- Script SQL para adicionar campo profile_pic_url ao modelo Contact
-- Execute este script diretamente no banco de dados

-- Adicionar coluna profile_pic_url (se não existir)
ALTER TABLE contacts_contact
ADD COLUMN IF NOT EXISTS profile_pic_url VARCHAR(500) NULL;

-- Adicionar comentário na coluna
COMMENT ON COLUMN contacts_contact.profile_pic_url IS 
'URL da foto de perfil do WhatsApp. Atualizada automaticamente via webhook contacts.update quando há mudança.';

-- Criar índice para melhorar performance em buscas por foto (opcional, mas recomendado)
CREATE INDEX IF NOT EXISTS idx_contacts_contact_profile_pic_url 
ON contacts_contact(profile_pic_url) 
WHERE profile_pic_url IS NOT NULL;

-- Verificar se a coluna foi criada corretamente
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'contacts_contact' 
  AND column_name = 'profile_pic_url';

