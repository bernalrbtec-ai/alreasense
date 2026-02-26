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
    path('bia-admin/verify-key/', views.verify_bia_admin_key, name='bia-admin-verify-key'),
    path('bia-admin/test-summarize/', views.test_summarize, name='bia-admin-test-summarize'),
    path('gateway/test/', views.gateway_test, name='gateway-test'),
    path('gateway/test/callback/', views.gateway_test_callback, name='gateway-test-callback'),
    path('gateway/test/result/<uuid:job_id>/', views.gateway_test_result, name='gateway-test-result'),
    path('gateway/reply/', views.gateway_reply, name='gateway-reply'),
    path('secretary/profile/', views.secretary_profile, name='secretary-profile'),
    path('triage/history/', views.triage_history, name='triage-history'),
    path('gateway/audit/', views.gateway_audit_history, name='gateway-audit-history'),
    path('transcription/metrics/', views.transcription_metrics, name='transcription-metrics'),
    path('transcription/metrics/rebuild/', views.rebuild_transcription_metrics_endpoint, name='rebuild-transcription-metrics'),
    path('transcription/quality/<uuid:attachment_id>/', views.transcription_quality_feedback, name='transcription-quality-feedback'),
    path('transcription/debug/', views.debug_transcription_attachments, name='debug-transcription-attachments'),
    path('summaries/', views.conversation_summary_list, name='conversation-summary-list'),
    path('summaries/reprocess/', views.conversation_summary_reprocess, name='conversation-summary-reprocess'),
    path('summaries/<int:pk>/', views.conversation_summary_detail, name='conversation-summary-detail'),
]
