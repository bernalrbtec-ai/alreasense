"""
Views para Fluxo (lista/botões por Inbox ou departamento).
"""
import logging
from datetime import timedelta
from urllib.parse import quote

from django.utils import timezone
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.authn.permissions import IsAdmin
from apps.authn.models import Department
from apps.chat.models_flow import Flow, FlowNode, FlowEdge, ConversationFlowState
from apps.chat.api.serializers_flow import (
    FlowSerializer,
    FlowListSerializer,
    FlowNodeSerializer,
    FlowNodeWriteSerializer,
    FlowEdgeSerializer,
    FlowEdgeWriteSerializer,
    DepartmentOptionSerializer,
)

logger = logging.getLogger(__name__)

try:
    import jwt  # PyJWT (transitive dep via simplejwt)
except Exception:  # pragma: no cover
    jwt = None


class FlowViewSet(viewsets.ModelViewSet):
    """CRUD de fluxos por tenant. Filtro: scope, department."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        qs = Flow.objects.filter(tenant=self.request.user.tenant).select_related("department", "whatsapp_instance").prefetch_related("nodes", "nodes__edges_out")
        scope = self.request.query_params.get("scope")
        if scope:
            qs = qs.filter(scope=scope)
        department_id = self.request.query_params.get("department_id")
        if department_id:
            qs = qs.filter(department_id=department_id)
        return qs.order_by("name")

    def get_serializer_class(self):
        if self.action == "list":
            return FlowListSerializer
        return FlowSerializer

    def perform_create(self, serializer):
        flow = serializer.save(tenant=self.request.user.tenant)
        # Garante workspace/bot associado ao fluxo (se APIs estiverem configuradas)
        try:
            from apps.chat.services.typebot_flow_service import ensure_typebot_bot_for_flow

            ensure_typebot_bot_for_flow(flow)
        except Exception as e:
            logger.warning("[FLOW] Erro ao agendar criação de bot Typebot para flow=%s: %s", getattr(flow, "id", None), e, exc_info=True)

    def perform_update(self, serializer):
        flow = serializer.save()
        # Em update/edit, também garantimos workspace/bot e completamos internal_id se necessário.
        try:
            from apps.chat.services.typebot_flow_service import ensure_typebot_bot_for_flow

            ensure_typebot_bot_for_flow(flow)
        except Exception as e:
            logger.warning("[FLOW] Erro ao garantir bot/workspace para flow=%s: %s", getattr(flow, "id", None), e, exc_info=True)

    def retrieve(self, request, *args, **kwargs):
        # Em buscar/abrir detalhes, garantir workspace/bot e internal_id antes de serializar (para o editor embutido).
        try:
            flow = self.get_object()
            from apps.chat.services.typebot_flow_service import ensure_typebot_bot_for_flow

            ensure_typebot_bot_for_flow(flow)
        except Exception as e:
            logger.warning("[FLOW] Erro ao completar integração no retrieve flow=%s: %s", getattr(kwargs, "pk", None), e, exc_info=True)
        serializer = self.get_serializer(self.get_object())
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="typebot_builder_login_url")
    def typebot_builder_login_url(self, request, pk=None):
        """
        Retorna uma URL de auto-login no Typebot Builder (para uso em iframe).
        Requer:
        - settings.SENSE_IFRAME_LOGIN_SECRET (mesmo valor no Typebot)
        - settings.TYPEBOT_BUILDER_BASE (domínio do builder, ex.: https://typebot.alrea.ai)
        """
        flow = self.get_object()
        if not (getattr(flow, "typebot_internal_id", None) or "").strip():
            return Response({"detail": "Bot ainda não sincronizado."}, status=status.HTTP_409_CONFLICT)

        builder_base = (getattr(settings, "TYPEBOT_BUILDER_BASE", None) or "").strip().rstrip("/")
        if not builder_base:
            return Response({"detail": "TYPEBOT_BUILDER_BASE não configurado no backend."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        secret = (getattr(settings, "SENSE_IFRAME_LOGIN_SECRET", None) or "").strip()
        if not secret:
            return Response({"detail": "SENSE_IFRAME_LOGIN_SECRET não configurado."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if jwt is None:
            return Response({"detail": "PyJWT não disponível no backend."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        locale = (request.data.get("locale") or "pt-BR").strip() or "pt-BR"
        # Caminho relativo dentro do builder
        return_to = f"/{locale}/typebots/{(flow.typebot_internal_id or '').strip()}/edit"

        now = timezone.now()
        payload = {
            "aud": "typebot-builder",
            "iss": "sense",
            "tenant_id": str(request.user.tenant_id),
            "user_id": str(getattr(request.user, "id", "")),
            "flow_id": str(getattr(flow, "id", "")),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=60)).timestamp()),
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        # Garantir querystring segura
        token_q = quote(token, safe="")
        return_to_q = quote(return_to, safe="/")
        login_url = f"{builder_base}/api/sense/iframe-login?token={token_q}&returnTo={return_to_q}"
        return Response({"loginUrl": login_url, "expiresIn": 60, "returnTo": return_to})

    @action(detail=False, methods=["get"])
    def available_departments(self, request):
        """Lista departamentos do tenant para dropdown."""
        departments = Department.objects.filter(tenant=request.user.tenant).order_by("name")
        return Response(DepartmentOptionSerializer(departments, many=True).data)

    @action(detail=False, methods=["get"])
    def available_instances(self, request):
        """Lista instâncias WhatsApp ativas do tenant para o fluxo enviar/responder por uma delas."""
        from apps.notifications.models import WhatsAppInstance
        instances = WhatsAppInstance.objects.filter(
            tenant=request.user.tenant,
            is_active=True,
        ).order_by("friendly_name").values("id", "friendly_name", "instance_name")
        return Response(list(instances))

    @action(detail=True, methods=["post"])
    def send_test(self, request, pk=None):
        """
        Envia o passo inicial do fluxo para um número de teste.
        Body: { "phone": "5511999999999" }
        Se o fluxo for Typebot (typebot_public_id preenchido), inicia a sessão Typebot e envia as primeiras mensagens.
        """
        flow = self.get_object()
        from apps.tenancy.models import Tenant
        allow = Tenant.objects.filter(id=request.user.tenant_id).values_list("allow_meta_interactive_buttons", flat=True).first()
        if allow is False:
            return Response(
                {"detail": "Botões interativos estão desativados para este tenant. Ative em configurações do tenant."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        phone = (request.data.get("phone") or "").strip()
        if not phone:
            return Response({"detail": "phone é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)
        from apps.chat.models import Conversation
        from apps.chat.models_flow import ConversationFlowState
        phone_digits = "".join(c for c in phone.replace("+", "").replace(" ", "").replace("-", "") if c.isdigit())
        if not phone_digits:
            return Response({"detail": "Número de telefone inválido"}, status=status.HTTP_400_BAD_REQUEST)
        search_suffix = phone_digits[-11:] if len(phone_digits) >= 11 else phone_digits
        candidates = Conversation.objects.filter(
            tenant=request.user.tenant,
            contact_phone__icontains=search_suffix,
        ).exclude(contact_phone__contains="@g.us")
        conversation = None
        for c in candidates:
            c_digits = "".join(x for x in (c.contact_phone or "") if x.isdigit())
            if c_digits == phone_digits or (len(phone_digits) >= 11 and c_digits.endswith(phone_digits[-11:])):
                conversation = c
                break
        if not conversation:
            return Response(
                {"detail": "Crie uma conversa com esse número antes ou use um número que já tenha conversa"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Fluxo Typebot: iniciar sessão e enviar mensagens via API
        if (getattr(flow, "typebot_public_id", None) or "").strip():
            from apps.chat.services.typebot_flow_service import start_typebot_flow
            ConversationFlowState.objects.filter(conversation_id=conversation.id).delete()
            ok, _ = start_typebot_flow(conversation, flow)
            if ok:
                return Response({"message_id": "typebot", "conversation_id": str(conversation.id)})
            return Response({"detail": "Falha ao iniciar Typebot (verifique Public ID e URL base)."}, status=status.HTTP_502_BAD_GATEWAY)
        from apps.chat.services.flow_engine import get_start_node
        start_node = get_start_node(flow)
        if not start_node:
            return Response({"detail": "Fluxo sem nó inicial"}, status=status.HTTP_400_BAD_REQUEST)
        if start_node.node_type == FlowNode.NODE_TYPE_DELAY:
            return Response(
                {"detail": "O fluxo começa com uma etapa timer. Para teste, use um nó inicial do tipo mensagem, lista ou botões."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.notifications.models import WhatsAppInstance
        instance = WhatsAppInstance.objects.filter(tenant=request.user.tenant, is_active=True).first()
        if not instance:
            return Response({"detail": "Nenhuma instância WhatsApp ativa"}, status=status.HTTP_400_BAD_REQUEST)
        if start_node.node_type in (FlowNode.NODE_TYPE_LIST, FlowNode.NODE_TYPE_BUTTONS) and getattr(
            instance, "integration_type", None
        ) == WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION:
            return Response(
                {
                    "detail": "Lista e botões estão desativados para instâncias Evolution API (bug na v2.3.7). "
                    "O fluxo de teste usaria o nó inicial como lista/botões. Use uma instância Meta ou altere o nó inicial para mensagem de texto."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.chat.services.flow_engine import send_flow_node, _auto_advance_message_chain
        state, created = ConversationFlowState.objects.get_or_create(
            conversation_id=conversation.id,
            defaults={"flow_id": flow.id, "current_node_id": start_node.id},
        )
        if not created:
            state.flow_id = flow.id
            state.current_node_id = start_node.id
            state.save(update_fields=["flow_id", "current_node_id"])
        message = send_flow_node(conversation, start_node)
        if not message:
            if created:
                state.delete()
            return Response({"detail": "Falha ao enfileirar mensagem de teste"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        _auto_advance_message_chain(conversation, state)
        return Response({"message_id": str(message.id), "conversation_id": str(conversation.id)})

    @action(detail=False, methods=["post"], url_path="validate_typebot")
    def validate_typebot(self, request):
        """
        Valida se o Typebot está acessível com o Public ID e URL base informados.
        Body: { "typebot_public_id": "...", "typebot_base_url": "..." (opcional) }
        Chama startChat com payload mínimo; se retornar sessionId, considera válido.
        """
        import requests
        typebot_public_id = (request.data.get("typebot_public_id") or "").strip()
        typebot_base_url = (request.data.get("typebot_base_url") or "").strip().rstrip("/")
        if not typebot_public_id:
            return Response(
                {"valid": False, "detail": "Public ID do Typebot é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Se URL base não vier do frontend, use o viewer (chat) configurado no backend.
        base = typebot_base_url or (getattr(settings, "TYPEBOT_VIEWER_BASE", None) or "https://typebot.io/api/v1")
        base = (base or "").strip().rstrip("/")
        if base and not base.endswith("/api/v1"):
            base = f"{base}/api/v1"
        url = f"{base}/typebots/{typebot_public_id}/startChat"
        try:
            r = requests.post(url, json={"prefilledVariables": {}}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("sessionId"):
                    return Response({"valid": True})
            return Response(
                {"valid": False, "detail": f"Typebot não respondeu corretamente (HTTP {r.status_code}). Verifique o Public ID e a URL base."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except requests.RequestException as e:
            logger.warning("[FLOW] validate_typebot request failed: %s", e)
            return Response(
                {"valid": False, "detail": "Não foi possível conectar ao Typebot. Verifique a URL base e se o Typebot está acessível."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    @action(detail=True, methods=["post"], url_path="fetch_typebot_variables")
    def fetch_typebot_variables(self, request, pk=None):
        """
        Consulta as variáveis do fluxo Typebot via API do dashboard (Builder API).
        Usa typebot_internal_id e typebot_api_key do fluxo, ou do body (typebot_internal_id, typebot_api_key).
        Retorna lista de variáveis [{ "id", "name" }] para mapeamento no cadastro.
        """
        import requests
        flow = self.get_object()
        internal_id = (request.data.get("typebot_internal_id") or getattr(flow, "typebot_internal_id", None) or "").strip()
        api_key = (request.data.get("typebot_api_key") or getattr(flow, "typebot_api_key", None) or "").strip()
        if not internal_id or not api_key:
            return Response(
                {"detail": "Configure 'ID interno do Typebot' e 'API key Typebot (dashboard)' no fluxo para carregar as variáveis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Builder API (publishedTypebot) fica em app.typebot.io no Typebot cloud.
        # typebot.co é só para o chat público; o dashboard/API é app.typebot.io.
        base_url = (getattr(flow, "typebot_base_url", None) or "").strip().rstrip("/").lower()
        if base_url and ("typebot.co" in base_url or "typebot.io" in base_url):
            builder_base = "https://app.typebot.io"
        elif base_url:
            builder_base = base_url.replace("/api/v1", "").rstrip("/") or base_url
        else:
            builder_base = "https://app.typebot.io"
        url = f"{builder_base}/api/v1/typebots/{internal_id}/publishedTypebot"
        try:
            r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
            if r.status_code == 401:
                return Response(
                    {"detail": "API key inválida ou expirada. Verifique no dashboard do Typebot."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if r.status_code == 404:
                return Response(
                    {"detail": "Typebot não encontrado. Verifique o ID interno (URL do typebot ao editar)."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            logger.warning("[FLOW] fetch_typebot_variables request failed: %s", e)
            return Response(
                {"detail": "Não foi possível conectar à API do Typebot. Verifique a URL base e a API key."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        published = data.get("publishedTypebot")
        if not published:
            return Response({"variables": []}, status=status.HTTP_200_OK)
        variables = published.get("variables")
        if not isinstance(variables, list):
            return Response({"variables": []}, status=status.HTTP_200_OK)
        out = []
        for v in variables:
            if not isinstance(v, dict):
                continue
            vid = v.get("id")
            name = v.get("name")
            if vid and name:
                out.append({"id": str(vid), "name": str(name)})
        return Response({"variables": out}, status=status.HTTP_200_OK)


class FlowNodeViewSet(viewsets.ModelViewSet):
    """CRUD de nós de um fluxo. Filtro: flow_id."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        qs = FlowNode.objects.filter(flow__tenant=self.request.user.tenant).select_related("flow").prefetch_related("edges_out")
        flow_id = self.request.query_params.get("flow_id")
        if flow_id:
            qs = qs.filter(flow_id=flow_id)
        return qs.order_by("flow", "order", "name")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FlowNodeWriteSerializer
        return FlowNodeSerializer

    def perform_create(self, serializer):
        flow = serializer.validated_data.get("flow")
        if flow.tenant_id != self.request.user.tenant_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Flow de outro tenant.")
        serializer.save()


class FlowEdgeViewSet(viewsets.ModelViewSet):
    """CRUD de arestas. Filtro: from_node_id ou flow_id."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        qs = FlowEdge.objects.filter(from_node__flow__tenant=self.request.user.tenant).select_related(
            "from_node", "to_node", "target_department"
        )
        from_node_id = self.request.query_params.get("from_node_id")
        if from_node_id:
            qs = qs.filter(from_node_id=from_node_id)
        flow_id = self.request.query_params.get("flow_id")
        if flow_id:
            qs = qs.filter(from_node__flow_id=flow_id)
        return qs

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        from_node = serializer.validated_data.get("from_node")
        if from_node and from_node.flow.tenant_id != self.request.user.tenant_id:
            raise PermissionDenied("Nó de origem não pertence ao seu tenant.")
        target_department = serializer.validated_data.get("target_department")
        if target_department and target_department.tenant_id != self.request.user.tenant_id:
            raise PermissionDenied("Departamento não pertence ao seu tenant.")
        serializer.save()

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        from_node = serializer.validated_data.get("from_node") or serializer.instance.from_node
        if from_node.flow.tenant_id != self.request.user.tenant_id:
            raise PermissionDenied("Nó de origem não pertence ao seu tenant.")
        target_department = serializer.validated_data.get("target_department")
        if target_department and target_department.tenant_id != self.request.user.tenant_id:
            raise PermissionDenied("Departamento não pertence ao seu tenant.")
        serializer.save()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FlowEdgeWriteSerializer
        return FlowEdgeSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def typebot_webhook(request):
    """
    Webhook para o Typebot enviar variáveis/resultado de volta ao Sense.
    Chamado pelo bloco "Webhook" do Typebot. Não requer autenticação.

    Body (JSON):
      - session_id (opcional): sessionId retornado pelo startChat.
      - result_id (opcional): resultId retornado pelo startChat (se não tiver session_id).
      - variables (obrigatório): objeto com chave/valor (ex: {"nome": "João", "email": "j@x.com"}).

    Persiste em ConversationFlowState.metadata["typebot_variables"] e em
    Conversation.metadata["typebot_result"] para consulta na conversa.

    Fechar conversa pelo Typebot: inclua em variables uma das chaves com valor true/1/sim:
      - close_conversation
      - encerrar_conversa
    O Sense marcará mensagens como lidas, definirá status=closed, limpará departamento/atendente
    e removerá o estado do fluxo. Envie a mensagem de despedida no Typebot antes do bloco Webhook.
    """
    try:
        data = request.data if isinstance(request.data, dict) else {}
    except Exception:
        data = {}
    variables = data.get("variables")
    if not isinstance(variables, dict):
        return Response(
            {"detail": "Campo 'variables' (objeto) é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    session_id = (data.get("session_id") or "").strip()
    result_id = (data.get("result_id") or "").strip()
    if not session_id and not result_id:
        return Response(
            {"detail": "Informe 'session_id' ou 'result_id'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    state = None
    if session_id:
        state = (
            ConversationFlowState.objects.filter(typebot_session_id=session_id)
            .select_related("conversation")
            .first()
        )
    if not state and result_id:
        state = (
            ConversationFlowState.objects.filter(metadata__typebot_result_id=result_id)
            .select_related("conversation")
            .first()
        )
    if not state:
        return Response(
            {"detail": "Sessão ou resultado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    # Normalizar valores para string (evitar tipos que não serializam bem)
    vars_simple = {}
    for k, v in variables.items():
        if k is None:
            continue
        key = str(k).strip()
        if not key:
            continue
        if v is None:
            vars_simple[key] = ""
        elif isinstance(v, (str, int, float, bool)):
            vars_simple[key] = str(v)
        else:
            vars_simple[key] = str(v)
    if not state.metadata:
        state.metadata = {}
    state.metadata["typebot_variables"] = {**(state.metadata.get("typebot_variables") or {}), **vars_simple}
    state.save(update_fields=["metadata"])
    conversation = state.conversation
    if conversation:
        if not conversation.metadata:
            conversation.metadata = {}
        conversation.metadata["typebot_result"] = {
            "variables": state.metadata["typebot_variables"],
            "updated_at": timezone.now().isoformat(),
        }
        conversation.save(update_fields=["metadata"])
        # Alinhar com cadastro de contato: atualizar ou criar Contact com nome/telefone/email do Typebot
        try:
            from django.db.models import Q
            from apps.contacts.models import Contact
            from apps.contacts.signals import normalize_phone_for_search
            phone_norm = normalize_phone_for_search(conversation.contact_phone or "")
            if not phone_norm or not conversation.tenant_id:
                pass
            else:
                contact = Contact.objects.filter(
                    Q(tenant_id=conversation.tenant_id) & (Q(phone=phone_norm) | Q(phone=conversation.contact_phone))
                ).first()
                name_val = (
                    vars_simple.get("NomeContato") or vars_simple.get("name") or vars_simple.get("nome") or ""
                ).strip()
                email_val = (vars_simple.get("email") or "").strip()
                phone_val = (
                    vars_simple.get("NumeroFone") or vars_simple.get("number") or conversation.contact_phone or ""
                ).strip()
                if contact:
                    updated = False
                    if name_val and contact.name != name_val:
                        contact.name = name_val
                        updated = True
                    if email_val is not None and contact.email != email_val:
                        contact.email = email_val
                        updated = True
                    if phone_val and contact.phone != phone_val:
                        contact.phone = normalize_phone_for_search(phone_val) or phone_val
                        updated = True
                    if updated:
                        contact.save()
                        logger.info("[TYPEBOT WEBHOOK] Contato atualizado contact=%s", contact.id)
                else:
                    if name_val or email_val or conversation.contact_phone:
                        new_name = name_val or conversation.contact_name or "Contato"
                        new_phone = normalize_phone_for_search(phone_val or conversation.contact_phone) or (conversation.contact_phone or "").strip()
                        if new_phone:
                            Contact.objects.create(
                                tenant_id=conversation.tenant_id,
                                phone=new_phone,
                                name=new_name,
                                email=email_val or "",
                            )
                            logger.info("[TYPEBOT WEBHOOK] Contato criado para conversation=%s", conversation.id)
        except Exception as e:
            logger.warning("[TYPEBOT WEBHOOK] Erro ao sincronizar contato: %s", e, exc_info=True)

    # Fechar conversa a partir do Typebot: se variáveis contiverem close_conversation ou encerrar_conversa = true/1/sim
    close_flag = (
        vars_simple.get("close_conversation") or vars_simple.get("encerrar_conversa") or ""
    ).strip().lower()
    if close_flag in ("true", "1", "sim", "yes", "sí"):
        try:
            from apps.chat.services.typebot_flow_service import close_conversation_from_typebot
            close_conversation_from_typebot(conversation)
        except Exception as e:
            logger.warning("[TYPEBOT WEBHOOK] Erro ao fechar conversa: %s", e, exc_info=True)

    logger.info("[TYPEBOT WEBHOOK] Variáveis salvas conversation=%s keys=%s", state.conversation_id, list(vars_simple.keys()))
    return Response({"ok": True, "saved_keys": list(vars_simple.keys())}, status=status.HTTP_200_OK)
