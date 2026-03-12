"""
Views para Fluxo (lista/botões por Inbox ou departamento).
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.authn.permissions import IsAdmin
from apps.authn.models import Department
from apps.chat.models_flow import Flow, FlowNode, FlowEdge
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


class FlowViewSet(viewsets.ModelViewSet):
    """CRUD de fluxos por tenant. Filtro: scope, department."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        qs = Flow.objects.filter(tenant=self.request.user.tenant).select_related("department").prefetch_related("nodes", "nodes__edges_out")
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
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=False, methods=["get"])
    def available_departments(self, request):
        """Lista departamentos do tenant para dropdown."""
        departments = Department.objects.filter(tenant=request.user.tenant).order_by("name")
        return Response(DepartmentOptionSerializer(departments, many=True).data)

    @action(detail=True, methods=["post"])
    def send_test(self, request, pk=None):
        """
        Envia o passo inicial do fluxo para um número de teste.
        Body: { "phone": "5511999999999" }
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
        from apps.chat.services.flow_engine import get_start_node
        start_node = get_start_node(flow)
        if not start_node:
            return Response({"detail": "Fluxo sem nó inicial"}, status=status.HTTP_400_BAD_REQUEST)
        if start_node.node_type == FlowNode.NODE_TYPE_DELAY:
            return Response(
                {"detail": "O fluxo começa com uma etapa timer. Para teste, use um nó inicial do tipo mensagem, lista ou botões."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.chat.models import Conversation
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
        from apps.chat.services.flow_engine import send_flow_node
        message = send_flow_node(conversation, start_node)
        if not message:
            return Response({"detail": "Falha ao enfileirar mensagem de teste"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message_id": str(message.id), "conversation_id": str(conversation.id)})


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
