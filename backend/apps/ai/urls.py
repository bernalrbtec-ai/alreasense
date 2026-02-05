from django.urls import path
from . import views

urlpatterns = [
    path('analyze/<int:message_id>/', views.analyze_message, name='analyze-message'),
    path('analyze/batch/', views.analyze_batch, name='analyze-batch'),
    path('stats/', views.ai_stats, name='ai-stats'),
    path('settings/', views.ai_settings, name='ai-settings'),
    path('transcribe/test/', views.transcribe_test, name='transcribe-test'),
    path('models/', views.models_list, name='ai-models'),
    path('webhook/test/', views.webhook_test, name='webhook-test'),
    path('triage/test/', views.triage_test, name='triage-test'),
    path('gateway/test/', views.gateway_test, name='gateway-test'),
    path('triage/history/', views.triage_history, name='triage-history'),
    path('gateway/audit/', views.gateway_audit_history, name='gateway-audit-history'),
]
