/**
 * Modal de transferência de conversa
 */
import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Conversation, Department, User } from '../types';
import { X, ArrowRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '@/stores/authStore';

interface TransferModalProps {
  conversation: Conversation;
  onClose: () => void;
  onTransferSuccess?: () => void;
}

export function TransferModal({ conversation, onClose, onTransferSuccess }: TransferModalProps) {
  const { updateConversation, setActiveConversation, removeConversation, setConversations } = useChatStore();
  const { user } = useAuthStore();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedDepartment, setSelectedDepartment] = useState<string>('');
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchDepartments();
  }, []);

  useEffect(() => {
    if (selectedDepartment) {
      fetchUsers(selectedDepartment);
    } else {
      setUsers([]);
      setSelectedAgent('');
    }
  }, [selectedDepartment]);

  const fetchDepartments = async () => {
    try {
      const response = await api.get('/auth/departments/');
      const depts = response.data.results || response.data;
      setDepartments(depts);
    } catch (error) {
      console.error('Erro ao carregar departamentos:', error);
    }
  };

  const fetchUsers = async (departmentId: string) => {
    try {
      const response = await api.get('/auth/users-api/', {
        params: { department: departmentId }
      });
      const usersData = response.data.results || response.data;
      setUsers(usersData);
    } catch (error) {
      console.error('Erro ao carregar usuários:', error);
    }
  };

  const handleTransfer = async () => {
    if (!selectedDepartment && !selectedAgent) {
      toast.error('Selecione um departamento ou agente');
      return;
    }

    try {
      setLoading(true);

      const payload: any = { reason };
      if (selectedDepartment) payload.new_department = selectedDepartment;
      if (selectedAgent) payload.new_agent = selectedAgent;

      const response = await api.post(`/chat/conversations/${conversation.id}/transfer/`, payload);
      const updatedConv: Conversation = response.data;

      // ✅ Recarregar lista completa de conversas
      try {
        const convsResponse = await api.get('/chat/conversations/', {
          params: { ordering: '-last_message_at' }
        });
        const convs = convsResponse.data.results || convsResponse.data;
        setConversations(convs);
        console.log('✅ [TransferModal] Lista de conversas recarregada:', convs.length);
      } catch (error) {
        console.error('❌ [TransferModal] Erro ao recarregar conversas:', error);
      }

      // ✅ Verificar se usuário ainda tem acesso à conversa transferida
      const userDepartments = user?.departments?.map((d: Department) => d.id) || [];
      const userHasAccess = 
        user?.is_admin ||  // Admin sempre tem acesso
        (updatedConv.department && userDepartments.includes(updatedConv.department.id)) ||  // Pertence ao departamento
        (updatedConv.department === null && updatedConv.status === 'pending');  // Inbox (sem departamento)
      
      if (!userHasAccess) {
        // Usuário não tem mais acesso: remover da lista e fechar
        removeConversation(conversation.id);
        setActiveConversation(null);
        console.log('🔒 [TransferModal] Usuário perdeu acesso, conversa removida');
      } else {
        // Usuário ainda tem acesso: atualizar conversa na lista
        updateConversation(updatedConv);
        console.log('✅ [TransferModal] Conversa atualizada, usuário mantém acesso');
        
        // Se a conversa transferida era a ativa, atualizar também
        if (useChatStore.getState().activeConversation?.id === conversation.id) {
          setActiveConversation(updatedConv);
        }
      }

      toast.success('Conversa transferida com sucesso! ✅');
      
      // Chamar callback se fornecido
      if (onTransferSuccess) {
        onTransferSuccess();
      }
      
      onClose();
    } catch (error: any) {
      console.error('Erro ao transferir:', error);
      toast.error(error.response?.data?.error || 'Erro ao transferir conversa');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-[#1f262e] rounded-xl shadow-2xl w-full max-w-md border border-gray-800">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-white">Transferir Conversa</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-700 rounded transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {/* Info atual */}
          <div className="p-3 bg-[#2b2f36] rounded-lg border border-gray-700">
            <p className="text-xs text-gray-400 mb-1">Contato:</p>
            <p className="text-sm text-white font-medium">
              {conversation.contact_name || conversation.contact_phone}
            </p>
            <p className="text-xs text-gray-400 mt-2">Departamento atual:</p>
            <p className="text-sm text-green-500">
              {conversation.department_data?.name || 'N/A'}
            </p>
          </div>

          {/* Selecionar departamento */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Novo Departamento
            </label>
            <select
              value={selectedDepartment}
              onChange={(e) => setSelectedDepartment(e.target.value)}
              className="w-full px-4 py-2 bg-[#2b2f36] border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-green-600"
            >
              <option value="">Manter departamento atual</option>
              {departments.map((dept) => (
                <option key={dept.id} value={dept.id}>
                  {dept.name}
                </option>
              ))}
            </select>
          </div>

          {/* Selecionar agente */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Novo Agente
            </label>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              disabled={!selectedDepartment}
              className="w-full px-4 py-2 bg-[#2b2f36] border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-green-600 disabled:opacity-50"
            >
              <option value="">Sem agente específico</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.first_name || user.email}
                </option>
              ))}
            </select>
            {!selectedDepartment && (
              <p className="mt-1 text-xs text-gray-500">
                Selecione um departamento primeiro
              </p>
            )}
          </div>

          {/* Motivo */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Motivo (opcional)
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ex: Cliente solicitou falar com financeiro"
              rows={3}
              className="w-full px-4 py-2 bg-[#2b2f36] border border-gray-700 rounded-lg text-white placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-green-600"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-300 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={handleTransfer}
            disabled={loading || (!selectedDepartment && !selectedAgent)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Transferindo...</span>
              </>
            ) : (
              <>
                <ArrowRight className="w-4 h-4" />
                <span>Transferir</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

