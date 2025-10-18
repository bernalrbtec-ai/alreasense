import { useState, useEffect } from 'react';
import { Building2, Plus, Pencil, Trash2 } from 'lucide-react';
import { api } from '../../lib/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { toast } from 'sonner';

interface Department {
  id: string;
  name: string;
  color: string;
  ai_enabled: boolean;
}

export function DepartmentsManager() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingDept, setEditingDept] = useState<Department | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    color: '#3b82f6',
    ai_enabled: false
  });

  useEffect(() => {
    fetchDepartments();
  }, []);

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
      toast.error('Erro ao carregar departamentos');
      setDepartments([]); // Garantir array vazio em caso de erro
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      // Criar payload sem o tenant (backend adiciona automaticamente)
      const payload = {
        name: formData.name,
        color: formData.color,
        ai_enabled: false // Sempre false até implementar IA
      };
      
      if (editingDept) {
        await api.patch(`/auth/departments/${editingDept.id}/`, payload);
        toast.success('Departamento atualizado!');
      } else {
        await api.post('/auth/departments/', payload);
        toast.success('Departamento criado!');
      }
      
      fetchDepartments();
      handleCloseModal();
    } catch (error: any) {
      console.error('Erro ao salvar departamento:', error);
      console.error('Erro detalhado:', error.response?.data);
      
      // Extrair mensagem de erro de forma segura
      const errorData = error.response?.data;
      let errorMsg = 'Erro ao salvar departamento';
      
      if (typeof errorData === 'string') {
        errorMsg = errorData;
      } else if (errorData && typeof errorData === 'object') {
        if (errorData.detail) {
          errorMsg = errorData.detail;
        } else if (errorData.error) {
          errorMsg = errorData.error;
        } else if (errorData.name) {
          errorMsg = Array.isArray(errorData.name) ? errorData.name[0] : errorData.name;
        } else {
          // Pegar primeira mensagem de qualquer campo
          const errors = Object.entries(errorData).map(([field, msgs]: [string, any]) => {
            const message = Array.isArray(msgs) ? msgs[0] : msgs;
            return `${field}: ${message}`;
          });
          errorMsg = errors[0] || errorMsg;
        }
      }
      
      // Garantir que seja string
      if (typeof errorMsg !== 'string') {
        errorMsg = 'Erro ao salvar departamento';
      }
      
      toast.error(errorMsg);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir este departamento?')) return;
    
    try {
      await api.delete(`/auth/departments/${id}/`);
      toast.success('Departamento excluído!');
      fetchDepartments();
    } catch (error) {
      toast.error('Erro ao excluir departamento');
    }
  };

  const handleEdit = (dept: Department) => {
    setEditingDept(dept);
    setFormData({
      name: dept.name,
      color: dept.color,
      ai_enabled: dept.ai_enabled
    });
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingDept(null);
    setFormData({ name: '', color: '#3b82f6', ai_enabled: false });
  };

  if (loading) {
    return <div className="text-center py-8">Carregando...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Departamentos</h3>
        <Button size="sm" onClick={() => setShowModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Novo Departamento
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {Array.isArray(departments) && departments.map((dept) => (
          <div
            key={dept.id}
            className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-sm transition-shadow"
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: `${dept.color}20` }}
                >
                  <Building2 className="w-5 h-5" style={{ color: dept.color }} />
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 text-sm">{dept.name}</h4>
                  {dept.ai_enabled && (
                    <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full">
                      IA
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => handleEdit(dept)}
                  className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                >
                  <Pencil className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => handleDelete(dept.id)}
                  className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {departments.length === 0 && (
        <div className="text-center py-8 bg-gray-50 rounded-lg">
          <Building2 className="w-10 h-10 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-600 text-sm">Nenhum departamento cadastrado</p>
          <button
            onClick={() => setShowModal(true)}
            className="mt-3 text-blue-600 hover:text-blue-700 font-medium text-sm"
          >
            Criar primeiro departamento
          </button>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              {editingDept ? 'Editar Departamento' : 'Novo Departamento'}
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nome
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="Ex: Financeiro, Comercial"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Cor
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="w-12 h-10 border border-gray-300 rounded cursor-pointer"
                  />
                  <input
                    type="text"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 opacity-50 cursor-not-allowed">
                <input
                  type="checkbox"
                  id="ai_enabled"
                  checked={false}
                  disabled
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <label htmlFor="ai_enabled" className="text-sm text-gray-700">
                  Habilitar IA <span className="text-xs text-blue-600 font-medium">(Em breve)</span>
                </label>
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
                  {editingDept ? 'Salvar' : 'Criar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

