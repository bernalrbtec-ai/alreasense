/**
 * Tabs de departamentos - Estilo WhatsApp Web
 */
import React, { useEffect } from 'react';
import { Inbox } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { Department } from '../types';
import { usePermissions } from '@/hooks/usePermissions';

export function DepartmentTabs() {
  const { departments, activeDepartment, setDepartments, setActiveDepartment } = useChatStore();
  const { can_access_all_departments, departmentIds } = usePermissions();

  useEffect(() => {
    const fetchDepartments = async () => {
      try {
        const response = await api.get('/auth/departments/');
        const depts = response.data.results || response.data;
        
        let filteredDepts = depts;
        if (!can_access_all_departments && departmentIds) {
          filteredDepts = depts.filter((d: Department) => departmentIds.includes(d.id));
        }
        
        setDepartments(filteredDepts);
        
        // Se não tem departamento ativo, selecionar Inbox
        if (!activeDepartment) {
          setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department);
        }
      } catch (error) {
        console.error('Erro ao carregar departamentos:', error);
      }
    };

    fetchDepartments();
  }, [can_access_all_departments, departmentIds, setDepartments, setActiveDepartment, activeDepartment]);

  return (
    <div className="flex items-center gap-1 px-2 py-2 bg-white border-b border-gray-200 overflow-x-auto">
      {/* Tab Inbox */}
      <button
        onClick={() => setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department)}
        className={`
          flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap
          ${activeDepartment?.id === 'inbox'
            ? 'bg-orange-50 text-orange-600 border border-orange-200'
            : 'text-gray-600 hover:bg-gray-100'
          }
        `}
      >
        <Inbox className="w-4 h-4" />
        Inbox
      </button>

      {/* Tabs Departamentos */}
      {departments.map((dept) => (
        <button
          key={dept.id}
          onClick={() => setActiveDepartment(dept)}
          className={`
            px-3 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap
            ${activeDepartment?.id === dept.id
              ? 'bg-green-50 text-green-600 border border-green-200'
              : 'text-gray-600 hover:bg-gray-100'
            }
          `}
        >
          {dept.name}
        </button>
      ))}
    </div>
  );
}
