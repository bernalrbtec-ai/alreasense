import type { Message } from '../types';

export type HubBubbleRun = 'first' | 'mid' | 'last' | 'single';

export type DisplayItemBase =
  | { type: 'message'; message: Message; isGroupStart: boolean; hubRun?: HubBubbleRun }
  | { type: 'transfer_merged'; messages: Message[]; mergedContent: string }
  | { type: 'date_separator'; dayKey: string; label: string };

function eligibleForHubBubbleGroup(m: Message): boolean {
  if (m.is_deleted) return false;
  if (m.is_internal) return false;
  if (m.direction !== 'incoming' && m.direction !== 'outgoing') return false;
  return true;
}

/**
 * Marca mensagens consecutivas (1:1) com hubRun para cantos colados e espaçamento reduzido.
 */
export function applyHubBubbleRuns(
  items: DisplayItemBase[],
  enabled: boolean,
  conversationType: 'individual' | 'group' | 'broadcast' | undefined
): DisplayItemBase[] {
  if (!enabled || conversationType !== 'individual') {
    return items.map((it) => (it.type === 'message' ? { ...it, hubRun: undefined } : it));
  }

  const result: DisplayItemBase[] = [];
  let i = 0;
  while (i < items.length) {
    const it = items[i];
    if (it.type !== 'message' || !eligibleForHubBubbleGroup(it.message)) {
      if (it.type === 'message') {
        result.push({ ...it, hubRun: 'single' });
      } else {
        result.push(it);
      }
      i++;
      continue;
    }

    const runIndices: number[] = [i];
    let j = i + 1;
    while (j < items.length) {
      const next = items[j];
      if (next.type !== 'message' || !eligibleForHubBubbleGroup(next.message)) break;
      const prevMsg = (items[runIndices[runIndices.length - 1]] as Extract<DisplayItemBase, { type: 'message' }>)
        .message;
      if (next.message.direction !== prevMsg.direction) break;
      if (next.message.direction === 'outgoing') {
        if (
          Boolean(next.message.metadata?.from_ai_agent) !== Boolean(prevMsg.metadata?.from_ai_agent)
        ) {
          break;
        }
      }
      runIndices.push(j);
      j++;
    }

    if (runIndices.length === 1) {
      const orig = items[runIndices[0]] as Extract<DisplayItemBase, { type: 'message' }>;
      result.push({ ...orig, hubRun: 'single' });
    } else {
      for (let k = 0; k < runIndices.length; k++) {
        const orig = items[runIndices[k]] as Extract<DisplayItemBase, { type: 'message' }>;
        const hubRun: HubBubbleRun =
          k === 0 ? 'first' : k === runIndices.length - 1 ? 'last' : 'mid';
        result.push({ ...orig, hubRun });
      }
    }
    i = j;
  }
  return result;
}
