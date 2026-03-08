/**
 * Modal de opções da lista interativa (estilo WhatsApp).
 * Exibe título (button_text), seções/rows e footer; somente leitura.
 * Bloqueia scroll do body quando aberto; anima entrada e saída.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { X } from 'lucide-react';

const CLOSE_ANIMATION_MS = 200;

export interface InteractiveListSection {
  title?: string;
  rows?: Array<{ id?: string; title?: string; description?: string }>;
}

interface InteractiveListModalProps {
  title: string;
  sections: InteractiveListSection[];
  footer?: string;
  onClose: () => void;
}

export function InteractiveListModal({ title, sections, footer, onClose }: InteractiveListModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleClose = useCallback(() => {
    if (isClosing) return;
    setIsClosing(true);
    setIsVisible(false);
    closeTimeoutRef.current = setTimeout(() => {
      closeTimeoutRef.current = null;
      onClose();
    }, CLOSE_ANIMATION_MS);
  }, [onClose, isClosing]);

  useEffect(() => {
    const t = requestAnimationFrame(() => setIsVisible(true));
    return () => cancelAnimationFrame(t);
  }, []);

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
      if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [handleClose]);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      closeButtonRef.current?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, []);

  const show = isVisible && !isClosing;
  const hasAnyRows = sections.some((sec) => Array.isArray(sec.rows) && sec.rows.length > 0);

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/50 transition-opacity duration-200 ${show ? 'opacity-100' : 'opacity-0'}`}
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="interactive-list-modal-title"
    >
      <div
        className={`bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-600 w-full max-w-md mx-4 max-h-[90vh] overflow-hidden flex flex-col transition-all duration-200 ${show ? 'opacity-100 scale-100 translate-y-0' : 'opacity-0 scale-95 translate-y-2'}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-600 flex-shrink-0">
          <h2 id="interactive-list-modal-title" className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate flex-1 min-w-0">
            {title || 'Opções'}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={handleClose}
            className="flex-shrink-0 p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-green-500/50"
            aria-label="Fechar"
          >
            <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-3 overflow-y-auto flex-1 max-h-[70vh]">
          {!hasAnyRows ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Nenhuma opção</p>
          ) : (
            <div className="space-y-3">
              {sections.map((sec, si) => {
                const rows = Array.isArray(sec.rows) ? sec.rows : [];
                if (rows.length === 0) return null;
                return (
                  <div key={si}>
                    {sec.title ? (
                      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">{sec.title}</p>
                    ) : null}
                    <ul className="divide-y divide-gray-100 dark:divide-gray-700 rounded-lg border border-gray-100 dark:border-gray-700 overflow-hidden">
                      {rows.map((row, ri) => {
                        const rowTitle = (row.title ?? row.id ?? '').toString().trim() || '—';
                        return (
                          <li key={ri} className="px-3 py-2.5 text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800/50">
                            <span className="font-medium">{rowTitle}</span>
                            {row.description ? (
                              <span className="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">{row.description}</span>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {footer ? (
          <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-700 flex-shrink-0">
            <p className="text-xs text-gray-500 dark:text-gray-400">{footer}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
