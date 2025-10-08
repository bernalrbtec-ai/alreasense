from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .tasks import analyze_message_async
from apps.chat_messages.models import Message
from apps.common.permissions import IsTenantMember, IsAdminUser


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def analyze_message(request, message_id):
    """Force analysis of a specific message."""
    
    try:
        message = Message.objects.get(
            id=message_id,
            tenant=request.user.tenant
        )
    except Message.DoesNotExist:
        return Response(
            {'error': 'Message not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Queue analysis task
    analyze_message_async.delay(
        tenant_id=str(request.user.tenant.id),
        message_id=message.id,
        is_shadow=False,
        run_id="manual"
    )
    
    return Response({
        'status': 'success',
        'message': 'Analysis queued',
        'message_id': message.id
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def analyze_batch(request):
    """Analyze multiple messages."""
    
    message_ids = request.data.get('message_ids', [])
    if not message_ids:
        return Response(
            {'error': 'No message IDs provided'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify all messages belong to tenant
    messages = Message.objects.filter(
        id__in=message_ids,
        tenant=request.user.tenant
    )
    
    if len(messages) != len(message_ids):
        return Response(
            {'error': 'Some messages not found or access denied'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Queue analysis tasks
    queued_count = 0
    for message in messages:
        analyze_message_async.delay(
            tenant_id=str(request.user.tenant.id),
            message_id=message.id,
            is_shadow=False,
            run_id="batch"
        )
        queued_count += 1
    
    return Response({
        'status': 'success',
        'message': f'Queued {queued_count} messages for analysis',
        'queued_count': queued_count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def ai_stats(request):
    """Get AI analysis statistics."""
    
    from apps.experiments.models import Inference
    from django.db.models import Avg, Count
    
    tenant = request.user.tenant
    
    # Get inference stats
    inferences = Inference.objects.filter(tenant=tenant)
    
    stats = {
        'total_inferences': inferences.count(),
        'avg_latency_ms': inferences.aggregate(avg=Avg('latency_ms'))['avg'] or 0,
        'models_used': list(inferences.values_list('model_name', flat=True).distinct()),
        'prompt_versions': list(inferences.values_list('prompt_version', flat=True).distinct()),
        'shadow_inferences': inferences.filter(is_shadow=True).count(),
        'champion_inferences': inferences.filter(is_shadow=False).count(),
    }
    
    # Recent performance
    recent_inferences = inferences.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    )
    
    stats['recent_avg_latency_ms'] = recent_inferences.aggregate(
        avg=Avg('latency_ms')
    )['avg'] or 0
    
    stats['recent_inference_count'] = recent_inferences.count()
    
    return Response(stats)
