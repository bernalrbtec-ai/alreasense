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
        flex items-center gap-2 px-3 py-2 rounded-lg transition-colors
        ${isEnabled 
          ? 'bg-green-100 text-green-700 hover:bg-green-200' 
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
        }
      `}
      title={isEnabled ? 'Desativar notificações' : 'Ativar notificações'}
    >
      {isEnabled ? (
        <>
          <Bell size={18} />
          <span className="text-sm font-medium">Notificações ON</span>
        </>
      ) : (
        <>
          <BellOff size={18} />
          <span className="text-sm font-medium">Notificações OFF</span>
        </>
      )}
    </button>
  );
}





