"""
Django admin para proxy (opcional).
"""
from django.contrib import admin

from .models import ProxyRotationInstanceLog, ProxyRotationLog, ProxyRotationSchedule


class ProxyRotationInstanceLogInline(admin.TabularInline):
    model = ProxyRotationInstanceLog
    extra = 0
    readonly_fields = ("instance_name", "proxy_host", "proxy_port", "success", "error_message", "created_at")


@admin.register(ProxyRotationLog)
class ProxyRotationLogAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "num_proxies", "num_instances", "num_updated", "triggered_by", "created_at")
    list_filter = ("status", "triggered_by")
    search_fields = ("error_message",)
    readonly_fields = (
        "started_at", "finished_at", "status", "num_proxies", "num_instances",
        "num_updated", "strategy", "error_message", "triggered_by", "created_by",
        "created_at",
    )
    inlines = [ProxyRotationInstanceLogInline]


@admin.register(ProxyRotationSchedule)
class ProxyRotationScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "is_active",
        "interval_minutes",
        "strategy",
        "next_run_at",
        "last_run_at",
        "created_at",
    )
    list_filter = ("is_active", "strategy")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at", "last_run_at")


@admin.register(ProxyRotationInstanceLog)
class ProxyRotationInstanceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "rotation_log", "instance_name", "success", "created_at")
    list_filter = ("success",)
    search_fields = ("instance_name",)
