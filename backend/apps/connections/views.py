from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from .models import EvolutionConnection
from .serializers import EvolutionConnectionSerializer, EvolutionConnectionCreateSerializer
from apps.common.permissions import IsTenantMember


class EvolutionConnectionListCreateView(generics.ListCreateAPIView):
    """List and create Evolution connections."""
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_queryset(self):
        return EvolutionConnection.objects.filter(tenant=self.request.user.tenant)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EvolutionConnectionCreateSerializer
        return EvolutionConnectionSerializer
    
    def perform_create(self, serializer):
        # Tenant is set in serializer.create()
        connection = serializer.save()
        
        # TODO: Start WebSocket listener for this connection
        # This would be handled by the ingestion service


class EvolutionConnectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete an Evolution connection."""
    
    serializer_class = EvolutionConnectionSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_queryset(self):
        return EvolutionConnection.objects.filter(tenant=self.request.user.tenant)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
def test_connection(request, pk):
    """Test Evolution API connection."""
    
    try:
        connection = EvolutionConnection.objects.get(
            pk=pk, 
            tenant=request.user.tenant
        )
    except EvolutionConnection.DoesNotExist:
        return Response(
            {'error': 'Connection not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # TODO: Implement connection test
    # This would make a test request to the Evolution API
    
    return Response({
        'status': 'success',
        'message': 'Connection test not implemented yet'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
def toggle_connection(request, pk):
    """Toggle connection active status."""
    
    try:
        connection = EvolutionConnection.objects.get(
            pk=pk, 
            tenant=request.user.tenant
        )
    except EvolutionConnection.DoesNotExist:
        return Response(
            {'error': 'Connection not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    connection.is_active = not connection.is_active
    connection.save()
    
    return Response({
        'status': 'success',
        'is_active': connection.is_active,
        'message': f'Connection {"activated" if connection.is_active else "deactivated"}'
    })
