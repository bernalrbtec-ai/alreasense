"""
Billing service for Stripe integration.
"""

import stripe
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import PaymentAccount, BillingEvent
from apps.tenancy.models import Tenant

# Configure Stripe
if hasattr(settings, 'STRIPE_SECRET_KEY') and settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


class BillingService:
    """Service for handling Stripe billing operations."""
    
    def __init__(self):
        self.stripe = stripe
    
    def create_customer(self, tenant: Tenant):
        """Create or get Stripe customer for tenant."""
        
        # Check if customer already exists
        account, created = PaymentAccount.objects.get_or_create(
            tenant=tenant
        )
        
        if account.stripe_customer_id:
            try:
                customer = self.stripe.Customer.retrieve(account.stripe_customer_id)
                return customer
            except stripe.error.InvalidRequestError:
                # Customer doesn't exist, create new one
                pass
        
        # Create new customer
        customer = self.stripe.Customer.create(
            email=tenant.users.first().email if tenant.users.exists() else None,
            name=tenant.name,
            metadata={
                'tenant_id': str(tenant.id),
                'plan': tenant.plan
            }
        )
        
        # Update payment account
        account.stripe_customer_id = customer.id
        account.save()
        
        return customer
    
    def create_checkout_session(self, tenant: Tenant, plan: str):
        """Create Stripe checkout session for plan upgrade."""
        
        customer = self.create_customer(tenant)
        
        # Get plan price
        price_id = self._get_price_id(plan)
        
        # Create checkout session
        session = self.stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{settings.FRONTEND_URL}/billing/cancel',
            metadata={
                'tenant_id': str(tenant.id),
                'plan': plan
            }
        )
        
        return session
    
    def create_portal_session(self, tenant: Tenant):
        """Create Stripe customer portal session."""
        
        account = PaymentAccount.objects.get(tenant=tenant)
        
        session = self.stripe.billing_portal.Session.create(
            customer=account.stripe_customer_id,
            return_url=f'{settings.FRONTEND_URL}/billing'
        )
        
        return session
    
    def handle_webhook(self, event: stripe.Event) -> bool:
        """Handle Stripe webhook events."""
        
        try:
            # Store event
            billing_event = BillingEvent.objects.create(
                tenant_id=event.metadata.get('tenant_id'),
                event_type=event.type,
                stripe_event_id=event.id,
                data=event.to_dict()
            )
            
            # Process event
            if event.type == 'invoice.paid':
                self._handle_invoice_paid(event)
            elif event.type == 'invoice.payment_failed':
                self._handle_payment_failed(event)
            elif event.type == 'customer.subscription.updated':
                self._handle_subscription_updated(event)
            elif event.type == 'customer.subscription.deleted':
                self._handle_subscription_deleted(event)
            
            billing_event.processed = True
            billing_event.save()
            
            return True
            
        except Exception as e:
            # Log error but don't fail webhook
            print(f"Error processing webhook {event.id}: {e}")
            return False
    
    def _get_price_id(self, plan: str) -> str:
        """Get Stripe price ID for plan."""
        
        price_ids = {
            'starter': 'price_starter_monthly',  # Replace with actual price IDs
            'pro': 'price_pro_monthly',
            'scale': 'price_scale_monthly',
            'enterprise': 'price_enterprise_monthly',
        }
        
        return price_ids.get(plan, price_ids['starter'])
    
    def _handle_invoice_paid(self, event: stripe.Event):
        """Handle successful invoice payment."""
        
        invoice = event.data.object
        customer_id = invoice.customer
        
        try:
            account = PaymentAccount.objects.get(stripe_customer_id=customer_id)
            account.status = 'active'
            account.save()
            
            # Update tenant status
            tenant = account.tenant
            tenant.status = 'active'
            tenant.next_billing_date = timezone.now().date() + timedelta(days=30)
            tenant.save()
            
        except PaymentAccount.DoesNotExist:
            pass
    
    def _handle_payment_failed(self, event: stripe.Event):
        """Handle failed invoice payment."""
        
        invoice = event.data.object
        customer_id = invoice.customer
        
        try:
            account = PaymentAccount.objects.get(stripe_customer_id=customer_id)
            account.status = 'expired'
            account.save()
            
            # Suspend tenant
            tenant = account.tenant
            tenant.status = 'suspended'
            tenant.save()
            
        except PaymentAccount.DoesNotExist:
            pass
    
    def _handle_subscription_updated(self, event: stripe.Event):
        """Handle subscription update."""
        
        subscription = event.data.object
        customer_id = subscription.customer
        
        try:
            account = PaymentAccount.objects.get(stripe_customer_id=customer_id)
            account.stripe_subscription_id = subscription.id
            account.current_period_start = timezone.datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            )
            account.current_period_end = timezone.datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )
            account.save()
            
        except PaymentAccount.DoesNotExist:
            pass
    
    def _handle_subscription_deleted(self, event: stripe.Event):
        """Handle subscription cancellation."""
        
        subscription = event.data.object
        customer_id = subscription.customer
        
        try:
            account = PaymentAccount.objects.get(stripe_customer_id=customer_id)
            account.status = 'cancelled'
            account.save()
            
            # Suspend tenant
            tenant = account.tenant
            tenant.status = 'suspended'
            tenant.save()
            
        except PaymentAccount.DoesNotExist:
            pass
