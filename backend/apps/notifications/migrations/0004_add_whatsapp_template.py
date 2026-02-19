# Fase 6 - Templates e janela 24h: modelo WhatsAppTemplate (Meta Cloud API)
# Criar tabela notifications_whatsapp_template

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_add_default_department'),
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='WhatsAppTemplate',
                    fields=[
                        ('id', models.UUIDField(editable=False, primary_key=True, serialize=False)),
                        ('name', models.CharField(help_text='Nome amigável para identificar o template no sistema', max_length=255, verbose_name='Nome (exibição)')),
                        ('template_id', models.CharField(db_index=True, help_text='Nome do template aprovado no Meta Business (ex: hello_world)', max_length=100, verbose_name='ID do template na Meta')),
                        ('language_code', models.CharField(default='pt_BR', help_text='Código do idioma do template (ex: pt_BR, en_US)', max_length=10, verbose_name='Código do idioma')),
                        ('body_parameters_default', models.JSONField(blank=True, default=list, help_text='Lista de valores padrão para variáveis do body', verbose_name='Parâmetros padrão do body')),
                        ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Ativo')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('tenant', models.ForeignKey(on_delete=models.CASCADE, related_name='whatsapp_templates', to='tenancy.tenant', verbose_name='Tenant')),
                        ('wa_instance', models.ForeignKey(blank=True, help_text='Opcional. Se vazio, template disponível para qualquer instância Meta do tenant.', null=True, on_delete=models.CASCADE, related_name='templates', to='notifications.whatsappinstance', verbose_name='Instância WhatsApp')),
                    ],
                    options={
                        'db_table': 'notifications_whatsapp_template',
                        'ordering': ['name'],
                        'verbose_name': 'Template WhatsApp',
                        'verbose_name_plural': 'Templates WhatsApp',
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS notifications_whatsapp_template (
                            id UUID PRIMARY KEY,
                            tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                            wa_instance_id UUID NULL REFERENCES notifications_whatsapp_instance(id) ON DELETE CASCADE,
                            name VARCHAR(255) NOT NULL,
                            template_id VARCHAR(100) NOT NULL,
                            language_code VARCHAR(10) NOT NULL DEFAULT 'pt_BR',
                            body_parameters_default JSONB NOT NULL DEFAULT '[]',
                            is_active BOOLEAN NOT NULL DEFAULT TRUE,
                            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                            CONSTRAINT notifications_wa_template_tenant_id_lang_uniq
                                UNIQUE (tenant_id, template_id, language_code)
                        );
                        CREATE INDEX IF NOT EXISTS idx_whatsapp_template_tenant ON notifications_whatsapp_template(tenant_id);
                        CREATE INDEX IF NOT EXISTS idx_whatsapp_template_template_id ON notifications_whatsapp_template(template_id);
                        CREATE INDEX IF NOT EXISTS idx_whatsapp_template_is_active ON notifications_whatsapp_template(is_active);
                    """,
                    reverse_sql="""
                        DROP INDEX IF EXISTS idx_whatsapp_template_is_active;
                        DROP INDEX IF EXISTS idx_whatsapp_template_template_id;
                        DROP INDEX IF EXISTS idx_whatsapp_template_tenant;
                        DROP TABLE IF EXISTS notifications_whatsapp_template;
                    """,
                ),
            ],
        ),
    ]
