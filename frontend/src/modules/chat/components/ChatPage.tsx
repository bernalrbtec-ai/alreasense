/**
 * Página principal do Flow Chat
 */
import React from 'react';
import { DepartmentTabs } from './DepartmentTabs';
import { ConversationList } from './ConversationList';
import { ChatWindow } from './ChatWindow';
import { MessageSquare } from 'lucide-react';

export function ChatPage() {
  return (
    <div className="flex flex-col h-screen bg-[#0e1115]">
      {/* Header com Logo + Departamentos */}
      <div className="flex-shrink-0">
        <div className="flex items-center gap-3 px-6 py-4 bg-[#1f262e] border-b border-gray-800">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-6 h-6 text-green-500" />
            <h1 className="text-xl font-bold text-white">Flow Chat</h1>
          </div>
        </div>
        
        <DepartmentTabs />
      </div>

      {/* Content: Conversations + Chat Window */}
      <div className="flex flex-1 overflow-hidden">
        <ConversationList />
        <ChatWindow />
      </div>
    </div>
  );
}

