"""
Serializers para a API de rotação de proxies.
"""
from rest_framework import serializers

from .models import ProxyRotationInstanceLog, ProxyRotationLog


class ProxyRotationInstanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProxyRotationInstanceLog
        fields = [
            "id",
            "instance_name",
            "proxy_host",
            "proxy_port",
            "success",
            "error_message",
            "created_at",
        ]


class ProxyRotationLogSerializer(serializers.ModelSerializer):
    instance_logs = ProxyRotationInstanceLogSerializer(many=True, read_only=True)
    created_by_email = serializers.SerializerMethodField()

    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else None

    class Meta:
        model = ProxyRotationLog
        fields = [
            "id",
            "started_at",
            "finished_at",
            "status",
            "num_proxies",
            "num_instances",
            "num_updated",
            "strategy",
            "error_message",
            "triggered_by",
            "created_by_email",
            "created_at",
            "instance_logs",
        ]
