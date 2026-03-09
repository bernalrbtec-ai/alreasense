# Flow schema: lista/botões por Inbox ou departamento. Schema via flow_schema.sql.

import uuid
from pathlib import Path

import django.db.models.deletion
from django.db import migrations, models


def read_flow_schema():
    path = Path(__file__).parent / "flow_schema.sql"
    return path.read_text(encoding="utf-8")


class Migration(migrations.Migration):

    dependencies = [
        ("authn", "0003_add_departments"),
        ("chat", "0016_add_instance_friendly_name"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=read_flow_schema(),
            reverse_sql="""
            DROP TABLE IF EXISTS chat_conversation_flow_state CASCADE;
            DROP TABLE IF EXISTS chat_flow_edge CASCADE;
            DROP TABLE IF EXISTS chat_flow_node CASCADE;
            DROP TABLE IF EXISTS chat_flow CASCADE;
            """,
            state_operations=[
                migrations.CreateModel(
                    name="Flow",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("name", models.CharField(max_length=160, verbose_name="Nome do fluxo")),
                        ("scope", models.CharField(choices=[("inbox", "Inbox"), ("department", "Departamento")], default="inbox", max_length=20, verbose_name="Escopo")),
                        ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("department", models.ForeignKey(blank=True, help_text="Null quando scope=inbox", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="flows", to="authn.department", verbose_name="Departamento")),
                        ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="flows", to="tenancy.tenant", verbose_name="Tenant")),
                    ],
                    options={"db_table": "chat_flow", "ordering": ["name"], "verbose_name": "Fluxo", "verbose_name_plural": "Fluxos"},
                ),
                migrations.CreateModel(
                    name="FlowNode",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("node_type", models.CharField(choices=[("list", "Lista"), ("buttons", "Botões")], max_length=20, verbose_name="Tipo")),
                        ("name", models.CharField(help_text="Ex: inicio, opcao_vendas", max_length=80, verbose_name="Nome interno")),
                        ("order", models.PositiveIntegerField(default=0, verbose_name="Ordem")),
                        ("is_start", models.BooleanField(default=False, help_text="Um único nó inicial por fluxo", verbose_name="Nó inicial")),
                        ("body_text", models.TextField(blank=True, default="", verbose_name="Corpo (lista/botões)")),
                        ("button_text", models.CharField(blank=True, default="", max_length=20, verbose_name="Texto do botão (lista)")),
                        ("header_text", models.CharField(blank=True, default="", max_length=60)),
                        ("footer_text", models.CharField(blank=True, default="", max_length=60)),
                        ("sections", models.JSONField(blank=True, default=list, help_text='[{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]', verbose_name="Seções (lista)")),
                        ("buttons", models.JSONField(blank=True, default=list, help_text='[{"id": "...", "title": "..."}]', verbose_name="Botões")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("flow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="nodes", to="chat.flow", verbose_name="Fluxo")),
                    ],
                    options={"db_table": "chat_flow_node", "ordering": ["flow", "order", "name"], "unique_together": {("flow", "name")}, "verbose_name": "Nó do fluxo", "verbose_name_plural": "Nós do fluxo"},
                ),
                migrations.CreateModel(
                    name="FlowEdge",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("option_id", models.CharField(help_text="rowId da lista ou id do botão", max_length=100, verbose_name="ID da opção")),
                        ("target_action", models.CharField(choices=[("next", "Próxima etapa"), ("transfer", "Transferir"), ("end", "Encerrar")], default="next", max_length=20, verbose_name="Ação")),
                        ("from_node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="edges_out", to="chat.flownode", verbose_name="Nó de origem")),
                        ("target_department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="flow_edges_as_target", to="authn.department", verbose_name="Departamento destino")),
                        ("to_node", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="edges_in", to="chat.flownode", verbose_name="Próximo nó")),
                    ],
                    options={"db_table": "chat_flow_edge", "unique_together": {("from_node", "option_id")}, "verbose_name": "Aresta do fluxo", "verbose_name_plural": "Arestas do fluxo"},
                ),
                migrations.CreateModel(
                    name="ConversationFlowState",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("entered_at", models.DateTimeField(auto_now_add=True)),
                        ("metadata", models.JSONField(blank=True, default=dict)),
                        ("conversation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="flow_state", to="chat.conversation", verbose_name="Conversa")),
                        ("current_node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversation_states", to="chat.flownode", verbose_name="Nó atual")),
                        ("flow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversation_states", to="chat.flow", verbose_name="Fluxo")),
                    ],
                    options={"db_table": "chat_conversation_flow_state", "verbose_name": "Estado de fluxo da conversa", "verbose_name_plural": "Estados de fluxo"},
                ),
            ],
        ),
    ]
