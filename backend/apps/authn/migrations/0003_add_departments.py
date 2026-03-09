# Generated manually for Department model and departments ManyToMany field

import uuid

import django.db.models.deletion
from django.db import migrations, models


def setup_department_if_not_exist(apps, schema_editor):
    """
    Verifica e adiciona Department e campo departments apenas se não existirem.
    """
    from django.db import connection
    
    with connection.cursor() as cursor:
        # 1. Verifica se tabela authn_department existe
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE tablename='authn_department';
        """)
        dept_table_exists = cursor.fetchone()
        
        if dept_table_exists:
            print("✅ Tabela authn_department já existe")
        else:
            print("➕ Criando tabela authn_department")
            cursor.execute("""
                CREATE TABLE authn_department (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    color VARCHAR(7) NOT NULL DEFAULT '#3b82f6',
                    ai_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    UNIQUE (tenant_id, name)
                );
            """)
            cursor.execute("""
                CREATE INDEX authn_department_tenant_id_idx ON authn_department(tenant_id);
            """)
        
        # 2. Verifica tabela ManyToMany user_departments
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE tablename='authn_user_departments';
        """)
        m2m_table_exists = cursor.fetchone()
        
        if m2m_table_exists:
            print("✅ Tabela authn_user_departments já existe")
        else:
            print("➕ Criando tabela authn_user_departments")
            cursor.execute("""
                CREATE TABLE authn_user_departments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES authn_user(id) ON DELETE CASCADE,
                    department_id UUID NOT NULL REFERENCES authn_department(id) ON DELETE CASCADE,
                    UNIQUE (user_id, department_id)
                );
            """)
            cursor.execute("""
                CREATE INDEX authn_user_departments_user_id_idx 
                ON authn_user_departments(user_id);
            """)
            cursor.execute("""
                CREATE INDEX authn_user_departments_department_id_idx 
                ON authn_user_departments(department_id);
            """)


class Migration(migrations.Migration):

    dependencies = [
        ("authn", "0002_initial"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        # Usa RunPython para verificar e criar tudo apenas se necessário
        migrations.RunPython(
            setup_department_if_not_exist,
            reverse_code=migrations.RunPython.noop
        ),
        # Atualiza apenas o estado das migrations (tabela já criada acima) para que
        # outras apps (ex.: chat 0017) possam referenciar authn.department.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Department",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("name", models.CharField(max_length=100)),
                        ("color", models.CharField(default="#3b82f6", max_length=7)),
                        ("ai_enabled", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="departments", to="tenancy.tenant")),
                    ],
                    options={},
                ),
            ],
        ),
    ]

