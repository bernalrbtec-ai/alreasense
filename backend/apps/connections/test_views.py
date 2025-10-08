from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(require_http_methods(["GET", "POST"]), name='dispatch')
class TestView(View):
    """Simple test endpoint to verify backend is working."""
    
    def get(self, request):
        return JsonResponse({
            'status': 'success',
            'message': 'Backend is working!',
            'cors_test': 'CORS headers should be present'
        })
    
    def post(self, request):
        return JsonResponse({
            'status': 'success',
            'message': 'POST request received',
            'method': 'POST'
        })
