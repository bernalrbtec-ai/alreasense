import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/select';
import { 
  Bell, 
  Search, 
  Filter, 
  MessageSquare, 
  Check, 
  Phone,
  Calendar,
  Reply,
  Eye
} from 'lucide-react';
import { useNotifications } from '../hooks/useNotifications';

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

export default function NotificationsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [campaignFilter, setCampaignFilter] = useState<string>('all');
  const [selectedNotification, setSelectedNotification] = useState<Notification | null>(null);
  const [showReplyModal, setShowReplyModal] = useState(false);
  const [replyMessage, setReplyMessage] = useState('');
  const [sendingReply, setSendingReply] = useState(false);
  
  // Templates de resposta rápida
  const quickReplies = [
    "Obrigado pelo seu contato! Em breve retornaremos.",
    "Recebemos sua mensagem e entraremos em contato em breve.",
    "Obrigado pelo interesse! Vamos analisar sua solicitação.",
    "Sua mensagem foi recebida com sucesso. Retornaremos em breve.",
    "Obrigado! Vamos processar sua solicitação o mais rápido possível."
  ];
  
  const { 
    notifications, 
    stats, 
    loading, 
    fetchNotifications, 
    markAsRead, 
    markAllAsRead, 
    replyToNotification 
  } = useNotifications();

  // Responder notificação
  const handleReplyToNotification = async () => {
    if (!selectedNotification || !replyMessage.trim()) return;
    
    setSendingReply(true);
    const success = await replyToNotification(selectedNotification.id, replyMessage);
    
    if (success) {
      setShowReplyModal(false);
      setReplyMessage('');
      setSelectedNotification(null);
    }
    
    setSendingReply(false);
  };

  // Filtros
  const filteredNotifications = notifications.filter(notification => {
    const matchesSearch = 
      notification.contact_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      notification.campaign_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      notification.received_message.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || notification.status === statusFilter;
    const matchesCampaign = campaignFilter === 'all' || notification.campaign_name === campaignFilter;
    
    return matchesSearch && matchesStatus && matchesCampaign;
  });

  // Campanhas únicas para filtro
  const uniqueCampaigns = [...new Set(notifications.map(n => n.campaign_name))];

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('pt-BR');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'unread':
        return <Badge variant="destructive">Não Lida</Badge>;
      case 'read':
        return <Badge variant="secondary">Lida</Badge>;
      case 'replied':
        return <Badge variant="default">Respondida</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'response':
        return <MessageSquare className="h-4 w-4 text-blue-500" />;
      case 'delivery':
        return <Check className="h-4 w-4 text-green-500" />;
      case 'read':
        return <Eye className="h-4 w-4 text-purple-500" />;
      default:
        return <Bell className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
          <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold flex items-center gap-2">
            <Bell className="h-6 w-6 sm:h-7 sm:w-7 lg:h-8 lg:w-8" />
            Notificações
          </h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Gerencie respostas e interações das suas campanhas
          </p>
        </div>
        
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold text-blue-600">
              {stats.unread_count}
            </div>
            <div className="text-sm text-muted-foreground">
              Não lidas
      </div>
      </div>

          {stats.unread_count > 0 && (
            <Button onClick={markAllAsRead} variant="outline">
              Marcar todas como lidas
            </Button>
          )}
                </div>
              </div>

      {/* Filtros */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filtros
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar por contato, campanha ou mensagem..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="all">Todos os status</option>
              <option value="unread">Não lidas</option>
              <option value="read">Lidas</option>
              <option value="replied">Respondidas</option>
            </Select>
            
            <Select value={campaignFilter} onChange={(e) => setCampaignFilter(e.target.value)}>
              <option value="all">Todas as campanhas</option>
              {uniqueCampaigns.map(campaign => (
                <option key={campaign} value={campaign}>
                  {campaign}
                </option>
              ))}
            </Select>
            
            <Button variant="outline" onClick={fetchNotifications}>
              Atualizar
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Lista de Notificações */}
      <Card>
        <CardHeader>
          <CardTitle>
            Notificações ({filteredNotifications.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-muted-foreground">Carregando notificações...</div>
                  </div>
          ) : filteredNotifications.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <Bell className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <div className="text-muted-foreground">
                  Nenhuma notificação encontrada
                </div>
              </div>
            </div>
          ) : (
            <div className="max-h-[600px] overflow-y-auto">
              <div className="space-y-4">
                {filteredNotifications.map((notification) => (
                  <Card key={notification.id} className={`transition-all hover:shadow-md ${
                    notification.status === 'unread' ? 'border-l-4 border-l-blue-500' : ''
                  }`}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3 flex-1">
                          {getNotificationIcon(notification.notification_type)}
                          
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2">
                              <h3 className="font-semibold text-lg">
                                {notification.contact_name}
                     </h3>
                              {getStatusBadge(notification.status)}
                   </div>
            
                            <div className="text-sm text-muted-foreground mb-2">
                              <div className="flex items-center gap-4">
                                <span className="flex items-center gap-1">
                                  <Phone className="h-3 w-3" />
                                  {notification.contact_phone}
                                </span>
                                <span className="flex items-center gap-1">
                                  <Calendar className="h-3 w-3" />
                                  {formatTimestamp(notification.received_timestamp)}
                                </span>
                         </div>
                         </div>
                         
                            <div className="mb-3">
                              <div className="text-sm font-medium text-muted-foreground mb-1">
                                Campanha: {notification.campaign_name}
                         </div>
                              <div className="text-sm bg-gray-50 p-3 rounded-lg border">
                                {notification.received_message}
                         </div>
                         </div>
                         
                            {notification.sent_reply && (
                              <div className="mb-3">
                                <div className="text-sm font-medium text-muted-foreground mb-1">
                                  Sua resposta:
                         </div>
                                <div className="text-sm bg-blue-50 p-3 rounded-lg border border-blue-200">
                                  {notification.sent_reply}
                         </div>
                  </div>
                            )}
                </div>
              </div>
              
                        <div className="flex items-center gap-2">
                          {notification.status === 'unread' && (
                  <Button
                              size="sm"
                    variant="outline"
                              onClick={() => markAsRead(notification.id)}
                  >
                              <Check className="h-4 w-4" />
                  </Button>
                          )}
                          
                          {notification.status !== 'replied' && (
                         <Button
                              size="sm"
                              onClick={() => {
                                setSelectedNotification(notification);
                                setShowReplyModal(true);
                              }}
                            >
                              <Reply className="h-4 w-4 mr-1" />
                              Responder
                            </Button>
                          )}
                        </div>
                </div>
                    </CardContent>
                  </Card>
                ))}
          </div>
        </div>
      )}
        </CardContent>
      </Card>

      {/* Modal de Resposta */}
      {showReplyModal && selectedNotification && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Responder para {selectedNotification.contact_name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Mensagem de resposta:
                  </label>
                
                {/* Templates de resposta rápida */}
                <div className="mb-3">
                  <div className="text-xs text-muted-foreground mb-2">Respostas rápidas:</div>
                  <div className="flex flex-wrap gap-2">
                    {quickReplies.map((template, index) => (
                      <Button
                        key={index}
                        variant="outline"
                        size="sm"
                        onClick={() => setReplyMessage(template)}
                        className="text-xs"
                      >
                        {template.substring(0, 30)}...
                      </Button>
                    ))}
                </div>
              </div>
              
                <textarea
                  value={replyMessage}
                  onChange={(e) => setReplyMessage(e.target.value)}
                  placeholder="Digite sua resposta..."
                  className="w-full p-3 border rounded-lg resize-none"
                  rows={4}
                  maxLength={4000}
                />
                <div className="text-xs text-muted-foreground mt-1">
                  {replyMessage.length}/4000 caracteres
                </div>
              </div>
              
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowReplyModal(false);
                    setReplyMessage('');
                    setSelectedNotification(null);
                  }}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={handleReplyToNotification}
                  disabled={!replyMessage.trim() || sendingReply}
                >
                  {sendingReply ? 'Enviando...' : 'Enviar Resposta'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}