from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""
    
    has_analysis = serializers.ReadOnlyField()
    is_positive = serializers.ReadOnlyField()
    is_satisfied = serializers.ReadOnlyField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'chat_id', 'sender', 'text', 'created_at',
            'sentiment', 'emotion', 'satisfaction', 'tone', 'summary',
            'has_analysis', 'is_positive', 'is_satisfied'
        ]
        read_only_fields = ['id', 'created_at']


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating messages."""
    
    class Meta:
        model = Message
        fields = ['connection', 'chat_id', 'sender', 'text', 'created_at']
    
    def create(self, validated_data):
        # Set tenant from request user
        validated_data['tenant'] = self.context['request'].user.tenant
        return super().create(validated_data)


class SemanticSearchSerializer(serializers.Serializer):
    """Serializer for semantic search requests."""
    
    query = serializers.CharField(max_length=500)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)
    similarity_threshold = serializers.FloatField(default=0.7, min_value=0.0, max_value=1.0)


class SemanticSearchResultSerializer(serializers.Serializer):
    """Serializer for semantic search results."""
    
    id = serializers.IntegerField()
    text = serializers.CharField()
    sentiment = serializers.FloatField(allow_null=True)
    satisfaction = serializers.IntegerField(allow_null=True)
    similarity_score = serializers.FloatField()
    created_at = serializers.DateTimeField()
