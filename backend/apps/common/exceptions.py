"""
Custom exception handlers for the application.
"""
from rest_framework.views import exception_handler
from django.http import JsonResponse
from django.urls import resolve, Resolver404


def custom_exception_handler(exc, context):
    """
    Custom exception handler that allows webhook endpoints to work without authentication.
    """
    request = context.get('request')
    
    # Allow webhook endpoints to work without authentication
    if request and request.path.startswith('/webhooks/'):
        # For webhooks, return a simple response instead of authentication error
        if hasattr(exc, 'status_code') and exc.status_code == 401:
            return JsonResponse({'error': 'Unauthorized origin'}, status=403)
    
    # Use default exception handler for all other cases
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'error': 'An error occurred',
            'status_code': response.status_code,
        }
        
        # Add more details if available
        if hasattr(exc, 'detail'):
            custom_response_data['detail'] = exc.detail
        elif hasattr(exc, 'args') and exc.args:
            custom_response_data['detail'] = str(exc.args[0])
        
        response.data = custom_response_data
    
    return response
