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
    <div className="flex-shrink-0 flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 sm:py-2 bg-white border-b border-gray-200 overflow-x-auto scrollbar-hide">
      {/* Tab Inbox - Responsivo */}
      <button
        onClick={() => setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department)}
        className={`
          flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
          ${activeDepartment?.id === 'inbox'
            ? 'bg-[#ea580c] text-white'
            : 'text-gray-600 hover:bg-gray-100 active:scale-95'
          }
        `}
      >
        <Inbox className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span className="hidden sm:inline">Inbox</span>
      </button>

      {/* Tabs Departamentos - Responsivo */}
      {departments.map((dept) => (
        <button
          key={dept.id}
          onClick={() => setActiveDepartment(dept)}
          className={`
            px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
            ${activeDepartment?.id === dept.id
              ? 'bg-[#00a884] text-white'
              : 'text-gray-600 hover:bg-gray-100 active:scale-95'
            }
          `}
        >
          {dept.name}
        </button>
      ))}
    </div>
  );
}
