from django.urls import path
from . import views

urlpatterns = [
    path('analyze/<int:message_id>/', views.analyze_message, name='analyze-message'),
    path('analyze/batch/', views.analyze_batch, name='analyze-batch'),
    path('stats/', views.ai_stats, name='ai-stats'),
]
