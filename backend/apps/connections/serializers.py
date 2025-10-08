from rest_framework import serializers
from .models import EvolutionConnection


class EvolutionConnectionSerializer(serializers.ModelSerializer):
    """Serializer for EvolutionConnection model."""
    
    status = serializers.ReadOnlyField()
    
    class Meta:
        model = EvolutionConnection
        fields = [
            'id', 'name', 'evo_ws_url', 'is_active', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        # Set tenant from request user
        validated_data['tenant'] = self.context['request'].user.tenant
        return super().create(validated_data)


class EvolutionConnectionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating EvolutionConnection."""
    
    evo_token = serializers.CharField(write_only=True)
    
    class Meta:
        model = EvolutionConnection
        fields = ['name', 'evo_ws_url', 'evo_token', 'is_active']
    
    def create(self, validated_data):
        # Set tenant from request user
        validated_data['tenant'] = self.context['request'].user.tenant
        return super().create(validated_data)
