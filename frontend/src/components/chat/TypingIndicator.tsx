/**
 * Indicador de digitação: três bolinhas animadas.
 */

import React from 'react';
import { motion } from 'framer-motion';

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-2" aria-live="polite" aria-label="Digitando">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-2 h-2 rounded-full bg-zinc-400 dark:bg-zinc-500"
          animate={{ y: [0, -6, 0] }}
          transition={{
            duration: 0.5,
            repeat: Infinity,
            delay: i * 0.12,
          }}
        />
      ))}
    </div>
  );
}
