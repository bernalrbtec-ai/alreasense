# Generated manually - 2025-01-XX
# ✅ ADD: default_department field to WhatsAppInstance

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_add_performance_indexes'),
        ('authn', '0003_add_departments'),  # Department precisa existir
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Adicionar campo default_department_id se não existir
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'notifications_whatsapp_instance' 
                        AND column_name = 'default_department_id'
                    ) THEN
                        ALTER TABLE notifications_whatsapp_instance 
                        ADD COLUMN default_department_id UUID NULL 
                        REFERENCES authn_department(id) ON DELETE SET NULL;
                        
                        CREATE INDEX IF NOT EXISTS idx_whatsappinstance_default_dept 
                        ON notifications_whatsapp_instance(default_department_id);
                    END IF;
                END $$;
            """,
            reverse_sql="""
                -- Reverter: remover campo se existir
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'notifications_whatsapp_instance' 
                        AND column_name = 'default_department_id'
                    ) THEN
                        DROP INDEX IF EXISTS idx_whatsappinstance_default_dept;
                        ALTER TABLE notifications_whatsapp_instance 
                        DROP COLUMN default_department_id;
                    END IF;
                END $$;
            """
        ),
    ]

