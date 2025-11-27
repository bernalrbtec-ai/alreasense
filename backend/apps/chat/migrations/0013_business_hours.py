"""
Migration para horários de atendimento e mensagens automáticas fora de horário.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0012_add_external_sender_to_reactions'),
        ('tenancy', '0001_initial'),
        ('authn', '0003_add_departments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Tabela: BusinessHours (Horários de Atendimento)
            CREATE TABLE IF NOT EXISTS chat_business_hours (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                department_id UUID REFERENCES authn_department(id) ON DELETE CASCADE,
                timezone VARCHAR(50) NOT NULL DEFAULT 'America/Sao_Paulo',
                
                -- Segunda-feira
                monday_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                monday_start TIME NOT NULL DEFAULT '09:00:00',
                monday_end TIME NOT NULL DEFAULT '18:00:00',
                
                -- Terça-feira
                tuesday_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                tuesday_start TIME NOT NULL DEFAULT '09:00:00',
                tuesday_end TIME NOT NULL DEFAULT '18:00:00',
                
                -- Quarta-feira
                wednesday_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                wednesday_start TIME NOT NULL DEFAULT '09:00:00',
                wednesday_end TIME NOT NULL DEFAULT '18:00:00',
                
                -- Quinta-feira
                thursday_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                thursday_start TIME NOT NULL DEFAULT '09:00:00',
                thursday_end TIME NOT NULL DEFAULT '18:00:00',
                
                -- Sexta-feira
                friday_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                friday_start TIME NOT NULL DEFAULT '09:00:00',
                friday_end TIME NOT NULL DEFAULT '18:00:00',
                
                -- Sábado
                saturday_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                saturday_start TIME NOT NULL DEFAULT '09:00:00',
                saturday_end TIME NOT NULL DEFAULT '18:00:00',
                
                -- Domingo
                sunday_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                sunday_start TIME NOT NULL DEFAULT '09:00:00',
                sunday_end TIME NOT NULL DEFAULT '18:00:00',
                
                holidays JSONB NOT NULL DEFAULT '[]',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_business_hours_unique 
                ON chat_business_hours(tenant_id, department_id) 
                WHERE department_id IS NOT NULL;
            
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_business_hours_tenant_unique 
                ON chat_business_hours(tenant_id) 
                WHERE department_id IS NULL;
            
            CREATE INDEX IF NOT EXISTS idx_chat_business_hours_tenant_active 
                ON chat_business_hours(tenant_id, is_active);
            
            CREATE INDEX IF NOT EXISTS idx_chat_business_hours_dept_active 
                ON chat_business_hours(tenant_id, department_id, is_active);
            
            -- Tabela: AfterHoursMessage (Mensagem Fora de Horário)
            CREATE TABLE IF NOT EXISTS chat_after_hours_message (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                department_id UUID REFERENCES authn_department(id) ON DELETE CASCADE,
                message_template TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_after_hours_msg_unique 
                ON chat_after_hours_message(tenant_id, department_id) 
                WHERE department_id IS NOT NULL;
            
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_after_hours_msg_tenant_unique 
                ON chat_after_hours_message(tenant_id) 
                WHERE department_id IS NULL;
            
            CREATE INDEX IF NOT EXISTS idx_chat_after_hours_msg_tenant_active 
                ON chat_after_hours_message(tenant_id, is_active);
            
            CREATE INDEX IF NOT EXISTS idx_chat_after_hours_msg_dept_active 
                ON chat_after_hours_message(tenant_id, department_id, is_active);
            
            -- Tabela: AfterHoursTaskConfig (Configuração de Tarefa)
            CREATE TABLE IF NOT EXISTS chat_after_hours_task_config (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                department_id UUID REFERENCES authn_department(id) ON DELETE CASCADE,
                create_task_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                task_title_template VARCHAR(255) NOT NULL DEFAULT 'Retornar contato de {contact_name}',
                task_description_template TEXT NOT NULL DEFAULT 'Cliente entrou em contato fora do horário de atendimento.\n\nHorário: {message_time}\nMensagem: {message_content}\n\nPróximo horário: {next_open_time}',
                task_priority VARCHAR(20) NOT NULL DEFAULT 'high',
                task_due_date_offset_hours INTEGER NOT NULL DEFAULT 2,
                task_type VARCHAR(10) NOT NULL DEFAULT 'task',
                auto_assign_to_department BOOLEAN NOT NULL DEFAULT TRUE,
                auto_assign_to_agent_id INTEGER REFERENCES authn_user(id) ON DELETE SET NULL,
                include_message_preview BOOLEAN NOT NULL DEFAULT TRUE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_after_hours_task_unique 
                ON chat_after_hours_task_config(tenant_id, department_id) 
                WHERE department_id IS NOT NULL;
            
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_after_hours_task_tenant_unique 
                ON chat_after_hours_task_config(tenant_id) 
                WHERE department_id IS NULL;
            
            CREATE INDEX IF NOT EXISTS idx_chat_after_hours_task_tenant_active 
                ON chat_after_hours_task_config(tenant_id, is_active);
            
            CREATE INDEX IF NOT EXISTS idx_chat_after_hours_task_dept_active 
                ON chat_after_hours_task_config(tenant_id, department_id, is_active);
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS chat_after_hours_task_config CASCADE;
            DROP TABLE IF EXISTS chat_after_hours_message CASCADE;
            DROP TABLE IF EXISTS chat_business_hours CASCADE;
            """
        ),
    ]

