/**
 * ✅ IMPROVEMENT: Enhanced API error handling with better UX
 */

export interface ApiError {
  message: string;
  statusCode: number;
  field?: string;
  errors?: Record<string, string[]>;
}

export class ApiErrorHandler {
  /**
   * Extract user-friendly error message from API response
   */
  static extractMessage(error: any): string {
    // Network error
    if (!error.response) {
      if (error.message === 'Network Error') {
        return 'Sem conexão com o servidor. Verifique sua internet.';
      }
      return error.message || 'Erro desconhecido';
    }

    const { status, data } = error.response;

    // Handle different status codes
    switch (status) {
      case 400:
        return this.extractValidationMessage(data);
      case 401:
        return 'Sessão expirada. Por favor, faça login novamente.';
      case 403:
        return 'Você não tem permissão para realizar esta ação.';
      case 404:
        return 'Recurso não encontrado.';
      case 429:
        return 'Muitas requisições. Por favor, aguarde um momento.';
      case 500:
        return 'Erro interno do servidor. Nossa equipe foi notificada.';
      case 502:
      case 503:
      case 504:
        return 'Servidor temporariamente indisponível. Tente novamente em instantes.';
      default:
        return this.extractValidationMessage(data);
    }
  }

  /**
   * Extract validation error message from response data
   */
  private static extractValidationMessage(data: any): string {
    if (!data) {
      return 'Erro desconhecido';
    }

    // String response
    if (typeof data === 'string') {
      return data;
    }

    // Standard error fields
    if (data.detail) {
      return Array.isArray(data.detail) ? data.detail[0] : data.detail;
    }
    if (data.message) {
      return Array.isArray(data.message) ? data.message[0] : data.message;
    }
    if (data.error) {
      return Array.isArray(data.error) ? data.error[0] : data.error;
    }

    // Field-specific errors
    if (data.non_field_errors) {
      return Array.isArray(data.non_field_errors) 
        ? data.non_field_errors[0] 
        : data.non_field_errors;
    }

    // First field error
    const firstKey = Object.keys(data)[0];
    if (firstKey && data[firstKey]) {
      const value = data[firstKey];
      const message = Array.isArray(value) ? value[0] : value;
      
      // Format field name (snake_case to Title Case)
      const fieldName = firstKey
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      
      return `${fieldName}: ${message}`;
    }

    return 'Erro desconhecido';
  }

  /**
   * Parse full API error with all details
   */
  static parse(error: any): ApiError {
    const message = this.extractMessage(error);
    const statusCode = error.response?.status || 0;
    const data = error.response?.data;

    // Extract field-specific errors
    const errors: Record<string, string[]> = {};
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      for (const [field, value] of Object.entries(data)) {
        if (Array.isArray(value)) {
          errors[field] = value.map(String);
        } else if (typeof value === 'string') {
          errors[field] = [value];
        }
      }
    }

    return {
      message,
      statusCode,
      errors: Object.keys(errors).length > 0 ? errors : undefined,
    };
  }

  /**
   * Check if error is retryable
   */
  static isRetryable(error: any): boolean {
    const status = error.response?.status;
    
    // Network errors are retryable
    if (!error.response) {
      return true;
    }

    // Server errors are retryable
    if (status >= 500) {
      return true;
    }

    // Rate limit is retryable
    if (status === 429) {
      return true;
    }

    return false;
  }

  /**
   * Get suggested retry delay in milliseconds
   */
  static getRetryDelay(error: any, attempt: number): number {
    // Check for Retry-After header
    const retryAfter = error.response?.headers?.['retry-after'];
    if (retryAfter) {
      const seconds = parseInt(retryAfter, 10);
      if (!isNaN(seconds)) {
        return seconds * 1000;
      }
    }

    // Exponential backoff: 1s, 2s, 4s, 8s
    return Math.min(1000 * Math.pow(2, attempt), 8000);
  }

  /**
   * Log error for debugging (only in development)
   */
  static log(error: any, context?: string): void {
    if (process.env.NODE_ENV === 'development') {
      console.group(`❌ API Error${context ? `: ${context}` : ''}`);
      console.error('Error object:', error);
      console.error('Response data:', error.response?.data);
      console.error('Status:', error.response?.status);
      console.error('Parsed:', this.parse(error));
      console.groupEnd();
    }
  }
}

/**
 * Retry wrapper for API calls with exponential backoff
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number;
    onRetry?: (attempt: number, error: any) => void;
  } = {}
): Promise<T> {
  const { maxRetries = 3, onRetry } = options;
  let lastError: any;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      // Don't retry if not retryable
      if (!ApiErrorHandler.isRetryable(error)) {
        throw error;
      }

      // Don't retry on last attempt
      if (attempt === maxRetries - 1) {
        break;
      }

      // Call onRetry callback
      if (onRetry) {
        onRetry(attempt + 1, error);
      }

      // Wait before retry
      const delay = ApiErrorHandler.getRetryDelay(error, attempt);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}

