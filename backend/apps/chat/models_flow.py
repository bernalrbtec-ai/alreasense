"""
Modelos para fluxo conversacional com lista e botões (por Inbox ou departamento).
Cada etapa é lista ou botões; cada opção leva a outra etapa, a um departamento ou a encerrar.
"""
import uuid
from django.db import models


class Flow(models.Model):
    """Fluxo por escopo: Inbox (department=null) ou um departamento."""

    SCOPE_INBOX = "inbox"
    SCOPE_DEPARTMENT = "department"
    SCOPE_CHOICES = [
        (SCOPE_INBOX, "Inbox"),
        (SCOPE_DEPARTMENT, "Departamento"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="flows",
        verbose_name="Tenant",
    )
    name = models.CharField(max_length=160, verbose_name="Nome do fluxo")
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default=SCOPE_INBOX,
        verbose_name="Escopo",
    )
    department = models.ForeignKey(
        "authn.Department",
        on_delete=models.CASCADE,
        related_name="flows",
        null=True,
        blank=True,
        verbose_name="Departamento",
        help_text="Null quando scope=inbox",
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_flow"
        verbose_name = "Fluxo"
        verbose_name_plural = "Fluxos"
        ordering = ["name"]

    def __str__(self):
        scope_label = "Inbox" if self.scope == self.SCOPE_INBOX else (self.department.name if self.department else "?")
        return f"{self.name} ({scope_label})"


class FlowNode(models.Model):
    """Etapa do fluxo: lista ou botões."""

    NODE_TYPE_LIST = "list"
    NODE_TYPE_BUTTONS = "buttons"
    NODE_TYPE_CHOICES = [
        (NODE_TYPE_LIST, "Lista"),
        (NODE_TYPE_BUTTONS, "Botões"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        Flow,
        on_delete=models.CASCADE,
        related_name="nodes",
        verbose_name="Fluxo",
    )
    node_type = models.CharField(
        max_length=20,
        choices=NODE_TYPE_CHOICES,
        verbose_name="Tipo",
    )
    name = models.CharField(
        max_length=80,
        verbose_name="Nome interno",
        help_text="Ex: inicio, opcao_vendas",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    is_start = models.BooleanField(
        default=False,
        verbose_name="Nó inicial",
        help_text="Um único nó inicial por fluxo",
    )

    # Conteúdo (lista)
    body_text = models.TextField(blank=True, default="", verbose_name="Corpo (lista/botões)")
    button_text = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Texto do botão (lista)",
    )
    header_text = models.CharField(max_length=60, blank=True, default="")
    footer_text = models.CharField(max_length=60, blank=True, default="")
    sections = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Seções (lista)",
        help_text='[{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]',
    )

    # Conteúdo (botões): body_text + buttons
    buttons = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Botões",
        help_text='[{"id": "...", "title": "..."}]',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_flow_node"
        verbose_name = "Nó do fluxo"
        verbose_name_plural = "Nós do fluxo"
        unique_together = [["flow", "name"]]
        ordering = ["flow", "order", "name"]

    def __str__(self):
        return f"{self.flow.name} / {self.name} ({self.get_node_type_display()})"


class FlowEdge(models.Model):
    """Aresta: opção (rowId ou button id) -> próximo nó, departamento ou encerrar."""

    TARGET_ACTION_NEXT = "next"
    TARGET_ACTION_TRANSFER = "transfer"
    TARGET_ACTION_END = "end"
    TARGET_ACTION_CHOICES = [
        (TARGET_ACTION_NEXT, "Próxima etapa"),
        (TARGET_ACTION_TRANSFER, "Transferir"),
        (TARGET_ACTION_END, "Encerrar"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_node = models.ForeignKey(
        FlowNode,
        on_delete=models.CASCADE,
        related_name="edges_out",
        verbose_name="Nó de origem",
    )
    option_id = models.CharField(
        max_length=100,
        verbose_name="ID da opção",
        help_text="rowId da lista ou id do botão",
    )
    to_node = models.ForeignKey(
        FlowNode,
        on_delete=models.CASCADE,
        related_name="edges_in",
        null=True,
        blank=True,
        verbose_name="Próximo nó",
    )
    target_department = models.ForeignKey(
        "authn.Department",
        on_delete=models.CASCADE,
        related_name="flow_edges_as_target",
        null=True,
        blank=True,
        verbose_name="Departamento destino",
    )
    target_action = models.CharField(
        max_length=20,
        choices=TARGET_ACTION_CHOICES,
        default=TARGET_ACTION_NEXT,
        verbose_name="Ação",
    )

    class Meta:
        db_table = "chat_flow_edge"
        verbose_name = "Aresta do fluxo"
        verbose_name_plural = "Arestas do fluxo"
        unique_together = [["from_node", "option_id"]]

    def __str__(self):
        if self.to_node:
            return f"{self.from_node.name} --[{self.option_id}]--> {self.to_node.name}"
        if self.target_department:
            return f"{self.from_node.name} --[{self.option_id}]--> {self.target_department.name}"
        return f"{self.from_node.name} --[{self.option_id}]--> encerrar"


class ConversationFlowState(models.Model):
    """Estado do fluxo por conversa: em qual nó a conversa está."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(
        "chat.Conversation",
        on_delete=models.CASCADE,
        related_name="flow_state",
        verbose_name="Conversa",
    )
    flow = models.ForeignKey(
        Flow,
        on_delete=models.CASCADE,
        related_name="conversation_states",
        verbose_name="Fluxo",
    )
    current_node = models.ForeignKey(
        FlowNode,
        on_delete=models.CASCADE,
        related_name="conversation_states",
        verbose_name="Nó atual",
    )
    entered_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "chat_conversation_flow_state"
        verbose_name = "Estado de fluxo da conversa"
        verbose_name_plural = "Estados de fluxo"

    def __str__(self):
        return f"{self.conversation_id} @ {self.current_node.name}"
