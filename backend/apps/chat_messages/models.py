from django.db import models
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection


class Message(models.Model):
    """Message model with AI analysis results and pgvector embedding."""
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    connection = models.ForeignKey(
        'connections.EvolutionConnection', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    chat_id = models.CharField(max_length=128, db_index=True)
    sender = models.CharField(max_length=64, default='unknown')  # hash do número/ID
    text = models.TextField()
    created_at = models.DateTimeField(db_index=True)
    
    # AI Analysis Results
    sentiment = models.FloatField(null=True, blank=True)  # -1..1
    emotion = models.CharField(max_length=40, null=True, blank=True)
    satisfaction = models.IntegerField(null=True, blank=True)  # 0..100
    tone = models.CharField(max_length=40, null=True, blank=True)
    summary = models.CharField(max_length=200, null=True, blank=True)
    
    # pgvector embedding (stored as binary, converted via DAO)
    embedding = models.BinaryField(null=True, blank=True)
    
    class Meta:
        db_table = 'messages_message'
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['chat_id']),
            models.Index(fields=['text']),  # Índice simples para busca
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.chat_id}: {self.text[:50]}..."
    
    @property
    def is_positive(self):
        """Check if message has positive sentiment."""
        return self.sentiment is not None and self.sentiment > 0.1
    
    @property
    def is_satisfied(self):
        """Check if message indicates satisfaction."""
        return self.satisfaction is not None and self.satisfaction >= 70
    
    @property
    def has_analysis(self):
        """Check if message has been analyzed by AI."""
        return self.sentiment is not None
