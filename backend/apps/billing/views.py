from rest_framework import generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from .models import Plan, PaymentAccount, BillingEvent
from .serializers import PlanSerializer, PaymentAccountSerializer, BillingInfoSerializer
from .service import BillingService
from apps.common.permissions import IsTenantMember


class PlanViewSet(viewsets.ModelViewSet):
    """ViewSet for managing subscription plans."""
    
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        print(f"🔍 PlanViewSet action: {self.action}")
        print(f"🔍 User: {self.request.user.username}")
        print(f"🔍 Is superuser: {self.request.user.is_superuser}")
        print(f"🔍 Is staff: {self.request.user.is_staff}")
        
        # Temporarily allow all authenticated users to manage plans for testing
        print(f"🔍 Allowing authenticated user access for action: {self.action}")
        return [IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        print(f"🔍 Creating plan with data: {request.data}")
        try:
            response = super().create(request, *args, **kwargs)
            print(f"✅ Plan created successfully: {response.data}")
            return response
        except Exception as e:
            print(f"❌ Error creating plan: {str(e)}")
            raise
    
    def update(self, request, *args, **kwargs):
        print(f"🔍 Updating plan {kwargs.get('pk')} with data: {request.data}")
        print(f"🔍 Request method: {request.method}")
        print(f"🔍 Content type: {request.content_type}")
        print(f"🔍 User: {request.user.username}")
        
        try:
            # Get the instance first
            instance = self.get_object()
            print(f"🔍 Plan instance: {instance}")
            print(f"🔍 Current plan data: {PlanSerializer(instance).data}")
            
            # Validate the data
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            print(f"🔍 Serializer is valid: {serializer.is_valid()}")
            if not serializer.is_valid():
                print(f"❌ Serializer errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            response = super().update(request, *args, **kwargs)
            print(f"✅ Plan updated successfully: {response.data}")
            return response
        except Exception as e:
            print(f"❌ Error updating plan: {str(e)}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            raise


class PaymentAccountView(generics.RetrieveAPIView):
    """Get payment account information."""
    
    serializer_class = PaymentAccountSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_object(self):
        account, created = PaymentAccount.objects.get_or_create(
            tenant=self.request.user.tenant
        )
        return account


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def billing_info(request):
    """Get comprehensive billing information."""
    
    tenant = request.user.tenant
    
    # Get or create payment account
    account, created = PaymentAccount.objects.get_or_create(
        tenant=tenant
    )
    
    # Get plan limits
    plan_limits = tenant.plan_limits
    
    # Calculate next billing date
    if account.current_period_end:
        next_billing_date = account.current_period_end.date()
    else:
        next_billing_date = tenant.next_billing_date
    
    billing_info_data = {
        'current_plan': tenant.plan,
        'plan_limits': plan_limits,
        'next_billing_date': next_billing_date,
        'status': account.status,
        'has_payment_method': bool(account.stripe_customer_id),
        'current_period_end': account.current_period_end,
    }
    
    serializer = BillingInfoSerializer(billing_info_data)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
def create_checkout_session(request):
    """Create Stripe checkout session for plan upgrade."""
    
    plan = request.data.get('plan')
    if not plan:
        return Response(
            {'error': 'Plan is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if plan not in ['starter', 'pro', 'scale', 'enterprise']:
        return Response(
            {'error': 'Invalid plan'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        billing_service = BillingService()
        checkout_session = billing_service.create_checkout_session(
            tenant=request.user.tenant,
            plan=plan
        )
        
        return Response({
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to create checkout session: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
def create_portal_session(request):
    """Create Stripe customer portal session."""
    
    try:
        billing_service = BillingService()
        portal_session = billing_service.create_portal_session(
            tenant=request.user.tenant
        )
        
        return Response({
            'portal_url': portal_session.url
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to create portal session: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def billing_history(request):
    """Get billing history for the tenant."""
    
    # Get recent billing events
    events = BillingEvent.objects.filter(
        tenant=request.user.tenant
    ).order_by('-created_at')[:50]
    
    from .serializers import BillingEventSerializer
    serializer = BillingEventSerializer(events, many=True)
    
    return Response({
        'events': serializer.data,
        'total_events': events.count()
    })
