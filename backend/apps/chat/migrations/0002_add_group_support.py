# Generated manually by Paulo Bernal
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Adicionar campos para suporte a grupos
            ALTER TABLE chat_conversation 
            ADD COLUMN IF NOT EXISTS conversation_type VARCHAR(20) NOT NULL DEFAULT 'individual',
            ADD COLUMN IF NOT EXISTS group_metadata JSONB NOT NULL DEFAULT '{}';
            
            CREATE INDEX IF NOT EXISTS idx_chat_conversation_type ON chat_conversation(conversation_type);
            
            -- Adicionar campos para remetente em grupos
            ALTER TABLE chat_message
            ADD COLUMN IF NOT EXISTS sender_name VARCHAR(255) DEFAULT '',
            ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(20) DEFAULT '';
            """,
            reverse_sql="""
            ALTER TABLE chat_conversation 
            DROP COLUMN IF EXISTS conversation_type,
            DROP COLUMN IF EXISTS group_metadata;
            
            DROP INDEX IF EXISTS idx_chat_conversation_type;
            
            ALTER TABLE chat_message
            DROP COLUMN IF EXISTS sender_name,
            DROP COLUMN IF EXISTS sender_phone;
            """
        )
    ]
