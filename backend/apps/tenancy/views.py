from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import Tenant
from .serializers import TenantSerializer, TenantMetricsSerializer
from apps.connections.models import EvolutionConnection
from apps.chat_messages.models import Message
from apps.experiments.models import Inference


class TenantListView(generics.ListAPIView):
    """List all tenants (admin only)."""
    
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class TenantDetailView(generics.RetrieveAPIView):
    """Get tenant details."""
    
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user.tenant


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_metrics(request, tenant_id):
    """Get tenant metrics and KPIs."""
    
    # Verify user has access to this tenant
    if str(request.user.tenant.id) != str(tenant_id):
        return Response(
            {'error': 'Access denied'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    tenant = request.user.tenant
    
    # Calculate metrics
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    # Message metrics
    messages = Message.objects.filter(tenant=tenant)
    total_messages = messages.count()
    messages_today = messages.filter(created_at__date=today).count()
    
    # Sentiment and satisfaction averages
    avg_sentiment = messages.filter(sentiment__isnull=False).aggregate(
        avg=Avg('sentiment')
    )['avg'] or 0.0
    
    avg_satisfaction = messages.filter(satisfaction__isnull=False).aggregate(
        avg=Avg('satisfaction')
    )['avg'] or 0.0
    
    # Positive messages percentage
    positive_messages = messages.filter(sentiment__gt=0.1).count()
    positive_messages_pct = (positive_messages / total_messages * 100) if total_messages > 0 else 0.0
    
    # Active connections
    active_connections = EvolutionConnection.objects.filter(
        tenant=tenant, is_active=True
    ).count()
    
    # Average latency from inferences
    avg_latency = Inference.objects.filter(
        tenant=tenant, latency_ms__isnull=False
    ).aggregate(avg=Avg('latency_ms'))['avg'] or 0.0
    
    metrics_data = {
        'total_messages': total_messages,
        'avg_sentiment': round(avg_sentiment, 2),
        'avg_satisfaction': round(avg_satisfaction, 2),
        'positive_messages_pct': round(positive_messages_pct, 2),
        'messages_today': messages_today,
        'active_connections': active_connections,
        'avg_latency_ms': round(avg_latency, 2),
    }
    
    serializer = TenantMetricsSerializer(metrics_data)
    return Response(serializer.data)
