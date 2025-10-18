/**
 * Ícone de status de mensagem (✓, ✓✓, ✓✓ azul)
 */
import React from 'react';
import { Check, CheckCheck, Clock, AlertCircle } from 'lucide-react';

interface StatusIconProps {
  status: 'pending' | 'sent' | 'delivered' | 'seen' | 'failed';
  className?: string;
}

export function StatusIcon({ status, className = '' }: StatusIconProps) {
  switch (status) {
    case 'pending':
      return (
        <Clock 
          className={`w-3 h-3 text-gray-400 ${className}`}
          title="Enviando..."
        />
      );
    
    case 'sent':
      return (
        <Check 
          className={`w-3 h-3 text-gray-400 ${className}`}
          title="Enviada"
        />
      );
    
    case 'delivered':
      return (
        <CheckCheck 
          className={`w-3 h-3 text-gray-400 ${className}`}
          title="Entregue"
        />
      );
    
    case 'seen':
      return (
        <CheckCheck 
          className={`w-3 h-3 text-blue-500 ${className}`}
          title="Vista"
        />
      );
    
    case 'failed':
      return (
        <AlertCircle 
          className={`w-3 h-3 text-red-500 ${className}`}
          title="Falhou"
        />
      );
    
    default:
      return null;
  }
}

