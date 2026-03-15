/**
 * Balão de mensagem para o painel de chat (spec).
 */

import React from 'react';
import { clsx } from 'clsx';
import type { ChatPanelMessage } from './adapters';
import { Check, CheckCheck } from 'lucide-react';
import { formatTimeRelative } from '@/utils/formatTime';

interface MessageBubbleProps {
  message: ChatPanelMessage;
}

function StatusIcon({ status }: { status: ChatPanelMessage['status'] }) {
  if (status === 'read') {
    return <CheckCheck className="w-3.5 h-3.5 text-blue-500" aria-hidden />;
  }
  if (status === 'delivered' || status === 'sent') {
    return <CheckCheck className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500" aria-hidden />;
  }
  return <Check className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500" aria-hidden />;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isOutbound = message.direction === 'outbound';

  return (
    <div
      className={clsx(
        'flex max-w-[85%]',
        isOutbound ? 'ml-auto' : 'mr-auto'
      )}
    >
      <div
        className={clsx(
          'px-3 py-2 shadow-sm',
          isOutbound
            ? 'rounded-tl-2xl rounded-tr-2xl rounded-bl-2xl rounded-br-sm bg-blue-600 text-white'
            : 'rounded-tl-2xl rounded-tr-2xl rounded-br-2xl rounded-bl-sm bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100'
        )}
      >
        {message.content ? (
          <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
        ) : null}
        <div className="flex items-center justify-end gap-1 mt-1 opacity-60">
          <span className="text-[10px]">
            {message.sentAt ? formatTimeRelative(message.sentAt) : ''}
          </span>
          {isOutbound && (
            <span className="ml-0.5">
              <StatusIcon status={message.status} />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
