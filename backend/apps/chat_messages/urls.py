from django.urls import path
from . import views

urlpatterns = [
    path('', views.MessageListCreateView.as_view(), name='message-list'),
    path('<int:pk>/', views.MessageDetailView.as_view(), name='message-detail'),
    path('semantic-search/', views.semantic_search_view, name='semantic-search'),
    path('stats/', views.message_stats, name='message-stats'),
    path('chat/<str:chat_id>/', views.chat_messages, name='chat-messages'),
]
