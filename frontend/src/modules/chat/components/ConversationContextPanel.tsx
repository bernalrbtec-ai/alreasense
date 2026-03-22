import { useEffect } from 'react';
import { X, ArrowRightLeft, XCircle, ClipboardList, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { Conversation } from '../types';
import {
  getConversationStatusPresentation,
  STATUS_CHIP_VARIANT_CLASSES,
} from '../utils/conversationStatusPresentation';

export interface ConversationContextPanelProps {
  open: boolean;
  onClose: () => void;
  conversation: Conversation | null;
  activeAgentName?: string | null;
  onTransfer: () => void;
  onCloseConversation: () => void;
  onCreateTask: () => void;
  canTransfer: boolean;
  showCloseConversation?: boolean;
}

export function ConversationContextPanel({
  open,
  onClose,
  conversation,
  activeAgentName,
  onTransfer,
  onCloseConversation,
  onCreateTask,
  canTransfer,
  showCloseConversation = true,
}: ConversationContextPanelProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const pres = conversation
    ? getConversationStatusPresentation(conversation, { activeAgentName: activeAgentName ?? null })
    : null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-[40] bg-black/40 md:hidden"
        aria-label="Fechar painel"
        onClick={onClose}
      />
      <aside
        className="fixed md:relative inset-y-0 right-0 z-[45] md:z-auto w-full max-w-md md:max-w-none md:w-[min(380px,36vw)] md:flex-shrink-0 flex flex-col bg-white dark:bg-gray-900 md:bg-chat-sidebar border-l border-gray-200 dark:border-gray-700 shadow-2xl md:shadow-none animate-fade-in max-h-full"
        aria-label="Contexto da conversa"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Contexto</h3>
          <Button type="button" variant="ghost" size="icon" className="rounded-full h-8 w-8" aria-label="Fechar" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-4 text-sm min-h-0">
          {conversation ? (
            <>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Conversa</p>
                <p className="font-medium text-gray-900 dark:text-gray-100 truncate">
                  {conversation.contact_name || conversation.contact_phone || '—'}
                </p>
                {pres && (
                  <span
                    className={`inline-flex mt-2 items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${STATUS_CHIP_VARIANT_CLASSES[pres.variant]}`}
                  >
                    {pres.label}
                  </span>
                )}
              </div>

              <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 p-3 bg-gray-50/80 dark:bg-gray-800/50">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 flex items-center gap-1">
                  <ClipboardList className="w-3.5 h-3.5" aria-hidden />
                  Tickets por conversa
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  Em breve: listagem quando a API estiver disponível.
                </p>
                <Button type="button" variant="outline" size="sm" className="w-full gap-1.5 text-xs" onClick={onCreateTask}>
                  <ClipboardList className="w-3.5 h-3.5" />
                  Nova tarefa
                </Button>
              </div>

              <div className="flex flex-col gap-2">
                {canTransfer && (
                  <Button type="button" variant="outline" className="w-full justify-start gap-2" onClick={onTransfer}>
                    <ArrowRightLeft className="w-4 h-4" />
                    Transferir conversa
                  </Button>
                )}
                {showCloseConversation && conversation.conversation_type !== 'group' && (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full justify-start gap-2 text-red-600 border-red-200 hover:bg-red-50 dark:border-red-900/50 dark:hover:bg-red-950/30"
                    onClick={onCloseConversation}
                  >
                    <XCircle className="w-4 h-4" />
                    Fechar conversa
                  </Button>
                )}
              </div>
            </>
          ) : (
            <p className="text-gray-500 dark:text-gray-400 text-xs">Nenhuma conversa selecionada.</p>
          )}

          <a
            href="/tasks"
            className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
          >
            Abrir tarefas
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </aside>
    </>
  );
}
