"""
✅ IMPROVEMENT: Centralized error handling with better logging and user feedback
"""
import logging
import traceback
from typing import Optional, Dict, Any
from django.http import JsonResponse
from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework.exceptions import APIException
from rest_framework import status

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Centralized error handler with structured logging
    """
    
    @staticmethod
    def handle_error(
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        log_traceback: bool = True
    ) -> JsonResponse:
        """
        Handle error with proper logging and user-friendly response
        
        Args:
            error: Exception that occurred
            context: Additional context for logging
            user_message: Custom message for user
            log_traceback: Whether to log full traceback
        
        Returns:
            JsonResponse with error details
        """
        context = context or {}
        
        # Determine error type and status code
        error_type = type(error).__name__
        
        if isinstance(error, ValidationError):
            status_code = status.HTTP_400_BAD_REQUEST
            default_message = "Dados inválidos"
        elif isinstance(error, PermissionDenied):
            status_code = status.HTTP_403_FORBIDDEN
            default_message = "Permissão negada"
        elif isinstance(error, APIException):
            status_code = error.status_code
            default_message = str(error.detail)
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            default_message = "Erro interno do servidor"
        
        # Log error
        log_data = {
            'error_type': error_type,
            'error_message': str(error),
            **context
        }
        
        if status_code >= 500:
            logger.error(f"❌ {error_type}: {error}", extra=log_data)
            if log_traceback:
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"⚠️ {error_type}: {error}", extra=log_data)
        
        # Prepare response
        response_data = {
            'success': False,
            'error': user_message or default_message,
            'error_type': error_type
        }
        
        # Add validation errors if present
        if isinstance(error, ValidationError):
            if hasattr(error, 'message_dict'):
                response_data['errors'] = error.message_dict
            elif hasattr(error, 'messages'):
                response_data['errors'] = error.messages
        
        return JsonResponse(response_data, status=status_code)
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str) -> JsonResponse:
        """
        Handle database-specific errors
        
        Args:
            error: Database exception
            operation: Operation that failed (e.g., "create", "update")
        
        Returns:
            JsonResponse with error details
        """
        error_message = str(error).lower()
        
        if 'unique constraint' in error_message or 'already exists' in error_message:
            return ErrorHandler.handle_error(
                error,
                context={'operation': operation},
                user_message="Este registro já existe no sistema"
            )
        elif 'foreign key' in error_message:
            return ErrorHandler.handle_error(
                error,
                context={'operation': operation},
                user_message="Operação inválida: referência não encontrada"
            )
        elif 'timeout' in error_message:
            return ErrorHandler.handle_error(
                error,
                context={'operation': operation},
                user_message="Operação demorou muito tempo. Tente novamente"
            )
        else:
            return ErrorHandler.handle_error(
                error,
                context={'operation': operation},
                user_message="Erro ao processar dados no banco"
            )
    
    @staticmethod
    def handle_external_api_error(error: Exception, service: str) -> JsonResponse:
        """
        Handle external API errors
        
        Args:
            error: API exception
            service: Service name (e.g., "Evolution API", "Stripe")
        
        Returns:
            JsonResponse with error details
        """
        return ErrorHandler.handle_error(
            error,
            context={'service': service},
            user_message=f"Erro ao comunicar com {service}. Tente novamente mais tarde"
        )


def safe_execute(
    func,
    *args,
    error_context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> tuple[bool, Any]:
    """
    Execute function safely with error handling
    
    Args:
        func: Function to execute
        *args: Positional arguments
        error_context: Context for error logging
        **kwargs: Keyword arguments
    
    Returns:
        (success: bool, result_or_error: Any)
    
    Example:
        success, result = safe_execute(
            send_message,
            campaign_id=campaign.id,
            error_context={'campaign': campaign.name}
        )
        if success:
            print(f"Message sent: {result}")
        else:
            print(f"Error: {result}")
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_context = error_context or {}
        logger.error(
            f"❌ Error in {func.__name__}: {str(e)}",
            extra=error_context
        )
        logger.error(traceback.format_exc())
        return False, e

