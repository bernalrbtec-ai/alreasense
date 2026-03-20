"""
Serializers para a API de rotação de proxies.
"""
from rest_framework import serializers

from .models import (
    ProxyRotationInstanceLog,
    ProxyRotationLog,
    ProxyRotationSchedule,
)


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


class ProxyRotationScheduleSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()

    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else None

    def validate_interval_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError("Mínimo 1 minuto.")
        if value > 10080:  # 7 dias
            raise serializers.ValidationError("Máximo 10080 minutos (7 dias).")
        return value

    class Meta:
        model = ProxyRotationSchedule
        fields = [
            "id",
            "name",
            "is_active",
            "interval_minutes",
            "strategy",
            "last_run_at",
            "next_run_at",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_run_at",
            "next_run_at",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
