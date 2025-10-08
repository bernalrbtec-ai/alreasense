from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Message
from .serializers import (
    MessageSerializer, 
    MessageCreateSerializer,
    SemanticSearchSerializer,
    SemanticSearchResultSerializer
)
from .dao import semantic_search, get_embedding_stats
from apps.common.permissions import IsTenantMember
from apps.ai.embeddings import embed_text


class MessageListCreateView(generics.ListCreateAPIView):
    """List and create messages."""
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['chat_id', 'sentiment', 'emotion', 'satisfaction']
    search_fields = ['text', 'sender']
    ordering_fields = ['created_at', 'sentiment', 'satisfaction']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Message.objects.filter(tenant=self.request.user.tenant)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MessageCreateSerializer
        return MessageSerializer
    
    def perform_create(self, serializer):
        # Tenant is set in serializer.create()
        message = serializer.save()
        
        # TODO: Trigger AI analysis via Celery task
        # analyze_message_async.delay(str(message.tenant.id), message.id)


class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete a message."""
    
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_queryset(self):
        return Message.objects.filter(tenant=self.request.user.tenant)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
def semantic_search_view(request):
    """Perform semantic search on messages."""
    
    serializer = SemanticSearchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    query = serializer.validated_data['query']
    limit = serializer.validated_data['limit']
    similarity_threshold = serializer.validated_data['similarity_threshold']
    
    try:
        # Generate embedding for the query
        query_embedding = embed_text(query)
        
        # Perform semantic search
        results = semantic_search(
            tenant_id=str(request.user.tenant.id),
            query_embedding=query_embedding,
            limit=limit,
            similarity_threshold=similarity_threshold
        )
        
        # Format results
        formatted_results = []
        for result in results:
            message_id, text, sentiment, satisfaction, similarity_score = result
            
            # Get the full message object for additional fields
            try:
                message = Message.objects.get(id=message_id)
                formatted_results.append({
                    'id': message_id,
                    'text': text,
                    'sentiment': sentiment,
                    'satisfaction': satisfaction,
                    'similarity_score': round(similarity_score, 4),
                    'created_at': message.created_at,
                    'chat_id': message.chat_id,
                    'sender': message.sender,
                    'emotion': message.emotion,
                    'tone': message.tone,
                    'summary': message.summary,
                })
            except Message.DoesNotExist:
                continue
        
        return Response({
            'query': query,
            'results': formatted_results,
            'total_results': len(formatted_results)
        })
        
    except Exception as e:
        return Response(
            {'error': f'Semantic search failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def message_stats(request):
    """Get message statistics for the tenant."""
    
    tenant = request.user.tenant
    messages = Message.objects.filter(tenant=tenant)
    
    # Basic stats
    total_messages = messages.count()
    analyzed_messages = messages.filter(sentiment__isnull=False).count()
    
    # Sentiment stats
    avg_sentiment = messages.filter(sentiment__isnull=False).aggregate(
        avg=models.Avg('sentiment')
    )['avg'] or 0.0
    
    positive_messages = messages.filter(sentiment__gt=0.1).count()
    negative_messages = messages.filter(sentiment__lt=-0.1).count()
    
    # Satisfaction stats
    avg_satisfaction = messages.filter(satisfaction__isnull=False).aggregate(
        avg=models.Avg('satisfaction')
    )['avg'] or 0.0
    
    satisfied_messages = messages.filter(satisfaction__gte=70).count()
    
    # Embedding stats
    embedding_stats = get_embedding_stats(str(tenant.id))
    
    return Response({
        'total_messages': total_messages,
        'analyzed_messages': analyzed_messages,
        'analysis_coverage': (analyzed_messages / total_messages * 100) if total_messages > 0 else 0,
        'avg_sentiment': round(avg_sentiment, 2),
        'positive_messages': positive_messages,
        'negative_messages': negative_messages,
        'avg_satisfaction': round(avg_satisfaction, 2),
        'satisfied_messages': satisfied_messages,
        'embedding_stats': embedding_stats,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def chat_messages(request, chat_id):
    """Get all messages for a specific chat."""
    
    messages = Message.objects.filter(
        tenant=request.user.tenant,
        chat_id=chat_id
    ).order_by('created_at')
    
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)
