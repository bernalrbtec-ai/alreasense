/**
 * Página principal do Flow Chat - Estilo WhatsApp Web
 * Layout tela cheia responsivo (100vh x 100vw) com sidebar retrátil
 */
import React, { useState } from 'react';
import { DepartmentTabs } from './DepartmentTabs';
import { ConversationList } from './ConversationList';
import { ChatWindow } from './ChatWindow';
import { useChatStore } from '../store/chatStore';
import { useTenantSocket } from '../hooks/useTenantSocket';
import { MessageSquare, ArrowLeft, Menu, LayoutDashboard, Users, Settings, LogOut } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

export function ChatPage() {
  const { activeConversation } = useChatStore();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // 🔌 Conectar WebSocket global do tenant (novas conversas)
  useTenantSocket();
  
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#f0f2f5]">
      {/* Sidebar Retrátil */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-xl transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        md:relative md:translate-x-0
      `}>
        <div className="flex flex-col h-full">
          {/* Logo e Close */}
          <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-6 h-6 text-[#00a884]" />
              <span className="font-bold text-gray-900">Alrea Flow</span>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="md:hidden p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
          </div>

          {/* User Info */}
          <div className="px-4 py-3 border-b border-gray-200">
            <p className="text-sm font-medium text-gray-900">{user?.first_name || user?.email}</p>
            <p className="text-xs text-gray-500">{user?.tenant_name}</p>
          </div>

          {/* Menu */}
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            <Link
              to="/dashboard"
              className="flex items-center gap-3 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <LayoutDashboard className="w-5 h-5" />
              <span className="text-sm font-medium">Dashboard</span>
            </Link>
            <Link
              to="/contacts"
              className="flex items-center gap-3 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Users className="w-5 h-5" />
              <span className="text-sm font-medium">Contatos</span>
            </Link>
            <Link
              to="/campaigns"
              className="flex items-center gap-3 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <MessageSquare className="w-5 h-5" />
              <span className="text-sm font-medium">Campanhas</span>
            </Link>
            <Link
              to="/configurations"
              className="flex items-center gap-3 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Settings className="w-5 h-5" />
              <span className="text-sm font-medium">Configurações</span>
            </Link>
          </nav>

          {/* Logout */}
          <div className="px-3 py-4 border-t border-gray-200">
            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="flex items-center gap-3 w-full px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5" />
              <span className="text-sm font-medium">Sair</span>
            </button>
          </div>
        </div>
      </div>

      {/* Overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header compacto */}
        <div className="flex-shrink-0 bg-[#00a884] px-3 sm:px-4 py-2.5 flex items-center gap-3 shadow-md">
          {/* Menu button */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 hover:bg-white/10 rounded-full transition-colors"
            title="Menu"
          >
            <Menu className="w-5 h-5 text-white" />
          </button>
          
          <MessageSquare className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
          <h1 className="text-white text-base sm:text-lg font-medium">Flow Chat</h1>
        </div>

        {/* Tabs de departamento */}
        <DepartmentTabs />

        {/* Content: Conversations + Chat Window */}
        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Lista de conversas */}
          <div className={`
            ${activeConversation ? 'hidden md:flex' : 'flex'}
            w-full md:w-[350px] lg:w-[380px] xl:w-[420px]
            flex-shrink-0 border-r border-gray-200
          `}>
            <ConversationList />
          </div>
          
          {/* Chat window */}
          <div className={`
            ${activeConversation ? 'flex' : 'hidden md:flex'}
            flex-1 min-w-0
          `}>
            <ChatWindow />
          </div>
        </div>
      </div>
    </div>
  );
}
