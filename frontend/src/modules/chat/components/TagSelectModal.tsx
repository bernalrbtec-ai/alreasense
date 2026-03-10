import { useState, useEffect, useRef } from 'react';
import { X, Loader2, Tag as TagIcon } from 'lucide-react';
import { api } from '@/lib/api';
import { showErrorToast } from '@/lib/toastHelper';

export interface TagOption {
  id: string;
  name: string;
  color: string;
  contact_count?: number;
}

interface TagSelectModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedIds: string[];
  onApply: (ids: string[], tagsInfo: TagOption[]) => void;
}

export function TagSelectModal({ isOpen, onClose, selectedIds, onApply }: TagSelectModalProps) {
  const [tags, setTags] = useState<TagOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [entered, setEntered] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) {
      setError(null);
      setEntered(false);
      return;
    }
    setEntered(false);
    setSelected(Array.isArray(selectedIds) ? selectedIds : []);
    const rafId = requestAnimationFrame(() => setEntered(true));
    const fetchTags = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.get('/contacts/tags/');
        const data = (response?.data?.results ?? response?.data) ?? [];
        setTags(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('Erro ao carregar tags:', err);
        setError('Não foi possível carregar as tags.');
        showErrorToast('Carregar tags', 'Tags', err as Error);
        setTags([]);
      } finally {
        setLoading(false);
      }
    };
    fetchTags();
    return () => cancelAnimationFrame(rafId);
  }, [isOpen]); // selectedIds lido só na abertura para evitar refetch a cada re-render do pai

  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen && containerRef.current) {
      const first = containerRef.current.querySelector<HTMLElement>('button, [tabindex="0"]');
      first?.focus();
    }
  }, [isOpen, loading, tags.length]);

  const toggle = (tagId: string) => {
    setSelected((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  };

  const handleApply = () => {
    const tagsInfo = tags.filter((t) => selected.includes(t.id));
    onApply(selected, tagsInfo);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      className={`fixed inset-0 flex items-center justify-center z-[60] p-4 transition-opacity duration-200 ease-out ${
        entered ? 'opacity-100 bg-black/50 dark:bg-black/60' : 'opacity-0 bg-black/0'
      }`}
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={containerRef}
        onClick={(e) => e.stopPropagation()}
        className={`bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl shadow-xl max-w-md w-full max-h-[70vh] flex flex-col transition-all duration-200 ease-out ${
          entered ? 'opacity-100 scale-100' : 'opacity-0 scale-95'
        }`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tag-modal-title"
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-600">
          <h2 id="tag-modal-title" className="text-lg font-semibold flex items-center gap-2">
            <TagIcon className="h-5 w-5 text-gray-500 dark:text-gray-400" />
            Filtrar por tag
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="flex flex-wrap gap-2 justify-center mb-4">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div
                    key={i}
                    className="h-8 w-20 rounded-full bg-gray-200 dark:bg-gray-600 animate-pulse"
                    style={{ animationDelay: `${i * 50}ms` }}
                  />
                ))}
              </div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">Carregando tags...</p>
            </div>
          ) : error ? (
            <p className="text-red-500 dark:text-red-400 text-sm text-center py-4">{error}</p>
          ) : tags.length === 0 ? (
            <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-8">
              Nenhuma tag criada. Crie tags em Contatos para filtrar.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => toggle(tag.id)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-150 border active:scale-95 ${
                    selected.includes(tag.id)
                      ? 'text-white border-transparent'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600'
                  }`}
                  style={
                    selected.includes(tag.id)
                      ? { backgroundColor: tag.color || '#3b82f6', borderColor: tag.color || '#3b82f6' }
                      : undefined
                  }
                >
                  {tag.name}
                  {tag.contact_count != null && (
                    <span className="ml-1 opacity-80">({tag.contact_count})</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-gray-200 dark:border-gray-600">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors active:scale-[0.98]"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={loading || tags.length === 0 || !!error}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 active:scale-[0.98]"
          >
            Aplicar
          </button>
        </div>
      </div>
    </div>
  );
}
