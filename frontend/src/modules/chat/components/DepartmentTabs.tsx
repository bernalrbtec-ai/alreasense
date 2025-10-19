/**
 * Tabs de departamentos (topo do chat)
 */
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useChatStore } from "../store/chatStore";
import { Department } from "../types";
import { usePermissions } from "@/hooks/usePermissions";
import { Loader2, Inbox } from "lucide-react";

export function DepartmentTabs() {
  const [loading, setLoading] = useState(true);
  const { departmentIds, can_access_all_departments } = usePermissions();
  const { 
    departments, 
    activeDepartment, 
    setDepartments, 
    setActiveDepartment 
  } = useChatStore();

  useEffect(() => {
    const fetchDepartments = async () => {
      try {
        setLoading(true);
        const response = await api.get("/auth/departments/");
        let allDepartments: Department[] = response.data.results || response.data;

        // Filtrar por permissões
        if (!can_access_all_departments) {
          allDepartments = allDepartments.filter(d => departmentIds.includes(d.id));
        }

        setDepartments(allDepartments);

        // Selecionar Inbox por padrão
        if (!activeDepartment) {
          setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department);
        }
      } catch (error) {
        console.error("Erro ao buscar departamentos:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchDepartments();
  }, [can_access_all_departments, departmentIds, setDepartments, setActiveDepartment, activeDepartment]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4 bg-[#1f262e] border-b border-gray-800">
        <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (departments.length === 0) {
    return (
      <div className="p-4 bg-[#1f262e] border-b border-gray-800 text-center text-gray-500 text-sm">
        Nenhum departamento disponível
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-4 md:px-6 py-3 bg-[#1f262e] border-b border-gray-800 overflow-x-auto">
      {/* Tab Inbox */}
      <button
        onClick={() => setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department)}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap
          ${activeDepartment?.id === 'inbox'
            ? 'bg-orange-600 text-white shadow-lg'
            : 'bg-[#2b2f36] text-gray-300 hover:bg-[#363c46]'
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
            px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap
            ${activeDepartment?.id === dept.id
              ? 'bg-green-600 text-white shadow-lg'
              : 'bg-[#2b2f36] text-gray-300 hover:bg-[#363c46]'
            }
          `}
          style={
            activeDepartment?.id === dept.id && dept.color
              ? { backgroundColor: dept.color }
              : {}
          }
        >
          {dept.name}
        </button>
      ))}
    </div>
  );
}
