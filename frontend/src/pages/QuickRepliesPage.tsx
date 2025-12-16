import { useState, useEffect } from 'react';
import { Plus, Edit, Trash2, Search, Zap, Save, X } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Label } from '../components/ui/Label';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import { api } from '../lib/api';
import { showSuccessToast, showErrorToast } from '../lib/toastHelper';
import { useQuickReplies, QuickReply } from '../modules/chat/hooks/useQuickReplies';

export default function QuickRepliesPage() {
  const [search, setSearch] = useState('');
  const [ordering, setOrdering] = useState<'-use_count,title' | 'title'>('-use_count,title');
  const [showModal, setShowModal] = useState(false);
  const [editingReply, setEditingReply] = useState<QuickReply | null>(null);
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    category: ''
  });
  const [saving, setSaving] = useState(false);

  const { quickReplies, loading, refetch, invalidateCache } = useQuickReplies(search, ordering);

  // Limpar formulário ao fechar modal
  useEffect(() => {
    if (!showModal) {
      setEditingReply(null);
      setFormData({ title: '', content: '', category: '' });
    }
  }, [showModal]);

  // Preencher formulário ao editar
  useEffect(() => {
    if (editingReply) {
      setFormData({
        title: editingReply.title,
        content: editingReply.content,
        category: editingReply.category || ''
      });
    }
  }, [editingReply]);

  const handleCreate = () => {
    setEditingReply(null);
    setFormData({ title: '', content: '', category: '' });
    setShowModal(true);
  };

  const handleEdit = (reply: QuickReply) => {
    setEditingReply(reply);
    setShowModal(true);
  };

  const handleDelete = async (reply: QuickReply) => {
    if (!confirm(`Tem certeza que deseja deletar "${reply.title}"?`)) {
      return;
    }

    try {
      await api.delete(`/chat/quick-replies/${reply.id}/`);
      showSuccessToast('Resposta rápida deletada com sucesso!');
      invalidateCache();
      refetch(true);
    } catch (error: any) {
      showErrorToast(error.response?.data?.error || 'Erro ao deletar resposta rápida');
    }
  };

  const handleSave = async () => {
    if (!formData.title.trim() || !formData.content.trim()) {
      showErrorToast('Título e conteúdo são obrigatórios');
      return;
    }

    setSaving(true);
    try {
      if (editingReply) {
        // Editar
        await api.patch(`/chat/quick-replies/${editingReply.id}/`, formData);
        showSuccessToast('Resposta rápida atualizada com sucesso!');
      } else {
        // Criar
        await api.post('/chat/quick-replies/', formData);
        showSuccessToast('Resposta rápida criada com sucesso!');
      }
      
      invalidateCache();
      refetch(true);
      setShowModal(false);
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || 
                      (error.response?.data?.title?.[0] || error.response?.data?.content?.[0]) ||
                      'Erro ao salvar resposta rápida';
      showErrorToast(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  const filteredReplies = quickReplies.filter(reply => {
    if (!search) return true;
    const lower = search.toLowerCase();
    return reply.title.toLowerCase().includes(lower) || 
           reply.content.toLowerCase().includes(lower) ||
           (reply.category && reply.category.toLowerCase().includes(lower));
  });

  return (
    <div className="container mx-auto px-4 py-6 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Zap className="w-6 h-6" />
            Respostas Rápidas
          </h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Gerencie respostas rápidas para uso no chat
          </p>
        </div>
        <Button onClick={handleCreate} className="flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nova Resposta
        </Button>
      </div>

      {/* Filtros */}
      <Card className="p-4 mb-6">
        <div className="flex gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por título, conteúdo ou categoria..."
                className="pl-10"
              />
            </div>
          </div>
          <select
            value={ordering}
            onChange={(e) => setOrdering(e.target.value as any)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                     focus:outline-none focus:ring-2 focus:ring-[#00a884]"
          >
            <option value="-use_count,title">Mais usadas</option>
            <option value="title">Título (A-Z)</option>
          </select>
        </div>
      </Card>

      {/* Lista */}
      {loading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner size="lg" />
        </div>
      ) : filteredReplies.length === 0 ? (
        <Card className="p-12 text-center">
          <Zap className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">
            {search ? 'Nenhuma resposta encontrada' : 'Nenhuma resposta rápida cadastrada'}
          </p>
        </Card>
      ) : (
        <div className="grid gap-4">
          {filteredReplies.map((reply) => (
            <Card key={reply.id} className="p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                      {reply.title}
                    </h3>
                    {/* ✅ Contador visual APENAS aqui (para admin/gerentes) */}
                    {reply.use_count > 0 ? (
                      <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 
                                     rounded-full text-xs font-medium">
                        {reply.use_count}x usado{reply.use_count > 1 ? 's' : ''}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400 dark:text-gray-500">Nunca usado</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-2 whitespace-pre-wrap">
                    {reply.content}
                  </p>
                  {reply.category && (
                    <span className="inline-block px-2 py-1 bg-gray-100 dark:bg-gray-700 
                                   text-gray-600 dark:text-gray-400 rounded text-xs">
                      {reply.category}
                    </span>
                  )}
                </div>
                <div className="flex gap-2 ml-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleEdit(reply)}
                    className="flex items-center gap-1"
                  >
                    <Edit className="w-4 h-4" />
                    Editar
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(reply)}
                    className="flex items-center gap-1 text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4" />
                    Deletar
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Modal de Criar/Editar */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                  {editingReply ? 'Editar Resposta Rápida' : 'Nova Resposta Rápida'}
                </h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <Label htmlFor="title">Título *</Label>
                  <Input
                    id="title"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="Ex: Boa tarde"
                    maxLength={100}
                  />
                </div>

                <div>
                  <Label htmlFor="content">Conteúdo *</Label>
                  <textarea
                    id="content"
                    value={formData.content}
                    onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                    placeholder="Digite o conteúdo da resposta..."
                    rows={6}
                    maxLength={4000}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                             bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                             focus:outline-none focus:ring-2 focus:ring-[#00a884] resize-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {formData.content.length}/4000 caracteres
                  </p>
                </div>

                <div>
                  <Label htmlFor="category">Categoria (opcional)</Label>
                  <Input
                    id="category"
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    placeholder="Ex: Saudações, Despedidas..."
                    maxLength={50}
                  />
                </div>

                <div className="flex gap-2 justify-end pt-4">
                  <Button
                    variant="outline"
                    onClick={() => setShowModal(false)}
                    disabled={saving}
                  >
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={saving || !formData.title.trim() || !formData.content.trim()}
                    className="flex items-center gap-2"
                  >
                    {saving ? (
                      <>
                        <LoadingSpinner size="sm" />
                        Salvando...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4" />
                        Salvar
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

