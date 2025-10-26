"""
✅ IMPROVEMENT: Enhanced RabbitMQ configuration with DLQ, retry logic, and monitoring
"""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class QueueConfig:
    """Configuration for a RabbitMQ queue"""
    name: str
    durable: bool = True
    arguments: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.arguments is None:
            self.arguments = {}


class RabbitMQConfig:
    """
    Centralized RabbitMQ configuration with best practices
    """
    
    # ✅ IMPROVEMENT: Dead Letter Queue configuration
    DLQ_EXCHANGE = 'campaigns.dlx'
    DLQ_QUEUE = 'campaigns.dlq'
    
    # ✅ IMPROVEMENT: Retry configuration
    RETRY_EXCHANGE = 'campaigns.retry'
    RETRY_DELAYS = [5000, 30000, 300000]  # 5s, 30s, 5min
    
    # ✅ IMPROVEMENT: TTL configuration (messages expire after 24h)
    MESSAGE_TTL = 86400000  # 24 hours in milliseconds
    
    # ✅ IMPROVEMENT: Queue configurations with DLQ
    @classmethod
    def get_queue_config(cls, queue_name: str) -> QueueConfig:
        """
        Get queue configuration with DLQ setup
        
        Args:
            queue_name: Name of the queue
        
        Returns:
            QueueConfig with DLQ arguments
        """
        return QueueConfig(
            name=queue_name,
            durable=True,
            arguments={
                # Dead Letter Exchange
                'x-dead-letter-exchange': cls.DLQ_EXCHANGE,
                'x-dead-letter-routing-key': queue_name,
                # Message TTL
                'x-message-ttl': cls.MESSAGE_TTL,
                # Queue max length (prevent memory issues)
                'x-max-length': 100000,
                # Max priority
                'x-max-priority': 10,
            }
        )
    
    @classmethod
    def get_retry_queue_config(cls, retry_attempt: int) -> QueueConfig:
        """
        Get retry queue configuration with delayed redelivery
        
        Args:
            retry_attempt: Retry attempt number (0-indexed)
        
        Returns:
            QueueConfig for retry queue
        """
        delay = cls.RETRY_DELAYS[min(retry_attempt, len(cls.RETRY_DELAYS) - 1)]
        queue_name = f"campaigns.retry.{retry_attempt}"
        
        return QueueConfig(
            name=queue_name,
            durable=True,
            arguments={
                # Delayed redelivery
                'x-message-ttl': delay,
                'x-dead-letter-exchange': 'campaigns',
                'x-dead-letter-routing-key': 'campaign.process',
            }
        )
    
    @classmethod
    def get_dlq_config(cls) -> QueueConfig:
        """
        Get Dead Letter Queue configuration
        
        Returns:
            QueueConfig for DLQ
        """
        return QueueConfig(
            name=cls.DLQ_QUEUE,
            durable=True,
            arguments={
                # Keep messages for 7 days for analysis
                'x-message-ttl': 604800000,  # 7 days
                # Limit queue size
                'x-max-length': 50000,
            }
        )


class RetryPolicy:
    """
    Retry policy for failed operations
    """
    
    MAX_RETRIES = 3
    BACKOFF_MULTIPLIER = 2
    INITIAL_DELAY = 5  # seconds
    
    @classmethod
    def should_retry(cls, attempt: int, error: Exception) -> bool:
        """
        Determine if operation should be retried
        
        Args:
            attempt: Current attempt number (0-indexed)
            error: Error that occurred
        
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= cls.MAX_RETRIES:
            return False
        
        # Don't retry on these errors
        non_retryable_errors = [
            'ValidationError',
            'PermissionDenied',
            'AuthenticationFailed',
            'BadRequest',
        ]
        
        error_name = type(error).__name__
        if error_name in non_retryable_errors:
            return False
        
        return True
    
    @classmethod
    def get_delay(cls, attempt: int) -> int:
        """
        Get delay before next retry (exponential backoff)
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        return cls.INITIAL_DELAY * (cls.BACKOFF_MULTIPLIER ** attempt)


class MessagePriority:
    """
    Message priority levels
    """
    CRITICAL = 10
    HIGH = 7
    NORMAL = 5
    LOW = 3
    BULK = 1

