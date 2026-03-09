"""
Serializers para Fluxo (lista/botões por Inbox ou departamento).
"""
from rest_framework import serializers
from apps.chat.models_flow import Flow, FlowNode, FlowEdge
from apps.authn.models import Department


class DepartmentOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "color"]
        read_only_fields = ["id", "name", "color"]


class FlowEdgeSerializer(serializers.ModelSerializer):
    from_node_name = serializers.CharField(source="from_node.name", read_only=True)
    to_node_name = serializers.CharField(source="to_node.name", read_only=True, allow_null=True)
    target_department_name = serializers.CharField(source="target_department.name", read_only=True, allow_null=True)

    class Meta:
        model = FlowEdge
        fields = [
            "id",
            "from_node",
            "from_node_name",
            "option_id",
            "to_node",
            "to_node_name",
            "target_department",
            "target_department_name",
            "target_action",
        ]
        read_only_fields = ["id"]


class FlowNodeSerializer(serializers.ModelSerializer):
    edges_out = FlowEdgeSerializer(many=True, read_only=True)

    class Meta:
        model = FlowNode
        fields = [
            "id",
            "flow",
            "node_type",
            "name",
            "order",
            "is_start",
            "body_text",
            "button_text",
            "header_text",
            "footer_text",
            "sections",
            "buttons",
            "edges_out",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FlowNodeWriteSerializer(serializers.ModelSerializer):
    """Serializer para criar/atualizar nó sem edges aninhados."""

    class Meta:
        model = FlowNode
        fields = [
            "id",
            "flow",
            "node_type",
            "name",
            "order",
            "is_start",
            "body_text",
            "button_text",
            "header_text",
            "footer_text",
            "sections",
            "buttons",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Nome do nó é obrigatório.")
        return name

    def validate(self, attrs):
        node_type = attrs.get("node_type") or (self.instance.node_type if self.instance else None)
        if node_type == FlowNode.NODE_TYPE_LIST:
            body = (attrs.get("body_text") or "").strip()
            btn = (attrs.get("button_text") or "").strip()
            if not body:
                raise serializers.ValidationError({"body_text": "Corpo da mensagem é obrigatório para lista."})
            if not btn:
                raise serializers.ValidationError({"button_text": "Texto do botão é obrigatório para lista."})
            sections = attrs.get("sections")
            if not sections or not isinstance(sections, list):
                raise serializers.ValidationError({"sections": "Lista exige ao menos uma seção com linhas."})
            for i, sec in enumerate(sections):
                if not isinstance(sec, dict):
                    raise serializers.ValidationError({"sections": f"Seção {i + 1}: deve ser um objeto com title e rows."})
                rows = sec.get("rows")
                if not rows or not isinstance(rows, list):
                    raise serializers.ValidationError({"sections": f"Seção {i + 1}: use title e rows (array de itens com id e title)."})
                for j, row in enumerate(rows):
                    if not isinstance(row, dict) or not row.get("id") or not row.get("title"):
                        raise serializers.ValidationError({"sections": f"Seção {i + 1}, linha {j + 1}: use id e title."})
        elif node_type == FlowNode.NODE_TYPE_BUTTONS:
            body = (attrs.get("body_text") or "").strip()
            if not body:
                raise serializers.ValidationError({"body_text": "Corpo da mensagem é obrigatório para botões."})
            buttons = attrs.get("buttons")
            if not buttons or not isinstance(buttons, list):
                raise serializers.ValidationError({"buttons": "Botões exige um array com 1 a 3 itens."})
            if len(buttons) < 1 or len(buttons) > 3:
                raise serializers.ValidationError({"buttons": "Informe entre 1 e 3 botões."})
            for i, b in enumerate(buttons):
                if not isinstance(b, dict) or not b.get("id") or not b.get("title"):
                    raise serializers.ValidationError({"buttons": f"Botão {i + 1}: use id e title."})
        return attrs


class FlowEdgeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowEdge
        fields = [
            "id",
            "from_node",
            "option_id",
            "to_node",
            "target_department",
            "target_action",
        ]
        read_only_fields = ["id"]

    def validate_option_id(self, value):
        option_id = (value or "").strip()
        if not option_id:
            raise serializers.ValidationError("ID da opção é obrigatório.")
        return option_id[:100]

    def validate(self, attrs):
        action = attrs.get("target_action", FlowEdge.TARGET_ACTION_NEXT)
        if action == FlowEdge.TARGET_ACTION_NEXT and not attrs.get("to_node"):
            raise serializers.ValidationError({"to_node": "Próxima etapa exige um próximo nó."})
        if action == FlowEdge.TARGET_ACTION_TRANSFER and not attrs.get("target_department"):
            raise serializers.ValidationError({"target_department": "Transferir exige um departamento."})
        if action == FlowEdge.TARGET_ACTION_END:
            attrs["to_node"] = None
            attrs["target_department"] = None
        elif action == FlowEdge.TARGET_ACTION_NEXT:
            attrs["target_department"] = None
        elif action == FlowEdge.TARGET_ACTION_TRANSFER:
            attrs["to_node"] = None
        from_node = attrs.get("from_node") or (self.instance.from_node if self.instance else None)
        to_node = attrs.get("to_node")
        if from_node and to_node and from_node.flow_id != to_node.flow_id:
            raise serializers.ValidationError({"to_node": "O próximo nó deve pertencer ao mesmo fluxo."})
        return attrs


class FlowSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    nodes = FlowNodeSerializer(many=True, read_only=True)

    class Meta:
        model = Flow
        fields = [
            "id",
            "tenant",
            "name",
            "scope",
            "department",
            "department_name",
            "is_active",
            "nodes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class FlowListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)

    class Meta:
        model = Flow
        fields = [
            "id",
            "name",
            "scope",
            "department",
            "department_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
