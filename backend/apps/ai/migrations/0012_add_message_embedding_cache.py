# Cache de embeddings de mensagens para otimização

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0011_add_inbox_idle_minutes'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS ai_message_embedding (
                id BIGSERIAL PRIMARY KEY,
                text_hash VARCHAR(64) NOT NULL UNIQUE,
                text TEXT NOT NULL,
                embedding JSONB NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                last_used_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE NULL
            );

            CREATE INDEX IF NOT EXISTS idx_message_embedding_text_hash ON ai_message_embedding(text_hash);
            CREATE INDEX IF NOT EXISTS idx_message_embedding_created_at ON ai_message_embedding(created_at);
            CREATE INDEX IF NOT EXISTS idx_message_embedding_expires_at ON ai_message_embedding(expires_at);
            CREATE INDEX IF NOT EXISTS idx_message_embedding_last_used_at ON ai_message_embedding(last_used_at);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_message_embedding_last_used_at;
            DROP INDEX IF EXISTS idx_message_embedding_expires_at;
            DROP INDEX IF EXISTS idx_message_embedding_created_at;
            DROP INDEX IF EXISTS idx_message_embedding_text_hash;
            DROP TABLE IF EXISTS ai_message_embedding;
            """,
        ),
    ]
