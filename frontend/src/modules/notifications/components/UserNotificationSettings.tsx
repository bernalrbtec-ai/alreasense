import React, { useState, useEffect } from 'react';
import { Bell, Clock, CheckCircle, AlertCircle, Loader2, Send } from 'lucide-react';
import { api } from '../../../lib/api';
import { showSuccessToast, showErrorToast } from '../../../lib/toastHelper';
import { toast } from 'sonner';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';

interface UserNotificationPreferences {
  id?: string;
  daily_summary_enabled: boolean;
  daily_summary_time: string | null;
  agenda_reminder_enabled: boolean;
  agenda_reminder_time: string | null;
  notify_pending: boolean;
  notify_in_progress: boolean;
  notify_status_changes: boolean;
  notify_completed: boolean;
  notify_overdue: boolean;
  notify_via_whatsapp: boolean;
  notify_via_websocket: boolean;
  notify_via_email: boolean;
  created_at?: string;
  updated_at?: string;
}

export const UserNotificationSettings: React.FC = () => {
  const [preferences, setPreferences] = useState<UserNotificationPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/notifications/user-preferences/mine/');
      setPreferences(response.data);
    } catch (error: any) {
      if (error.response?.status === 404) {
        const defaultPrefs: UserNotificationPreferences = {
          daily_summary_enabled: false,
          daily_summary_time: null,
          agenda_reminder_enabled: false,
          agenda_reminder_time: null,
          notify_pending: true,
          notify_in_progress: true,
          notify_status_changes: true,
          notify_completed: false,
          notify_overdue: true,
          notify_via_whatsapp: true,
          notify_via_websocket: true,
          notify_via_email: false,
        };
        setPreferences(defaultPrefs);
      } else {
        showErrorToast('carregar', 'preferências de notificação', error);
        console.error('Error fetching preferences:', error);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const savePreferences = async () => {
    if (!preferences) return;

    try {
      setIsSaving(true);
      const response = await api.patch('/notifications/user-preferences/mine/', preferences);
      setPreferences(response.data);
      setHasChanges(false);
      showSuccessToast('salvar', 'preferências');
    } catch (error: any) {
      showErrorToast('salvar', 'preferências', error);
      console.error('Error saving preferences:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const updatePreference = (field: keyof UserNotificationPreferences, value: any) => {
    if (!preferences) return;
    setPreferences({ ...preferences, [field]: value });
    setHasChanges(true);
  };

  const sendDailySummaryNow = async () => {
    if (!preferences?.daily_summary_enabled) {
      toast.error('Ative o resumo diário primeiro');
      return;
    }

    try {
      setIsSending(true);
      const response = await api.post('/notifications/user-preferences/send_daily_summary_now/');
      
      if (response.data.success) {
        toast.success(response.data.message || '✅ Resumo diário enviado com sucesso!');
      } else {
        toast.error(response.data.message || '❌ Erro ao enviar resumo diário');
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.message || 'Erro ao enviar resumo diário';
      toast.error(`❌ ${errorMessage}`);
      console.error('Error sending daily summary:', error);
    } finally {
      setIsSending(false);
    }
  };

  useEffect(() => {
    if (!hasChanges || !preferences) return;
    const timer = setTimeout(() => {
      savePreferences();
    }, 2000);
    return () => clearTimeout(timer);
  }, [preferences, hasChanges]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando suas preferências...</p>
        </div>
      </div>
    );
  }

  if (!preferences) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-start">
          <AlertCircle className="h-6 w-6 text-red-600 mt-0.5" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Erro ao carregar preferências</h3>
            <p className="mt-2 text-sm text-red-700">Não foi possível carregar suas preferências de notificação.</p>
            <button
              onClick={fetchPreferences}
              className="mt-4 text-sm font-medium text-red-800 hover:text-red-900 underline"
            >
              Tentar novamente
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {isSaving && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-2 text-sm text-blue-700 animate-fade-in">
          <Loader2 className="h-4 w-4 animate-spin" />
          Salvando suas preferências...
        </div>
      )}

      {hasChanges && !isSaving && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-center justify-between text-sm">
          <span className="text-yellow-800">Você tem alterações não salvas</span>
          <Button onClick={savePreferences} size="sm" variant="outline">
            Salvar agora
          </Button>
        </div>
      )}

      {/* Resumo Diário */}
      <Card className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Resumo Diário
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Configure um horário para receber um resumo completo das suas tarefas
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={preferences.daily_summary_enabled}
              onChange={(e) => updatePreference('daily_summary_enabled', e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>

        {preferences.daily_summary_enabled && (
          <div className="mt-4 space-y-4 animate-fade-in">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Horário do Resumo
              </label>
              <input
                type="time"
                value={preferences.daily_summary_time || ''}
                onChange={(e) => updatePreference('daily_summary_time', e.target.value)}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-lg py-2 px-4"
                required
              />
              {preferences.daily_summary_time && (
                <p className="mt-2 text-xs text-gray-500">
                  Você receberá o resumo todos os dias às {preferences.daily_summary_time}
                </p>
              )}
            </div>
            <div className="pt-2 border-t border-gray-200">
              <Button
                onClick={sendDailySummaryNow}
                disabled={isSending}
                variant="outline"
                className="w-full sm:w-auto"
              >
                {isSending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Enviando...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 mr-2" />
                    Enviar Resumo Agora
                  </>
                )}
              </Button>
              <p className="mt-2 text-xs text-gray-500">
                Envie o resumo diário manualmente para testar ou quando necessário
              </p>
            </div>
          </div>
        )}
      </Card>

      {/* Canais de Notificação */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Bell className="h-5 w-5" />
          Canais de Notificação
        </h3>
        <div className="space-y-4">
          {[
            { key: 'notify_via_whatsapp', label: 'WhatsApp', desc: 'Receber notificações via WhatsApp' },
            { key: 'notify_via_websocket', label: 'WebSocket (Navegador)', desc: 'Receber notificações no navegador' },
            { key: 'notify_via_email', label: 'Email', desc: 'Receber notificações por email' },
          ].map(({ key, label, desc }) => (
            <div key={key} className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700">{label}</label>
                <p className="text-xs text-gray-500">{desc}</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences[key as keyof UserNotificationPreferences] as boolean}
                  onChange={(e) => updatePreference(key as keyof UserNotificationPreferences, e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
          ))}
        </div>
      </Card>

      {/* Tipos de Notificação */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle className="h-5 w-5" />
          Tipos de Notificação
        </h3>
        <div className="space-y-4">
          {[
            { key: 'notify_pending', label: 'Tarefas Pendentes', desc: 'Receber notificações sobre tarefas pendentes' },
            { key: 'notify_in_progress', label: 'Tarefas em Progresso', desc: 'Receber notificações sobre tarefas em andamento' },
            { key: 'notify_status_changes', label: 'Mudanças de Status', desc: 'Receber notificações quando tarefas mudam de status' },
            { key: 'notify_completed', label: 'Tarefas Concluídas', desc: 'Receber notificações sobre tarefas concluídas' },
            { key: 'notify_overdue', label: 'Tarefas Atrasadas', desc: 'Receber notificações sobre tarefas atrasadas' },
          ].map(({ key, label, desc }) => (
            <div key={key} className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700">{label}</label>
                <p className="text-xs text-gray-500">{desc}</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences[key as keyof UserNotificationPreferences] as boolean}
                  onChange={(e) => updatePreference(key as keyof UserNotificationPreferences, e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

