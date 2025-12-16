import { useState, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Zap, Search, X } from 'lucide-react';
import { useQuickReplies, QuickReply } from '../hooks/useQuickReplies';
import { api } from '@/lib/api';

interface QuickRepliesButtonProps {
  onSelect: (content: string) => void;
  disabled?: boolean;
}

export function QuickRepliesButton({ onSelect, disabled }: QuickRepliesButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  // ✅ Usar hook com cache
  const { quickReplies, loading, refetch, invalidateCache } = useQuickReplies(
    search,
    '-use_count,title'
  );

  // ✅ Debug: Log para verificar se componente está sendo renderizado
  useEffect(() => {
    console.log('⚡ [QUICK REPLIES BUTTON] Componente montado', { disabled, quickRepliesCount: quickReplies.length });
  }, [disabled, quickReplies.length]);

  // ✅ Ouvir evento customizado para abrir via atalho "/"
  useEffect(() => {
    const handleOpenEvent = () => {
      if (!disabled) {
        setIsOpen(true);
      }
    };
    
    document.addEventListener('openQuickReplies', handleOpenEvent);
    return () => document.removeEventListener('openQuickReplies', handleOpenEvent);
  }, [disabled]);

  // ✅ Buscar ao abrir (com cache) e calcular posição
  useEffect(() => {
    if (isOpen) {
      // ✅ FIX: Não fazer refetch automático - o hook já busca ao montar
      // Apenas calcular posição do dropdown baseado no botão
      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        setPosition({
          top: rect.top - 8, // 8px acima do botão
          right: window.innerWidth - rect.right
        });
      }
    } else {
      setPosition(null);
    }
  }, [isOpen]); // ✅ FIX: Remover refetch das dependências para evitar loops

  // ✅ Fechar ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // ✅ Fechar ao pressionar Escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
        setSearch('');
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  const handleSelect = async (reply: QuickReply) => {
    // Inserir conteúdo no input
    onSelect(reply.content);
    
    // Incrementar contador de uso (sem bloquear UI)
    api.post(`/chat/quick-replies/${reply.id}/use/`)
      .then(() => {
        // ✅ Invalidar cache local para atualizar ordenação
        invalidateCache();
        // ✅ Refetch silencioso em background (sem parâmetros)
        setTimeout(() => refetch(), 500);
      })
      .catch(console.error);
    
    // Fechar dropdown
    setIsOpen(false);
    setSearch('');
  };

  const filtered = useMemo(() => {
    if (!search) return quickReplies;
    const lower = search.toLowerCase();
    return quickReplies.filter(r => 
      r.title.toLowerCase().includes(lower) || 
      r.content.toLowerCase().includes(lower)
    );
  }, [quickReplies, search]);

  return (
    <>
      <div className="relative">
        <button
          ref={buttonRef}
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled}
          className={`
            p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 
            flex-shrink-0 shadow-sm hover:shadow-md
            ${isOpen ? 'bg-gray-200 shadow-md' : ''}
            ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
          `}
          title="Respostas rápidas (/)"
        >
          <Zap className="w-6 h-6 text-gray-600" />
        </button>
      </div>
      
      {isOpen && position && createPortal(
        <div 
          ref={dropdownRef}
          className="fixed w-80 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 z-[10000] max-h-96 flex flex-col"
          style={{
            top: `${position.top}px`,
            right: `${position.right}px`,
            transform: 'translateY(-100%)'
          }}>
          {/* Busca */}
          <div className="p-3 border-b border-gray-200 dark:border-gray-700">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar respostas rápidas..."
                className="w-full pl-10 pr-8 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                         focus:outline-none focus:ring-2 focus:ring-[#00a884] 
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                autoFocus
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          
          {/* Lista - ✅ SEM contador visual */}
          <div className="overflow-y-auto flex-1">
            {loading ? (
              <div className="p-4 text-center text-gray-500 dark:text-gray-400">Carregando...</div>
            ) : filtered.length === 0 ? (
              <div className="p-4 text-center text-gray-500 dark:text-gray-400">
                {search ? 'Nenhuma resposta encontrada' : 'Nenhuma resposta rápida cadastrada'}
              </div>
            ) : (
              filtered.map((reply) => (
                <button
                  key={reply.id}
                  onClick={() => handleSelect(reply)}
                  className="w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700 
                           border-b border-gray-100 dark:border-gray-700 last:border-0 
                           transition-colors"
                >
                  {/* ✅ Layout simplificado - SEM contador */}
                  <div className="font-semibold text-gray-900 dark:text-gray-100">{reply.title}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 mt-1 line-clamp-2">
                    {reply.content}
                  </div>
                  {reply.category && (
                    <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">{reply.category}</div>
                  )}
                </button>
              ))
            )}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

