import { useState, useEffect } from 'react';
import { Building2, Plus, Pencil, Trash2, Users } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

interface Department {
  id: string;
  tenant: string;
  name: string;
  color: string;
  ai_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingDept, setEditingDept] = useState<Department | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    color: '#3b82f6',
    ai_enabled: false
  });

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchDepartments();
  }, []);

  const fetchDepartments = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_URL}/api/auth/departments/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDepartments(response.data);
    } catch (error) {
      console.error('Erro ao buscar departamentos:', error);
      toast.error('Erro ao carregar departamentos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('access_token');
      
      if (editingDept) {
        // Update
        await axios.patch(
          `${API_URL}/api/auth/departments/${editingDept.id}/`,
          formData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success('Departamento atualizado com sucesso!');
      } else {
        // Create
        await axios.post(
          `${API_URL}/api/auth/departments/`,
          formData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success('Departamento criado com sucesso!');
      }
      
      fetchDepartments();
      handleCloseModal();
    } catch (error: any) {
      console.error('Erro ao salvar departamento:', error);
      const errorMsg = error.response?.data?.name?.[0] || 'Erro ao salvar departamento';
      toast.error(errorMsg);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir este departamento?')) return;
    
    try {
      const token = localStorage.getItem('access_token');
      await axios.delete(`${API_URL}/api/auth/departments/${id}/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Departamento excluído com sucesso!');
      fetchDepartments();
    } catch (error) {
      console.error('Erro ao excluir departamento:', error);
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
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Departamentos</h1>
          <p className="text-gray-600 mt-1">
            Gerencie os departamentos da sua organização
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Novo Departamento
        </button>
      </div>

      {/* Grid de Departamentos */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {departments.map((dept) => (
          <div
            key={dept.id}
            className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div
                  className="w-12 h-12 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: `${dept.color}20` }}
                >
                  <Building2
                    className="w-6 h-6"
                    style={{ color: dept.color }}
                  />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{dept.name}</h3>
                  {dept.ai_enabled && (
                    <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full mt-1 inline-block">
                      IA Habilitada
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleEdit(dept)}
                  className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                  title="Editar"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(dept.id)}
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                  title="Excluir"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Users className="w-4 h-4" />
              <span>0 usuários</span>
            </div>
          </div>
        ))}
      </div>

      {departments.length === 0 && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <Building2 className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600">Nenhum departamento cadastrado</p>
          <button
            onClick={() => setShowModal(true)}
            className="mt-4 text-blue-600 hover:text-blue-700 font-medium"
          >
            Criar primeiro departamento
          </button>
        </div>
      )}

      {/* Modal Criar/Editar */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              {editingDept ? 'Editar Departamento' : 'Novo Departamento'}
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nome do Departamento
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Ex: Financeiro, Comercial, Suporte"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Cor
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="w-16 h-10 border border-gray-300 rounded cursor-pointer"
                  />
                  <input
                    type="text"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="#3b82f6"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="ai_enabled"
                  checked={formData.ai_enabled}
                  onChange={(e) => setFormData({ ...formData, ai_enabled: e.target.checked })}
                  className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                />
                <label htmlFor="ai_enabled" className="text-sm text-gray-700">
                  Habilitar recursos de IA
                </label>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
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

