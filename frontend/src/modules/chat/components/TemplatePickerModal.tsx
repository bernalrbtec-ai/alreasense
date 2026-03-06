/**
 * Modal para escolher template WhatsApp (Meta).
 * Exibe templates disponíveis para a conversa; ao selecionar, envia mensagem por template (ex.: com botões).
 * Fora da janela 24h o envio por template é obrigatório; dentro da 24h pode ser usado para enviar templates com botões.
 */
import React, { useState, useEffect } from 'react';
import { X, FileText, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

export interface WhatsAppTemplate {
  id: string;
  name: string;
  template_id: string;
  language_code: string;
  body?: string;
  body_parameters_default?: string[];
  meta_status?: string;
  wa_instance_name?: string;
}

interface TemplatePickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  conversationId: string;
  onSelectTemplate: (templateId: string, bodyParameters: string[]) => void;
}

export function TemplatePickerModal({
  isOpen,
  onClose,
  conversationId,
  onSelectTemplate,
}: TemplatePickerModalProps) {
  const [templates, setTemplates] = useState<WhatsAppTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !conversationId) {
      setTemplates([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get(`/chat/conversations/${conversationId}/available-templates/`)
      .then((res) => {
        if (cancelled) return;
        const list = res.data?.results ?? res.data ?? [];
        setTemplates(Array.isArray(list) ? list : []);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.error || 'Erro ao carregar templates');
        setTemplates([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, conversationId]);

  const handleSelect = (t: WhatsAppTemplate) => {
    const params = Array.isArray(t.body_parameters_default) ? t.body_parameters_default : [];
    onSelectTemplate(t.id, params);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="template-picker-modal-title">
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 id="template-picker-modal-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Enviar por template
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="px-4 pt-2 text-sm text-gray-500 dark:text-gray-400">
          Escolha um template aprovado para enviar (ex.: mensagens com botões). Fora da janela de 24h só é possível enviar por template.
        </p>
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
            </div>
          )}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400 py-2">{error}</p>
          )}
          {!loading && !error && templates.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-4">
              Nenhum template disponível. Cadastre templates na configuração (Meta).
            </p>
          )}
          {!loading && templates.length > 0 && (
            <ul className="space-y-2">
              {templates.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(t)}
                    className="w-full flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-left transition"
                  >
                    <FileText className="w-5 h-5 text-indigo-500 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 dark:text-gray-100 truncate">
                        {t.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {t.template_id} · {t.language_code}
                        {t.meta_status ? ` · ${t.meta_status}` : ''}
                      </p>
                      {t.body && (
                        <p className="text-xs text-gray-600 dark:text-gray-300 mt-1 line-clamp-2 break-words">
                          {t.body}
                        </p>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
