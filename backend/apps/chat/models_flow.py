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
    description = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Descrição breve",
        help_text="Descrição opcional exibida ao escolher o fluxo (ex.: menu de abertura de chamados).",
    )
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
    whatsapp_instance = models.ForeignKey(
        "notifications.WhatsAppInstance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flows",
        verbose_name="Instância WhatsApp",
        help_text="Quando definida, o fluxo envia/responde por esta instância.",
    )
    # Typebot: quando preenchido, o fluxo é executado pelo Typebot (em vez de nós/arestas).
    typebot_public_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Typebot Public ID",
        help_text="ID público do Typebot (Share > API). Deixe vazio para usar fluxo com nós/lista/botões.",
    )
    typebot_base_url = models.URLField(
        blank=True,
        default="",
        verbose_name="Typebot Base URL",
        help_text="URL base da API do Typebot (ex: https://typebot.io ou self-hosted). Vazio = typebot.io",
    )
    typebot_prefilled_extra = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Typebot variáveis extras",
        help_text='Variáveis adicionais enviadas ao Typebot em prefilledVariables (ex: {"campanha": "black-friday"}). Chaves e valores devem ser string.',
    )
    typebot_internal_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Typebot ID interno (dashboard)",
        help_text="ID do typebot no dashboard (URL ao editar). Usado com API key para buscar lista de variáveis.",
    )
    typebot_api_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Typebot API key (dashboard)",
        help_text="Token da API do Typebot (dashboard) para consultar variáveis do fluxo. Opcional.",
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
    """Etapa do fluxo: mensagem, imagem, arquivo, lista ou botões."""

    NODE_TYPE_MESSAGE = "message"
    NODE_TYPE_IMAGE = "image"
    NODE_TYPE_FILE = "file"
    NODE_TYPE_LIST = "list"
    NODE_TYPE_BUTTONS = "buttons"
    NODE_TYPE_DELAY = "delay"
    NODE_TYPE_CHOICES = [
        (NODE_TYPE_MESSAGE, "Mensagem (texto)"),
        (NODE_TYPE_IMAGE, "Imagem"),
        (NODE_TYPE_FILE, "Arquivo"),
        (NODE_TYPE_LIST, "Lista"),
        (NODE_TYPE_BUTTONS, "Botões"),
        (NODE_TYPE_DELAY, "Timer (espera em segundos)"),
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

    # Mídia (imagem/arquivo): URL acessível pela instância (ex: /media/ hash ou URL pública)
    media_url = models.CharField(
        max_length=1024,
        blank=True,
        default="",
        verbose_name="URL da mídia",
        help_text="Para tipo imagem ou arquivo: URL da imagem/documento (até 1024 caracteres).",
    )

    # Posição no canvas (arrastar e soltar); null = usar layout por order
    position_x = models.FloatField(null=True, blank=True, verbose_name="Posição X")
    position_y = models.FloatField(null=True, blank=True, verbose_name="Posição Y")

    # Timer (só para node_type=delay): esperar N segundos antes de ir para o próximo nó
    delay_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Espera (segundos)",
        help_text="Para tipo timer: quantos segundos esperar antes da próxima etapa.",
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
    """Estado do fluxo por conversa: nó atual (fluxo Sense) ou sessão Typebot."""

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
        null=True,
        blank=True,
        verbose_name="Nó atual",
        help_text="Null quando o fluxo é Typebot (usa typebot_session_id).",
    )
    typebot_session_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Typebot Session ID",
        help_text="Sessão retornada pelo Typebot startChat; usado em continueChat.",
    )
    entered_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "chat_conversation_flow_state"
        verbose_name = "Estado de fluxo da conversa"
        verbose_name_plural = "Estados de fluxo"

    def __str__(self):
        if self.typebot_session_id:
            return f"{self.conversation_id} @ Typebot({self.typebot_session_id[:16]}...)"
        return f"{self.conversation_id} @ {self.current_node.name if self.current_node else '?'}"
