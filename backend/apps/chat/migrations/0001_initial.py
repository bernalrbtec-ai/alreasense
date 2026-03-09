# Generated migration for Flow Chat module
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenancy", "0001_initial"),
        ("authn", "0003_add_departments"),
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
        ),
        # Atualiza apenas o estado das migrations (tabelas já criadas acima) para que
        # outras migrations (ex.: 0017_flow_schema) possam referenciar chat.conversation.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Conversation",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("contact_phone", models.CharField(max_length=20)),
                        ("contact_name", models.CharField(blank=True, max_length=255, null=True)),
                        ("status", models.CharField(default="open", max_length=20)),
                        ("last_message_at", models.DateTimeField(blank=True, null=True)),
                        ("unread_count", models.IntegerField(default=0)),
                        ("metadata", models.JSONField(default=dict)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="authn.user")),
                        ("department", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to="authn.department")),
                        ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to="tenancy.tenant")),
                    ],
                    options={},
                ),
                migrations.CreateModel(
                    name="Message",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("content", models.TextField(blank=True, null=True)),
                        ("direction", models.CharField(default="incoming", max_length=10)),
                        ("status", models.CharField(default="sent", max_length=20)),
                        ("is_internal", models.BooleanField(default=False)),
                        ("metadata", models.JSONField(default=dict)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="chat.conversation")),
                        ("sender", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="authn.user")),
                    ],
                    options={},
                ),
                migrations.CreateModel(
                    name="MessageAttachment",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("file_type", models.CharField(max_length=50)),
                        ("file_path", models.CharField(blank=True, max_length=500, null=True)),
                        ("file_url", models.CharField(blank=True, max_length=500, null=True)),
                        ("original_filename", models.CharField(blank=True, max_length=255, null=True)),
                        ("size_bytes", models.BigIntegerField(default=0)),
                        ("storage_type", models.CharField(default="local", max_length=10)),
                        ("is_image", models.BooleanField(default=False)),
                        ("is_video", models.BooleanField(default=False)),
                        ("is_audio", models.BooleanField(default=False)),
                        ("expires_at", models.DateTimeField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="chat.message")),
                        ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="tenancy.tenant")),
                    ],
                    options={},
                ),
            ],
        ),
    ]
