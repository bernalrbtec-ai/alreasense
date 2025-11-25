import React, { useState } from 'react';
import { Bell, Users, Building2 } from 'lucide-react';
import { useAuthStore } from '../../../stores/authStore';
import { UserNotificationSettings } from './UserNotificationSettings';
import { DepartmentNotificationSettings } from './DepartmentNotificationSettings';

export const NotificationSettings: React.FC = () => {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<'user' | 'department'>('user');
  
  const isManager = user?.role === 'gerente' || user?.role === 'admin';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-100">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Bell className="h-6 w-6 text-blue-600" />
              Notificações
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              Personalize suas notificações para ficar sempre informado sobre suas tarefas e compromissos.
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" role="tablist">
          <button
            onClick={() => setActiveTab('user')}
            role="tab"
            aria-selected={activeTab === 'user'}
            aria-controls="user-notifications-panel"
            className={`
              group relative py-4 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'user'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            <span className="flex items-center gap-2">
              <Users className="h-4 w-4" /> Minhas Notificações
              {activeTab === 'user' && (
                <span className="absolute -top-1 -right-1 h-2 w-2 bg-blue-500 rounded-full animate-pulse"></span>
              )}
            </span>
          </button>
          
          {isManager && (
            <button
              onClick={() => setActiveTab('department')}
              role="tab"
              aria-selected={activeTab === 'department'}
              aria-controls="department-notifications-panel"
              className={`
                group relative py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeTab === 'department'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <span className="flex items-center gap-2">
                <Building2 className="h-4 w-4" /> Notificações do Departamento
                {activeTab === 'department' && (
                  <span className="absolute -top-1 -right-1 h-2 w-2 bg-blue-500 rounded-full animate-pulse"></span>
                )}
              </span>
            </button>
          )}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        <div
          key={activeTab}
          className="animate-fade-in"
          role="tabpanel"
          id={`${activeTab}-notifications-panel`}
        >
          {activeTab === 'user' && <UserNotificationSettings />}
          {activeTab === 'department' && isManager && <DepartmentNotificationSettings />}
        </div>
      </div>
    </div>
  );
};

