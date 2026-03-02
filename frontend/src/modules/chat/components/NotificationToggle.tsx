/**
 * NotificationToggle - Botão para ativar/desativar notificações de desktop
 * 
 * - Mostra status atual (ativado/desativado)
 * - Ao clicar, pede permissão se necessário
 * - Feedback visual do estado
 */

import React from 'react';
import { Bell, BellOff } from 'lucide-react';
import { useDesktopNotifications } from '@/hooks/useDesktopNotifications';
import { toast } from 'sonner';

export function NotificationToggle() {
  const { isEnabled, isSupported, toggleNotifications } = useDesktopNotifications();

  if (!isSupported) {
    return null; // Não mostrar se o navegador não suporta
  }

  const handleToggle = async () => {
    const result = await toggleNotifications();
    
    if (result) {
      toast.success('🔔 Notificações ativadas!', {
        description: 'Você receberá notificações quando chegar mensagens',
      });
    } else if (!isEnabled) {
      toast.error('❌ Permissão negada', {
        description: 'Verifique as configurações do navegador',
      });
    } else {
      toast.info('🔕 Notificações desativadas');
    }
  };

  return (
    <button
      onClick={handleToggle}
      className={`
        p-2 rounded-full transition-colors
        ${isEnabled 
          ? 'text-green-600 hover:bg-green-100' 
          : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
        }
      `}
      title={isEnabled ? 'Desativar notificações' : 'Ativar notificações'}
    >
      {isEnabled ? (
        <Bell className="w-5 h-5" />
      ) : (
        <BellOff className="w-5 h-5" />
      )}
    </button>
  );
}














