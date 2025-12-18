"""
RabbitMQ integration para sistema de Billing
"""
from .billing_publisher import BillingQueuePublisher
from .billing_consumer import BillingQueueConsumer, get_billing_consumer

__all__ = [
    'BillingQueuePublisher',
    'BillingQueueConsumer',
    'get_billing_consumer',
]


