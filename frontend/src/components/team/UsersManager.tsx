import { useState, useEffect } from 'react';
import { Users, Plus, Pencil, Trash2, Mail, Shield, Building2 } from 'lucide-react';
import { api } from '../../lib/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { toast } from 'sonner';

interface Department {
  id: string;
  name: string;
  color: string;
}

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  department_ids: string[];
  department_names: string[];
  is_active: boolean;
}

const ROLE_LABELS: Record<string, string> = {
  'admin': 'Administrador',
  'gerente': 'Gerente',
  'agente': 'Agente'
};

const ROLE_COLORS: Record<string, string> = {
  'admin': 'bg-purple-100 text-purple-700',
  'gerente': 'bg-blue-100 text-blue-700',
  'agente': 'bg-green-100 text-green-700'
};

export function UsersManager() {
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    role: 'agente',
    password: '',
    password_confirm: '',
    department_ids: [] as string[]
  });

  useEffect(() => {
    Promise.all([fetchUsers(), fetchDepartments()]);
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await api.get('/auth/users-api/');
      // Garantir que sempre temos um array
      const data = Array.isArray(response.data) 
        ? response.data 
        : (response.data?.results || []);
      setUsers(data);
    } catch (error) {
      console.error('Erro ao buscar usuários:', error);
      toast.error('Erro ao carregar usuários');
      setUsers([]); // Garantir array vazio em caso de erro
    } finally {
      setLoading(false);
    }
  };

  const fetchDepartments = async () => {
    try {
      const response = await api.get('/auth/departments/');
      // Garantir que sempre temos um array
      const data = Array.isArray(response.data) 
        ? response.data 
        : (response.data?.results || []);
      setDepartments(data);
    } catch (error) {
      console.error('Erro ao buscar departamentos:', error);
      setDepartments([]); // Garantir array vazio em caso de erro
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!editingUser && formData.password !== formData.password_confirm) {
      toast.error('As senhas não coincidem');
      return;
    }
    
    try {
      if (editingUser) {
        // Update user (sem senha)
        const { password, password_confirm, ...updateData } = formData;
        await api.patch(`/auth/users-api/${editingUser.id}/`, updateData);
        toast.success('Usuário atualizado!');
      } else {
        // Create user - garantir que username seja o email
        const payload = {
          ...formData,
          username: formData.email, // Garantir que username seja definido
        };
        await api.post('/auth/users-api/', payload);
        toast.success('Usuário criado!');
      }
      
      fetchUsers();
      handleCloseModal();
    } catch (error: any) {
      console.error('Erro ao salvar usuário:', error);
      console.error('Erro detalhado:', error.response?.data);
      
      // Extrair mensagem de erro mais específica
      const errorData = error.response?.data;
      let errorMsg = 'Erro ao salvar usuário';
      
      if (typeof errorData === 'string') {
        errorMsg = errorData;
      } else if (errorData && typeof errorData === 'object') {
        // Tentar extrair mensagens de erro dos campos
        if (errorData.detail) {
          errorMsg = errorData.detail;
        } else if (errorData.error) {
          errorMsg = errorData.error;
        } else {
          // Pegar a primeira mensagem de erro de qualquer campo
          const errors = Object.entries(errorData).map(([field, msgs]: [string, any]) => {
            const message = Array.isArray(msgs) ? msgs[0] : msgs;
            return `${field}: ${message}`;
          });
          errorMsg = errors[0] || errorMsg;
        }
      }
      
      // Garantir que errorMsg seja sempre uma string
      if (typeof errorMsg !== 'string') {
        errorMsg = 'Erro ao salvar usuário';
      }
      
      toast.error(errorMsg);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir este usuário?')) return;
    
    try {
      await api.delete(`/auth/users-api/${id}/`);
      toast.success('Usuário excluído!');
      fetchUsers();
    } catch (error) {
      toast.error('Erro ao excluir usuário');
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      password: '',
      password_confirm: '',
      department_ids: user.department_ids || []
    });
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingUser(null);
    setFormData({
      email: '',
      first_name: '',
      last_name: '',
      role: 'agente',
      password: '',
      password_confirm: '',
      department_ids: []
    });
  };

  if (loading) {
    return <div className="text-center py-8">Carregando...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Usuários</h3>
        <Button size="sm" onClick={() => setShowModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Novo Usuário
        </Button>
      </div>

      <div className="space-y-2">
        {Array.isArray(users) && users.map((user) => (
          <div
            key={user.id}
            className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-sm transition-shadow"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3 flex-1">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <span className="text-blue-700 font-medium text-sm">
                    {user.first_name?.[0] || user.email[0].toUpperCase()}
                  </span>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-gray-900">
                      {user.first_name} {user.last_name}
                    </h4>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${ROLE_COLORS[user.role] || 'bg-gray-100 text-gray-700'}`}>
                      {ROLE_LABELS[user.role] || user.role}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <div className="flex items-center gap-1">
                      <Mail className="w-3.5 h-3.5" />
                      {user.email}
                    </div>
                    {user.department_names && user.department_names.length > 0 && (
                      <div className="flex items-center gap-1">
                        <Building2 className="w-3.5 h-3.5" />
                        {user.department_names.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleEdit(user)}
                  className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(user.id)}
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {users.length === 0 && (
        <div className="text-center py-8 bg-gray-50 rounded-lg">
          <Users className="w-10 h-10 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-600 text-sm">Nenhum usuário cadastrado</p>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              {editingUser ? 'Editar Usuário' : 'Novo Usuário'}
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Nome *
                  </label>
                  <input
                    type="text"
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Sobrenome *
                  </label>
                  <input
                    type="text"
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email *
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                  disabled={!!editingUser}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Função *
                </label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="agente">Agente - Acesso ao chat dos seus departamentos</option>
                  <option value="gerente">Gerente - Métricas do departamento + chat</option>
                  <option value="admin">Administrador - Acesso total ao tenant</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  {formData.role === 'agente' && '• Agente tem acesso apenas ao chat dos departamentos que pertence'}
                  {formData.role === 'gerente' && '• Gerente pode visualizar métricas e acessar chat dos seus departamentos'}
                  {formData.role === 'admin' && '• Administrador tem acesso completo a todos os recursos do tenant'}
                </p>
              </div>

              {!editingUser && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Senha *
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Confirmar Senha *
                    </label>
                    <input
                      type="password"
                      value={formData.password_confirm}
                      onChange={(e) => setFormData({ ...formData, password_confirm: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      required
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Departamentos
                </label>
                <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3">
                  {Array.isArray(departments) && departments.map((dept) => (
                    <label key={dept.id} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.department_ids.includes(dept.id)}
                        onChange={(e) => {
                          const newIds = e.target.checked
                            ? [...formData.department_ids, dept.id]
                            : formData.department_ids.filter(id => id !== dept.id);
                          setFormData({ ...formData, department_ids: newIds });
                        }}
                        className="w-4 h-4 text-blue-600 rounded"
                      />
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded"
                          style={{ backgroundColor: dept.color }}
                        />
                        <span className="text-sm text-gray-700">{dept.name}</span>
                      </div>
                    </label>
                  ))}
                  {departments.length === 0 && (
                    <p className="text-sm text-gray-500">Nenhum departamento disponível</p>
                  )}
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  {editingUser ? 'Salvar' : 'Criar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

