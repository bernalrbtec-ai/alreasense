# Generated manually - Usando RunSQL porque tabelas anteriores foram criadas via RunSQL

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0006_add_metadata_to_messageattachment'),
        ('authn', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Tabela: MessageReaction
            CREATE TABLE IF NOT EXISTS chat_message_reaction (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                message_id UUID NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES authn_user(id) ON DELETE CASCADE,
                emoji VARCHAR(10) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            
            -- Índices
            CREATE INDEX IF NOT EXISTS idx_chat_message_reaction_message ON chat_message_reaction(message_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_chat_message_reaction_user ON chat_message_reaction(user_id, created_at);
            
            -- Constraint único: uma reação por usuário, mensagem e emoji
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_message_reaction_unique ON chat_message_reaction(message_id, user_id, emoji);
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS chat_message_reaction CASCADE;
            """
        ),
    ]

