# Generated manually to add external_sender support to MessageReaction
# ✅ CORREÇÃO: Usar RunSQL para ser idempotente (pode ser executado mesmo se SQL já foi rodado)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0011_messagereaction'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- ✅ CORREÇÃO: Tornar campo user nullable (idempotente)
            DO $$ 
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'chat_message_reaction' 
                    AND column_name = 'user_id' 
                    AND is_nullable = 'NO'
                ) THEN
                    ALTER TABLE chat_message_reaction ALTER COLUMN user_id DROP NOT NULL;
                END IF;
            END $$;

            -- ✅ CORREÇÃO: Adicionar campo external_sender (idempotente)
            ALTER TABLE chat_message_reaction 
                ADD COLUMN IF NOT EXISTS external_sender VARCHAR(50) NOT NULL DEFAULT '';

            -- Remover DEFAULT após adicionar
            DO $$ 
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'chat_message_reaction' 
                    AND column_name = 'external_sender' 
                    AND column_default IS NOT NULL
                ) THEN
                    ALTER TABLE chat_message_reaction ALTER COLUMN external_sender DROP DEFAULT;
                END IF;
            END $$;

            -- ✅ CORREÇÃO: Remover constraint unique antigo (idempotente)
            DROP INDEX IF EXISTS idx_chat_message_reaction_unique;

            -- ✅ CORREÇÃO: Adicionar índice para external_sender (idempotente)
            CREATE INDEX IF NOT EXISTS idx_chat_message_reaction_external_sender 
                ON chat_message_reaction(external_sender, created_at);

            -- ✅ CORREÇÃO: Adicionar constraint único para user (idempotente)
            DROP INDEX IF EXISTS unique_user_reaction_per_message_emoji;
            CREATE UNIQUE INDEX IF NOT EXISTS unique_user_reaction_per_message_emoji 
                ON chat_message_reaction(message_id, user_id, emoji) 
                WHERE user_id IS NOT NULL;

            -- ✅ CORREÇÃO: Adicionar constraint único para external_sender (idempotente)
            DROP INDEX IF EXISTS unique_external_reaction_per_message_emoji;
            CREATE UNIQUE INDEX IF NOT EXISTS unique_external_reaction_per_message_emoji 
                ON chat_message_reaction(message_id, external_sender, emoji) 
                WHERE external_sender != '';

            -- ✅ CORREÇÃO: Adicionar comentários (idempotente)
            COMMENT ON COLUMN chat_message_reaction.user_id IS 'NULL para reações de contatos externos (WhatsApp)';
            COMMENT ON COLUMN chat_message_reaction.external_sender IS 'Número do contato que reagiu (para reações recebidas do WhatsApp)';
            """,
            reverse_sql="""
            -- Reverter: remover campo external_sender
            ALTER TABLE chat_message_reaction DROP COLUMN IF EXISTS external_sender;
            
            -- Reverter: tornar user NOT NULL novamente
            ALTER TABLE chat_message_reaction ALTER COLUMN user_id SET NOT NULL;
            
            -- Reverter: remover índices novos
            DROP INDEX IF EXISTS idx_chat_message_reaction_external_sender;
            DROP INDEX IF EXISTS unique_user_reaction_per_message_emoji;
            DROP INDEX IF EXISTS unique_external_reaction_per_message_emoji;
            
            -- Reverter: recriar constraint antigo
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_message_reaction_unique 
                ON chat_message_reaction(message_id, user_id, emoji);
            """
        ),
    ]

