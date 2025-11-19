/**
 * Modal para adicionar contatos faltantes a uma campanha existente
 */
import React, { useState, useEffect } from 'react';
import { X, Users, AlertCircle, CheckCircle, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface Tag {
  id: string;
  name: string;
  color: string;
  contact_count: number;
}

interface AddContactsModalProps {
  campaign: {
    id: string;
    name: string;
    total_contacts: number;
  };
  onClose: () => void;
  onSuccess: () => void;
}

export function AddContactsModal({ campaign, onClose, onSuccess }: AddContactsModalProps) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTagId, setSelectedTagId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [result, setResult] = useState<{
    added_count: number;
    total_contacts: number;
  } | null>(null);

  // Buscar tags ao abrir o modal
  useEffect(() => {
    const fetchTags = async () => {
      try {
        const response = await api.get('/contacts/tags/');
        const tagsData = response.data.results || response.data || [];
        setTags(tagsData);
      } catch (error) {
        console.error('Erro ao buscar tags:', error);
      }
    };
    fetchTags();
  }, []);

  const filteredTags = tags.filter(tag =>
    tag.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleAddMissing = async () => {
    if (!selectedTagId) {
      toast.error('Selecione uma tag');
      return;
    }

    try {
      setAdding(true);
      
      const response = await api.post(`/campaigns/${campaign.id}/add-contacts/`, {
        tag_id: selectedTagId,
        add_missing_from_tag: true
      });

      setResult(response.data);
      toast.success(`${response.data.added_count} contatos adicionados com sucesso!`);
      
      // Aguardar um pouco antes de fechar para o usuário ver o resultado
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (error: any) {
      console.error('❌ Erro ao adicionar contatos:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao adicionar contatos';
      toast.error(errorMsg);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl border border-gray-200 w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Adicionar Contatos Faltantes</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4">
          {!result ? (
            <>
              <div className="mb-4">
                <p className="text-sm text-gray-600 mb-2">
                  Campanha: <span className="font-medium text-gray-900">{campaign.name}</span>
                </p>
                <p className="text-sm text-gray-600 mb-2">
                  Contatos atuais: <span className="font-medium text-gray-900">{campaign.total_contacts}</span>
                </p>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-blue-900 mb-1">
                      Adicionar contatos faltantes
                    </p>
                    <p className="text-xs text-blue-700">
                      Selecione a tag e adicione apenas os contatos que ainda não estão na campanha.
                    </p>
                  </div>
                </div>
              </div>

              {/* Seleção de Tag */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Selecionar Tag
                </label>
                
                {/* Busca de tags */}
                <div className="relative mb-3">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Buscar tag..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {/* Lista de tags */}
                <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg">
                  {filteredTags.length === 0 ? (
                    <div className="p-4 text-center text-sm text-gray-500">
                      Nenhuma tag encontrada
                    </div>
                  ) : (
                    <div className="divide-y divide-gray-200">
                      {filteredTags.map((tag) => (
                        <button
                          key={tag.id}
                          onClick={() => setSelectedTagId(tag.id)}
                          className={`
                            w-full text-left p-3 hover:bg-gray-50 transition-colors
                            ${selectedTagId === tag.id ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''}
                          `}
                        >
                          <div className="flex items-center gap-2">
                            <div
                              className="w-4 h-4 rounded-full"
                              style={{ backgroundColor: tag.color }}
                            />
                            <span className="font-medium text-gray-900">{tag.name}</span>
                            <span className="text-xs text-gray-500 ml-auto">
                              {tag.contact_count} contatos
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-green-900 mb-1">
                    Contatos adicionados com sucesso!
                  </p>
                  <p className="text-xs text-green-700">
                    {result.added_count} novos contatos foram adicionados à campanha.
                  </p>
                  <p className="text-xs text-green-700 mt-1">
                    Total de contatos agora: {result.total_contacts}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            disabled={adding}
          >
            {result ? 'Fechar' : 'Cancelar'}
          </button>
          {!result && (
            <button
              onClick={handleAddMissing}
              disabled={adding || !selectedTagId}
              className={`
                px-4 py-2 rounded-lg transition-colors flex items-center gap-2
                ${adding || !selectedTagId
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
                }
              `}
            >
              {adding ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Adicionando...
                </>
              ) : (
                <>
                  <Users className="w-4 h-4" />
                  Adicionar Contatos Faltantes
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

