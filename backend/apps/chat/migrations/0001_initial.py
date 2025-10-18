# Generated migration for Flow Chat module
from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenancy', '0001_initial'),
        ('authn', '0003_add_departments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Tabela: Conversation
            CREATE TABLE IF NOT EXISTS chat_conversation (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                department_id UUID NOT NULL REFERENCES authn_department(id) ON DELETE CASCADE,
                contact_phone VARCHAR(20) NOT NULL,
                contact_name VARCHAR(255),
                assigned_to_id INTEGER REFERENCES authn_user(id) ON DELETE SET NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                last_message_at TIMESTAMP WITH TIME ZONE,
                unread_count INTEGER NOT NULL DEFAULT 0,
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_chat_conversation_tenant ON chat_conversation(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_chat_conversation_department ON chat_conversation(department_id);
            CREATE INDEX IF NOT EXISTS idx_chat_conversation_phone ON chat_conversation(contact_phone);
            CREATE INDEX IF NOT EXISTS idx_chat_conversation_status ON chat_conversation(status);
            CREATE INDEX IF NOT EXISTS idx_chat_conversation_last_msg ON chat_conversation(last_message_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conversation_unique ON chat_conversation(tenant_id, contact_phone);
            
            -- Tabela: Message
            CREATE TABLE IF NOT EXISTS chat_message (
                id UUID PRIMARY KEY,
                conversation_id UUID NOT NULL REFERENCES chat_conversation(id) ON DELETE CASCADE,
                sender_id INTEGER REFERENCES authn_user(id) ON DELETE SET NULL,
                content TEXT,
                direction VARCHAR(10) NOT NULL DEFAULT 'incoming',
                status VARCHAR(20) NOT NULL DEFAULT 'sent',
                is_internal BOOLEAN NOT NULL DEFAULT FALSE,
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_chat_message_conversation ON chat_message(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_chat_message_created ON chat_message(created_at);
            
            -- Tabela: MessageAttachment
            CREATE TABLE IF NOT EXISTS chat_messageattachment (
                id UUID PRIMARY KEY,
                message_id UUID NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                file_type VARCHAR(50) NOT NULL,
                file_path VARCHAR(500),
                file_url VARCHAR(500),
                original_filename VARCHAR(255),
                size_bytes BIGINT NOT NULL DEFAULT 0,
                storage_type VARCHAR(10) NOT NULL DEFAULT 'local',
                is_image BOOLEAN NOT NULL DEFAULT FALSE,
                is_video BOOLEAN NOT NULL DEFAULT FALSE,
                is_audio BOOLEAN NOT NULL DEFAULT FALSE,
                expires_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_chat_attachment_message ON chat_messageattachment(message_id);
            CREATE INDEX IF NOT EXISTS idx_chat_attachment_tenant ON chat_messageattachment(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_chat_attachment_expires ON chat_messageattachment(expires_at);
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS chat_messageattachment CASCADE;
            DROP TABLE IF EXISTS chat_message CASCADE;
            DROP TABLE IF EXISTS chat_conversation CASCADE;
            """
        )
    ]
