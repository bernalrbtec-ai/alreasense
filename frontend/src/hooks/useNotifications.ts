import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/hooks/use-toast';
import { api } from '@/lib/api';

interface Notification {
  id: string;
  campaign_name: string;
  contact_name: string;
  contact_phone: string;
  instance_name: string;
  notification_type: 'response' | 'delivery' | 'read';
  status: 'unread' | 'read' | 'replied';
  received_message: string;
  received_timestamp: string;
  sent_reply?: string;
  sent_timestamp?: string;
  sent_by_name?: string;
  created_at: string;
}

interface NotificationStats {
  unread_count: number;
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [stats, setStats] = useState<NotificationStats>({ unread_count: 0 });
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const { toast } = useToast();

  // Carregar notificações
  const fetchNotifications = useCallback(async () => {
    try {
      const response = await api.get('/campaigns/notifications/');
      const newNotifications = response.data.results || response.data;
      
      setNotifications(newNotifications);
      
      // Buscar contador de não lidas
      const statsResponse = await api.get('/campaigns/notifications/unread_count/');
      setStats(statsResponse.data);
      
      setLastChecked(new Date());
    } catch (error) {
      console.error('Erro ao carregar notificações:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Verificar novas notificações (para polling)
  const checkNewNotifications = useCallback(async () => {
    try {
      const response = await api.get('/campaigns/notifications/unread_count/');
      const currentUnreadCount = response.data.unread_count;
      const previousUnreadCount = stats.unread_count;
      
      // Se há novas notificações não lidas
      if (currentUnreadCount > previousUnreadCount && previousUnreadCount > 0) {
        // Buscar a notificação mais recente
        const notificationsResponse = await api.get('/campaigns/notifications/?limit=1');
        const latestNotification = notificationsResponse.data.results?.[0] || notificationsResponse.data[0];
        
        if (latestNotification) {
          showNotificationToast(latestNotification);
        }
      }
      
      setStats(response.data);
    } catch (error) {
      console.error('Erro ao verificar novas notificações:', error);
    }
  }, [stats.unread_count]);

  // Mostrar toast de notificação
  const showNotificationToast = useCallback((notification: Notification) => {
    const messagePreview = notification.received_message.length > 100 
      ? notification.received_message.substring(0, 100) + '...'
      : notification.received_message;

    toast({
      title: `💬 ${notification.contact_name} respondeu!`,
      description: `Campanha: ${notification.campaign_name}\n${messagePreview}`,
      duration: 8000,
      action: {
        label: 'Ver Detalhes',
        onClick: () => {
          // Navegar para página de notificações
          window.location.href = '/admin/notifications';
        }
      }
    });
  }, [toast]);

  // Marcar como lida
  const markAsRead = useCallback(async (notificationId: string) => {
    try {
      await api.post('/campaigns/notifications/mark_as_read/', {
        notification_id: notificationId
      });
      
      // Atualizar lista local
      setNotifications(prev => 
        prev.map(notif => 
          notif.id === notificationId 
            ? { ...notif, status: 'read' as const }
            : notif
        )
      );
      
      // Atualizar stats
      setStats(prev => ({ unread_count: Math.max(0, prev.unread_count - 1) }));
      
      return true;
    } catch (error) {
      console.error('Erro ao marcar como lida:', error);
      toast({
        title: 'Erro',
        description: 'Não foi possível marcar como lida',
        variant: 'destructive',
      });
      return false;
    }
  }, [toast]);

  // Marcar todas como lidas
  const markAllAsRead = useCallback(async () => {
    try {
      await api.post('/campaigns/notifications/mark_all_as_read/');
      
      // Atualizar lista local
      setNotifications(prev => 
        prev.map(notif => ({ ...notif, status: 'read' as const }))
      );
      
      setStats({ unread_count: 0 });
      
      toast({
        title: 'Sucesso',
        description: 'Todas as notificações foram marcadas como lidas',
      });
      
      return true;
    } catch (error) {
      console.error('Erro ao marcar todas como lidas:', error);
      toast({
        title: 'Erro',
        description: 'Não foi possível marcar todas como lidas',
        variant: 'destructive',
      });
      return false;
    }
  }, [toast]);

  // Responder notificação
  const replyToNotification = useCallback(async (notificationId: string, message: string) => {
    try {
      await api.post('/campaigns/notifications/reply/', {
        notification_id: notificationId,
        message: message
      });
      
      // Atualizar lista local
      setNotifications(prev => 
        prev.map(notif => 
          notif.id === notificationId 
            ? { 
                ...notif, 
                status: 'replied' as const,
                sent_reply: message,
                sent_timestamp: new Date().toISOString()
              }
            : notif
        )
      );
      
      toast({
        title: 'Sucesso',
        description: 'Resposta enviada com sucesso',
      });
      
      return true;
    } catch (error) {
      console.error('Erro ao enviar resposta:', error);
      toast({
        title: 'Erro',
        description: 'Não foi possível enviar a resposta',
        variant: 'destructive',
      });
      return false;
    }
  }, [toast]);

  // Efeito para carregamento inicial
  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  // Efeito para polling de novas notificações
  useEffect(() => {
    // Polling a cada 15 segundos
    const interval = setInterval(checkNewNotifications, 15000);
    return () => clearInterval(interval);
  }, [checkNewNotifications]);

  return {
    notifications,
    stats,
    loading,
    lastChecked,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    replyToNotification,
    checkNewNotifications,
  };
}

// Hook simplificado para apenas o contador de notificações (usado no header)
export function useNotificationCount() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const response = await api.get('/campaigns/notifications/unread_count/');
      setUnreadCount(response.data.unread_count);
    } catch (error) {
      console.error('Erro ao carregar contador de notificações:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUnreadCount();
    
    // Polling a cada 30 segundos
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  return {
    unreadCount,
    loading,
    refreshCount: fetchUnreadCount,
  };
}
