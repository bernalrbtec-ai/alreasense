# Generated manually on 2025-10-18

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenancy', '0001_initial'),
        ('authn', '0003_add_departments'),
    ]

    operations = [
        migrations.RunSQL(
            # SQL para criar as tabelas
            sql="""
            -- Tabela de conversas
            CREATE TABLE IF NOT EXISTS chat_conversation (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                department_id UUID NOT NULL REFERENCES authn_department(id) ON DELETE CASCADE,
                contact_phone VARCHAR(20) NOT NULL,
                contact_name VARCHAR(255) DEFAULT '',
                assigned_to_id UUID REFERENCES authn_user(id) ON DELETE SET NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                last_message_at TIMESTAMP WITH TIME ZONE,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );

            -- Índices para conversation
            CREATE INDEX IF NOT EXISTS chat_conver_tenant__b8e5c6_idx ON chat_conversation(tenant_id, department_id, status);
            CREATE INDEX IF NOT EXISTS chat_conver_tenant__84c8ab_idx ON chat_conversation(tenant_id, contact_phone);
            CREATE INDEX IF NOT EXISTS chat_conver_assigne_c28e30_idx ON chat_conversation(assigned_to_id, status);
            CREATE INDEX IF NOT EXISTS chat_conver_last_msg_idx ON chat_conversation(last_message_at DESC);

            -- Tabela de mensagens
            CREATE TABLE IF NOT EXISTS chat_message (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES chat_conversation(id) ON DELETE CASCADE,
                sender_id UUID REFERENCES authn_user(id) ON DELETE SET NULL,
                content TEXT DEFAULT '',
                direction VARCHAR(10) NOT NULL,
                message_id VARCHAR(255) UNIQUE,
                evolution_status VARCHAR(50) DEFAULT '',
                error_message TEXT DEFAULT '',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                is_internal BOOLEAN NOT NULL DEFAULT FALSE,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );

            -- Índices para message
            CREATE INDEX IF NOT EXISTS chat_messag_convers_3eb4b5_idx ON chat_message(conversation_id, created_at);
            CREATE INDEX IF NOT EXISTS chat_messag_message_58cc5e_idx ON chat_message(message_id);
            CREATE INDEX IF NOT EXISTS chat_messag_status_e7aa0d_idx ON chat_message(status, direction);
            CREATE INDEX IF NOT EXISTS chat_messag_created_idx ON chat_message(created_at);

            -- Tabela de anexos
            CREATE TABLE IF NOT EXISTS chat_attachment (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                message_id UUID NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                original_filename VARCHAR(255) NOT NULL,
                mime_type VARCHAR(100) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_url VARCHAR(500) NOT NULL,
                thumbnail_path VARCHAR(500) DEFAULT '',
                storage_type VARCHAR(10) NOT NULL DEFAULT 'local',
                size_bytes BIGINT NOT NULL DEFAULT 0,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );

            -- Índices para attachment
            CREATE INDEX IF NOT EXISTS chat_messag_tenant__a41bf4_idx ON chat_attachment(tenant_id, storage_type);
            CREATE INDEX IF NOT EXISTS chat_messag_expires_e58dc8_idx ON chat_attachment(expires_at);

            -- Tabela many-to-many para participantes
            CREATE TABLE IF NOT EXISTS chat_conversation_participants (
                id SERIAL PRIMARY KEY,
                conversation_id UUID NOT NULL REFERENCES chat_conversation(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES authn_user(id) ON DELETE CASCADE,
                UNIQUE(conversation_id, user_id)
            );

            CREATE INDEX IF NOT EXISTS chat_conv_part_conv_idx ON chat_conversation_participants(conversation_id);
            CREATE INDEX IF NOT EXISTS chat_conv_part_user_idx ON chat_conversation_participants(user_id);
            """,
            # SQL reverso para desfazer
            reverse_sql="""
            DROP TABLE IF EXISTS chat_conversation_participants CASCADE;
            DROP TABLE IF EXISTS chat_attachment CASCADE;
            DROP TABLE IF EXISTS chat_message CASCADE;
            DROP TABLE IF EXISTS chat_conversation CASCADE;
            """
        ),
    ]
