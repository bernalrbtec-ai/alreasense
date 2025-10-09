from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Avg, Count
from django.utils import timezone

from .models import PromptTemplate, Inference, ExperimentRun
from .serializers import (
    PromptTemplateSerializer, 
    PromptTemplateCreateSerializer,
    InferenceSerializer,
    ExperimentRunSerializer,
    ExperimentRunCreateSerializer,
    ReplayRequestSerializer
)
from .tasks import replay_window
from apps.common.permissions import IsTenantMember, IsAdminUser
from apps.billing.decorators import require_product


@require_product('sense')
class PromptTemplateListCreateView(generics.ListCreateAPIView):
    """List and create prompt templates."""
    
    permission_classes = [IsAuthenticated, IsTenantMember, IsAdminUser]
    
    def get_queryset(self):
        return PromptTemplate.objects.all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PromptTemplateCreateSerializer
        return PromptTemplateSerializer


@require_product('sense')
class PromptTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete a prompt template."""
    
    serializer_class = PromptTemplateSerializer
    permission_classes = [IsAuthenticated, IsTenantMember, IsAdminUser]
    
    def get_queryset(self):
        return PromptTemplate.objects.all()


@require_product('sense')
class InferenceListView(generics.ListAPIView):
    """List inferences for the tenant."""
    
    serializer_class = InferenceSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_queryset(self):
        return Inference.objects.filter(tenant=self.request.user.tenant)


class ExperimentRunListCreateView(generics.ListCreateAPIView):
    """List and create experiment runs."""
    
    permission_classes = [IsAuthenticated, IsTenantMember, IsAdminUser]
    
    def get_queryset(self):
        return ExperimentRun.objects.filter(tenant=self.request.user.tenant)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ExperimentRunCreateSerializer
        return ExperimentRunSerializer


class ExperimentRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete an experiment run."""
    
    serializer_class = ExperimentRunSerializer
    permission_classes = [IsAuthenticated, IsTenantMember, IsAdminUser]
    
    def get_queryset(self):
        return ExperimentRun.objects.filter(tenant=self.request.user.tenant)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def start_replay_experiment(request):
    """Start a replay experiment."""
    
    serializer = ReplayRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    # Create experiment run
    experiment_run = ExperimentRun.objects.create(
        tenant=request.user.tenant,
        name=data.get('name', f'Replay {data["prompt_version"]}'),
        description=data.get('description', ''),
        prompt_version=data['prompt_version'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        status='running'
    )
    
    # Count total messages in time window
    from apps.chat_messages.models import Message
    total_messages = Message.objects.filter(
        tenant=request.user.tenant,
        created_at__range=[data['start_date'], data['end_date']]
    ).count()
    
    experiment_run.total_messages = total_messages
    experiment_run.save()
    
    # Start replay task
    replay_window.delay(
        tenant_id=str(request.user.tenant.id),
        start_iso=data['start_date'].isoformat(),
        end_iso=data['end_date'].isoformat(),
        prompt_version=data['prompt_version'],
        run_id=experiment_run.run_id
    )
    
    return Response({
        'status': 'success',
        'message': 'Replay experiment started',
        'experiment_run': ExperimentRunSerializer(experiment_run).data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def experiment_comparison(request, run_id1, run_id2):
    """Compare two experiment runs."""
    
    # Get experiment runs
    try:
        run1 = ExperimentRun.objects.get(
            run_id=run_id1, 
            tenant=request.user.tenant
        )
        run2 = ExperimentRun.objects.get(
            run_id=run_id2, 
            tenant=request.user.tenant
        )
    except ExperimentRun.DoesNotExist:
        return Response(
            {'error': 'Experiment run not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get inference statistics for both runs
    inferences1 = Inference.objects.filter(run_id=run_id1, is_shadow=True)
    inferences2 = Inference.objects.filter(run_id=run_id2, is_shadow=True)
    
    stats1 = {
        'run_id': run_id1,
        'prompt_version': run1.prompt_version,
        'total_inferences': inferences1.count(),
        'avg_sentiment': inferences1.aggregate(avg=Avg('sentiment'))['avg'] or 0,
        'avg_satisfaction': inferences1.aggregate(avg=Avg('satisfaction'))['avg'] or 0,
        'avg_latency_ms': inferences1.aggregate(avg=Avg('latency_ms'))['avg'] or 0,
    }
    
    stats2 = {
        'run_id': run_id2,
        'prompt_version': run2.prompt_version,
        'total_inferences': inferences2.count(),
        'avg_sentiment': inferences2.aggregate(avg=Avg('sentiment'))['avg'] or 0,
        'avg_satisfaction': inferences2.aggregate(avg=Avg('satisfaction'))['avg'] or 0,
        'avg_latency_ms': inferences2.aggregate(avg=Avg('latency_ms'))['avg'] or 0,
    }
    
    return Response({
        'run1': stats1,
        'run2': stats2,
        'comparison': {
            'sentiment_diff': stats2['avg_sentiment'] - stats1['avg_sentiment'],
            'satisfaction_diff': stats2['avg_satisfaction'] - stats1['avg_satisfaction'],
            'latency_diff': stats2['avg_latency_ms'] - stats1['avg_latency_ms'],
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def experiment_stats(request):
    """Get experiment statistics for the tenant."""
    
    tenant = request.user.tenant
    
    # Get recent experiment runs
    recent_runs = ExperimentRun.objects.filter(
        tenant=tenant,
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    )
    
    # Get inference statistics
    inferences = Inference.objects.filter(tenant=tenant)
    
    stats = {
        'total_experiments': recent_runs.count(),
        'active_experiments': recent_runs.filter(status='running').count(),
        'completed_experiments': recent_runs.filter(status='completed').count(),
        'total_inferences': inferences.count(),
        'shadow_inferences': inferences.filter(is_shadow=True).count(),
        'champion_inferences': inferences.filter(is_shadow=False).count(),
        'avg_latency_ms': inferences.aggregate(avg=Avg('latency_ms'))['avg'] or 0,
        'prompt_versions_used': list(inferences.values_list('prompt_version', flat=True).distinct()),
    }
    
    return Response(stats)
