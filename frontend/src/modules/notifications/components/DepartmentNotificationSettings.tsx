import React, { useState, useEffect, useCallback } from 'react';
import { Building2, Clock, Bell, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../../../lib/api';
import { showSuccessToast, showErrorToast } from '../../../lib/toastHelper';
import { useAuthStore } from '../../../stores/authStore';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';

interface DepartmentNotificationPreferences {
  id?: string;
  department: string;
  department_name: string;
  daily_summary_enabled: boolean;
  daily_summary_time: string | null;
  agenda_reminder_enabled: boolean;
  agenda_reminder_time: string | null;
  notify_pending: boolean;
  notify_in_progress: boolean;
  notify_status_changes: boolean;
  notify_completed: boolean;
  notify_overdue: boolean;
  notify_only_critical: boolean;
  notify_only_assigned: boolean;
  max_tasks_per_notification: number;
  notify_via_whatsapp: boolean;
  notify_via_websocket: boolean;
  notify_via_email: boolean;
  can_manage?: boolean;
  created_at?: string;
  updated_at?: string;
}

export const DepartmentNotificationSettings: React.FC = () => {
  const { user } = useAuthStore();
  const [preferences, setPreferences] = useState<DepartmentNotificationPreferences[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState<Record<string, boolean>>({});
  const [hasChanges, setHasChanges] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/notifications/department-preferences/my_departments/');
      setPreferences(response.data);
      // Inicializar hasChanges para cada departamento
      const changes: Record<string, boolean> = {};
      response.data.forEach((pref: DepartmentNotificationPreferences) => {
        if (pref.id) {
          changes[pref.id] = false;
        }
      });
      setHasChanges(changes);
    } catch (error: any) {
      showErrorToast('Erro ao carregar preferências de departamento');
      console.error('Error fetching department preferences:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const savePreferences = useCallback(async (prefId: string) => {
    const pref = preferences.find(p => p.id === prefId);
    if (!pref || !hasChanges[prefId]) return;

    setIsSaving(prev => ({ ...prev, [prefId]: true }));
    try {
      const response = await api.patch(`/notifications/department-preferences/${prefId}/`, pref);
      setPreferences(prev => prev.map(p => p.id === prefId ? response.data : p));
      setHasChanges(prev => ({ ...prev, [prefId]: false }));
      showSuccessToast(`Preferências de ${pref.department_name} salvas com sucesso!`, {
        duration: 3000,
      });
    } catch (error: any) {
      showErrorToast('Erro ao salvar preferências de departamento', {
        duration: 5000,
      });
      console.error('Error saving department preferences:', error);
    } finally {
      setIsSaving(prev => ({ ...prev, [prefId]: false }));
    }
  }, [preferences, hasChanges]);

  // Auto-save após 2 segundos de inatividade
  useEffect(() => {
    Object.keys(hasChanges).forEach(prefId => {
      if (hasChanges[prefId]) {
        const timer = setTimeout(() => {
          savePreferences(prefId);
        }, 2000);
        return () => clearTimeout(timer);
      }
    });
  }, [preferences, hasChanges, savePreferences]);

  const updatePreference = (prefId: string, field: keyof DepartmentNotificationPreferences, value: any) => {
    setPreferences(prev => prev.map(p => {
      if (p.id === prefId) {
        return { ...p, [field]: value };
      }
      return p;
    }));
    setHasChanges(prev => ({ ...prev, [prefId]: true }));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando preferências dos departamentos...</p>
        </div>
      </div>
    );
  }

  if (preferences.length === 0) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-start">
          <AlertCircle className="h-6 w-6 text-blue-600 mt-0.5" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">Nenhum departamento encontrado</h3>
            <p className="mt-2 text-sm text-blue-700">
              Você não é gestor de nenhum departamento. Apenas gestores podem configurar notificações de departamento.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {preferences.map((pref) => (
        <div key={pref.id} className="space-y-6">
          {/* Header do Departamento */}
          <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg p-6 border border-purple-100">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  <Building2 className="h-6 w-6 text-purple-600" />
                  {pref.department_name}
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  Configure as notificações para este departamento
                </p>
              </div>
            </div>
          </div>

          {/* Indicador de salvamento */}
          {isSaving[pref.id!] && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-2 text-sm text-blue-700 animate-fade-in">
              <Loader2 className="h-4 w-4 animate-spin" />
              Salvando preferências de {pref.department_name}...
            </div>
          )}

          {hasChanges[pref.id!] && !isSaving[pref.id!] && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-center justify-between text-sm animate-fade-in">
              <span className="text-yellow-800">Você tem alterações não salvas em {pref.department_name}</span>
              <Button
                onClick={() => savePreferences(pref.id!)}
                className="px-3 py-1 bg-yellow-600 text-white rounded hover:bg-yellow-700 transition-colors"
              >
                Salvar agora
              </Button>
            </div>
          )}

          {/* Resumo Diário */}
          <Card className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h4 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Bell className="h-5 w-5 text-blue-600" /> Resumo Diário
                </h4>
                <p className="mt-1 text-sm text-gray-500">
                  Configure um horário para receber um resumo das tarefas do departamento
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={pref.daily_summary_enabled}
                  onChange={(e) => updatePreference(pref.id!, 'daily_summary_enabled', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>

            {pref.daily_summary_enabled && (
              <div className="mt-4 space-y-4 animate-fade-in">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Horário do Resumo
                  </label>
                  <input
                    type="time"
                    value={pref.daily_summary_time || ''}
                    onChange={(e) => updatePreference(pref.id!, 'daily_summary_time', e.target.value)}
                    className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-lg py-2 px-4"
                  />
                  {pref.daily_summary_time && (
                    <p className="mt-2 text-xs text-gray-500">
                      Você receberá o resumo todos os dias às {pref.daily_summary_time}
                    </p>
                  )}
                </div>
              </div>
            )}
          </Card>

          {/* Filtros Avançados */}
          <Card className="p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-orange-600" /> Filtros Avançados
            </h4>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">Apenas Tarefas Críticas</label>
                  <p className="text-xs text-gray-500">Mostrar apenas tarefas com prioridade alta ou urgente</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pref.notify_only_critical}
                    onChange={(e) => updatePreference(pref.id!, 'notify_only_critical', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">Apenas Tarefas Atribuídas</label>
                  <p className="text-xs text-gray-500">Mostrar apenas tarefas com responsável definido</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pref.notify_only_assigned}
                    onChange={(e) => updatePreference(pref.id!, 'notify_only_assigned', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Máximo de Tarefas por Notificação
                </label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={pref.max_tasks_per_notification}
                  onChange={(e) => updatePreference(pref.id!, 'max_tasks_per_notification', parseInt(e.target.value))}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 py-2 px-4"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Limite para evitar mensagens muito longas (padrão: 20)
                </p>
              </div>
            </div>
          </Card>

          {/* Canais de Notificação */}
          <Card className="p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Bell className="h-5 w-5" /> Canais de Notificação
            </h4>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">WhatsApp</label>
                  <p className="text-xs text-gray-500">Receber notificações via WhatsApp</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pref.notify_via_whatsapp}
                    onChange={(e) => updatePreference(pref.id!, 'notify_via_whatsapp', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">WebSocket (Navegador)</label>
                  <p className="text-xs text-gray-500">Receber notificações no navegador</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pref.notify_via_websocket}
                    onChange={(e) => updatePreference(pref.id!, 'notify_via_websocket', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>
          </Card>

          {/* Tipos de Notificação */}
          <Card className="p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <CheckCircle className="h-5 w-5" /> Tipos de Notificação
            </h4>
            <div className="space-y-4">
              {[
                { key: 'notify_pending', label: 'Tarefas Pendentes', desc: 'Incluir tarefas pendentes' },
                { key: 'notify_in_progress', label: 'Tarefas Em Progresso', desc: 'Incluir tarefas em andamento' },
                { key: 'notify_completed', label: 'Tarefas Concluídas', desc: 'Incluir tarefas concluídas' },
                { key: 'notify_overdue', label: 'Tarefas Atrasadas', desc: 'Incluir tarefas atrasadas' },
              ].map(({ key, label, desc }) => (
                <div key={key} className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-gray-700">{label}</label>
                    <p className="text-xs text-gray-500">{desc}</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={pref[key as keyof DepartmentNotificationPreferences] as boolean}
                      onChange={(e) => updatePreference(pref.id!, key as keyof DepartmentNotificationPreferences, e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ))}
    </div>
  );
};

