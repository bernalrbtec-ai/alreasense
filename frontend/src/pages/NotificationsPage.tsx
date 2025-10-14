import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { 
  Bell, 
  Search, 
  MessageSquare, 
  Check, 
  Phone,
  Calendar,
  Reply,
  Eye
} from 'lucide-react';

interface Notification {
  id: string;
  campaign_name: string;
  contact_name: string;
  contact_phone: string;
  message_content: string;
  received_at: string;
  status: 'unread' | 'read' | 'replied';
  notification_type: 'response' | 'delivery' | 'read';
}

interface NotificationStats {
  total: number;
  unread: number;
  responses: number;
  deliveries: number;
  reads: number;
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [stats] = useState<NotificationStats>({
    total: 0,
    unread: 0,
    responses: 0,
    deliveries: 0,
    reads: 0
  });
  const [selectedTab, setSelectedTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const handleMarkAsRead = (notificationId: string) => {
    setNotifications(prev => 
      prev.map(notif => 
        notif.id === notificationId 
          ? { ...notif, status: 'read' as const }
          : notif
      )
    );
  };

  const handleMarkAllAsRead = () => {
    setNotifications(prev => 
      prev.map(notif => ({ ...notif, status: 'read' as const }))
    );
  };

  const filteredNotifications = notifications.filter(notification => {
    const matchesTab = selectedTab === 'all' || notification.status === selectedTab;
    const matchesSearch = notification.contact_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         notification.campaign_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'response': return <Reply className="h-4 w-4" />;
      case 'delivery': return <Check className="h-4 w-4" />;
      case 'read': return <Eye className="h-4 w-4" />;
      default: return <Bell className="h-4 w-4" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'unread': return 'bg-blue-100 text-blue-800';
      case 'read': return 'bg-gray-100 text-gray-800';
      case 'replied': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'response': return 'bg-green-100 text-green-800';
      case 'delivery': return 'bg-blue-100 text-blue-800';
      case 'read': return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Notificações</h1>
          <p className="mt-1 text-sm text-gray-500">
            Respostas e atualizações de campanhas
          </p>
        </div>
        <Button 
          onClick={handleMarkAllAsRead}
          variant="outline"
          disabled={stats.unread === 0}
        >
          <Check className="h-4 w-4 mr-2" />
          Marcar todas como lidas
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Bell className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 rounded-lg">
              <MessageSquare className="h-5 w-5 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Não Lidas</p>
              <p className="text-2xl font-bold text-gray-900">{stats.unread}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <Reply className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Respostas</p>
              <p className="text-2xl font-bold text-gray-900">{stats.responses}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Eye className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Mensagens Lidas</p>
              <p className="text-2xl font-bold text-gray-900">{stats.reads}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Filters */}
      <Card className="p-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                placeholder="Buscar por contato ou campanha..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant={selectedTab === 'all' ? 'default' : 'outline'}
              onClick={() => setSelectedTab('all')}
              size="sm"
            >
              Todas ({stats.total})
            </Button>
            <Button
              variant={selectedTab === 'unread' ? 'default' : 'outline'}
              onClick={() => setSelectedTab('unread')}
              size="sm"
            >
              Não Lidas ({stats.unread})
            </Button>
            <Button
              variant={selectedTab === 'read' ? 'default' : 'outline'}
              onClick={() => setSelectedTab('read')}
              size="sm"
            >
              Lidas ({stats.total - stats.unread})
            </Button>
          </div>
        </div>
      </Card>

      {/* Notifications List */}
      <Card className="p-6">
        <CardHeader>
          <CardTitle>Notificações Recentes</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredNotifications.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Bell className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>Nenhuma notificação encontrada</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredNotifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`p-4 border rounded-lg transition-colors ${
                    notification.status === 'unread' 
                      ? 'bg-blue-50 border-blue-200' 
                      : 'bg-white border-gray-200'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <div className="p-2 bg-white rounded-lg shadow-sm">
                        {getNotificationIcon(notification.notification_type)}
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-medium text-gray-900 truncate">
                            {notification.contact_name}
                          </h3>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(notification.notification_type)}`}>
                            {notification.notification_type}
                          </span>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(notification.status)}`}>
                            {notification.status}
                          </span>
                        </div>
                        
                        <p className="text-sm text-gray-600 mb-2">
                          <strong>Campanha:</strong> {notification.campaign_name}
                        </p>
                        
                        <p className="text-sm text-gray-600 mb-2">
                          <Phone className="h-3 w-3 inline mr-1" />
                          {notification.contact_phone}
                        </p>
                        
                        <p className="text-sm text-gray-500">
                          <Calendar className="h-3 w-3 inline mr-1" />
                          {new Date(notification.received_at).toLocaleString('pt-BR')}
                        </p>
                        
                        {notification.message_content && (
                          <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                            <p className="text-sm text-gray-700">{notification.message_content}</p>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {notification.status === 'unread' && (
                      <Button
                        onClick={() => handleMarkAsRead(notification.id)}
                        variant="outline"
                        size="sm"
                      >
                        <Check className="h-4 w-4 mr-1" />
                        Marcar como lida
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}