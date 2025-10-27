/**
 * useDesktopNotifications - Hook para notificações de desktop
 * 
 * Funcionalidades:
 * - Pedir permissão ao usuário
 * - Notificar quando chegar mensagem (apenas se tab não está em foco)
 * - Ao clicar na notificação, abrir/focar a conversa
 * - Configuração: ativar/desativar
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

interface NotificationOptions {
  title: string;
  body: string;
  icon?: string;
  tag?: string;
  conversationId?: string;
}

export function useDesktopNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>('default');
  const [isEnabled, setIsEnabled] = useState(false);
  const navigate = useNavigate();

  // Verificar permissão inicial
  useEffect(() => {
    if ('Notification' in window) {
      setPermission(Notification.permission);
      
      // Recuperar preferência do localStorage
      const saved = localStorage.getItem('desktop-notifications-enabled');
      setIsEnabled(saved === 'true' && Notification.permission === 'granted');
    }
  }, []);

  // Pedir permissão
  const requestPermission = useCallback(async () => {
    if (!('Notification' in window)) {
      console.warn('⚠️ [NOTIFICATIONS] Navegador não suporta notificações');
      return false;
    }

    if (Notification.permission === 'granted') {
      setIsEnabled(true);
      localStorage.setItem('desktop-notifications-enabled', 'true');
      return true;
    }

    if (Notification.permission !== 'denied') {
      const result = await Notification.requestPermission();
      setPermission(result);
      
      if (result === 'granted') {
        setIsEnabled(true);
        localStorage.setItem('desktop-notifications-enabled', 'true');
        console.log('✅ [NOTIFICATIONS] Permissão concedida');
        return true;
      } else {
        console.log('❌ [NOTIFICATIONS] Permissão negada');
        return false;
      }
    }

    return false;
  }, []);

  // Ativar/desativar notificações
  const toggleNotifications = useCallback(async () => {
    if (!isEnabled) {
      // Ativar: pedir permissão
      const granted = await requestPermission();
      return granted;
    } else {
      // Desativar
      setIsEnabled(false);
      localStorage.setItem('desktop-notifications-enabled', 'false');
      console.log('🔕 [NOTIFICATIONS] Desativadas');
      return false;
    }
  }, [isEnabled, requestPermission]);

  // Mostrar notificação
  const showNotification = useCallback(
    (options: NotificationOptions) => {
      // Verificar se está habilitado
      if (!isEnabled || Notification.permission !== 'granted') {
        return;
      }

      // Não notificar se a tab estiver em foco
      if (document.hasFocus()) {
        console.log('ℹ️ [NOTIFICATIONS] Tab em foco, não notificando');
        return;
      }

      console.log('🔔 [NOTIFICATIONS] Mostrando notificação:', options.title);

      // Criar notificação
      const notification = new Notification(options.title, {
        body: options.body,
        icon: options.icon || '/logo.png',
        tag: options.tag || 'alrea-chat',
        badge: '/logo.png',
        requireInteraction: false,
      });

      // Ao clicar: focar janela e navegar para conversa
      notification.onclick = () => {
        window.focus();
        
        if (options.conversationId) {
          navigate(`/chat?conversation=${options.conversationId}`);
        }
        
        notification.close();
      };

      // Fechar automaticamente após 5 segundos
      setTimeout(() => {
        notification.close();
      }, 5000);
    },
    [isEnabled, navigate]
  );

  return {
    permission,
    isEnabled,
    isSupported: 'Notification' in window,
    requestPermission,
    toggleNotifications,
    showNotification,
  };
}





