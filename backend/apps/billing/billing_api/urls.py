"""
URLs para Billing API
"""
from django.urls import path
from . import views
from . import admin_views

app_name = 'billing_api'

urlpatterns = [
    # ========== ENDPOINTS PÚBLICOS (com API Key) ==========
    
    # Endpoint 1: Envia cobrança atrasada
    path('send/overdue', views.SendOverdueView.as_view(), name='send-overdue'),
    
    # Endpoint 2: Envia cobrança a vencer
    path('send/upcoming', views.SendUpcomingView.as_view(), name='send-upcoming'),
    
    # Endpoint 3: Envia notificação/aviso
    path('send/notification', views.SendNotificationView.as_view(), name='send-notification'),
    
    # Endpoint 4: Consulta status da fila
    path('queue/<uuid:queue_id>/status', views.QueueStatusView.as_view(), name='queue-status'),
    
    # Endpoint 5: Lista contatos de uma campanha
    path('campaign/<uuid:campaign_id>/contacts', views.CampaignContactsView.as_view(), name='campaign-contacts'),
    
    # ========== ENDPOINTS ADMIN ==========
    
    # API Keys (admin)
    path('api-keys/', admin_views.BillingAPIKeysListView.as_view(), name='api-keys-list'),
    path('api-keys/', admin_views.BillingAPIKeyCreateView.as_view(), name='api-keys-create'),
    path('api-keys/<uuid:key_id>/', admin_views.BillingAPIKeyDeleteView.as_view(), name='api-keys-delete'),
    
    # Templates (admin)
    path('templates/', admin_views.BillingTemplatesListView.as_view(), name='templates-list'),
    path('templates/', admin_views.BillingTemplateCreateView.as_view(), name='templates-create'),
    path('templates/<uuid:template_id>/', admin_views.BillingTemplateUpdateView.as_view(), name='templates-update'),
    path('templates/<uuid:template_id>/', admin_views.BillingTemplateDeleteView.as_view(), name='templates-delete'),
    
    # Campanhas (admin)
    path('campaigns/', admin_views.BillingCampaignsListView.as_view(), name='campaigns-list'),
    
    # Estatísticas (admin)
    path('stats/', admin_views.BillingStatsView.as_view(), name='stats'),
]

