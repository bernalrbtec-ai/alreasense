# Generated migration for adding deleted message fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0013_business_hours'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Adicionar coluna is_deleted (BOOLEAN com default FALSE)
            ALTER TABLE chat_message 
            ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

            -- Criar índice para is_deleted (para queries rápidas de mensagens apagadas)
            CREATE INDEX IF NOT EXISTS chat_message_is_deleted_idx ON chat_message(is_deleted);

            -- Adicionar coluna deleted_at (TIMESTAMP nullable)
            ALTER TABLE chat_message 
            ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE NULL;

            -- Adicionar comentários nas colunas (opcional, mas útil para documentação)
            COMMENT ON COLUMN chat_message.is_deleted IS 'True se mensagem foi apagada no WhatsApp';
            COMMENT ON COLUMN chat_message.deleted_at IS 'Timestamp quando mensagem foi apagada';
            """,
            reverse_sql="""
            -- Remover índice
            DROP INDEX IF EXISTS chat_message_is_deleted_idx;
            
            -- Remover colunas
            ALTER TABLE chat_message DROP COLUMN IF EXISTS deleted_at;
            ALTER TABLE chat_message DROP COLUMN IF EXISTS is_deleted;
            """
        )
    ]

