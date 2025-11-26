import React, { useEffect, useState } from 'react';
import { User, Phone, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { showErrorToast } from '@/lib/toastHelper';

interface SharedContactCardProps {
  contactData: {
    name?: string;
    display_name?: string;
    phone?: string;
  };
  content?: string;
  onAddContact: (contact: { name: string; phone: string }) => void;
}

export function SharedContactCard({ contactData, content, onAddContact }: SharedContactCardProps) {
  const navigate = useNavigate();
  const { setActiveConversation, addConversation } = useChatStore();
  
  // Extrair dados do contato
  let phone = contactData?.phone || '';
  let name = contactData?.name || contactData?.display_name || '';
  
  // Se não tem dados no metadata, tentar extrair do conteúdo
  if (!name && !phone && content) {
    const match = content.match(/Compartilhou contato:\s*(.+)/i);
    if (match) {
      name = match[1].trim();
    }
  }
  
  // Se ainda não tem nome, usar fallback
  if (!name) {
    name = 'Contato';
  }
  
  // Formatar telefone para exibição
  const formatPhone = (phone: string) => {
    if (!phone) return '';
    let clean = phone.replace(/[^\d+]/g, '');
    
    if (clean.startsWith('+55')) {
      clean = clean.substring(3);
    } else if (clean.startsWith('55') && clean.length >= 12) {
      clean = clean.substring(2);
    }
    
    if (clean.length === 11) {
      return `(${clean.substring(0, 2)}) ${clean.substring(2, 7)}-${clean.substring(7)}`;
    } else if (clean.length === 10) {
      return `(${clean.substring(0, 2)}) ${clean.substring(2, 6)}-${clean.substring(6)}`;
    }
    
    return phone;
  };
  
  const formattedPhone = phone ? formatPhone(phone) : '';
  const cleanPhoneForSearch = phone ? phone.replace(/[^\d]/g, '') : '';
  
  // Estado para contato cadastrado (quando existe)
  const [savedContact, setSavedContact] = useState<{
    name: string;
    tags: Array<{ id: string; name: string; color: string }>;
  } | null>(null);
  const [isCheckingContact, setIsCheckingContact] = useState(false);
  
  // Verificar se contato já existe na agenda e buscar dados completos
  useEffect(() => {
    if (!cleanPhoneForSearch) return;
    
    const checkContactExists = async () => {
      setIsCheckingContact(true);
      try {
        const response = await api.get(`/contacts/contacts/?search=${encodeURIComponent(cleanPhoneForSearch)}`);
        const contacts = response.data.results || response.data || [];
        
        // Encontrar contato que corresponde ao telefone
        const foundContact = contacts.find((contact: any) => {
          const contactPhone = contact.phone?.replace(/[^\d]/g, '') || '';
          return contactPhone === cleanPhoneForSearch || 
                 contactPhone === `55${cleanPhoneForSearch}` ||
                 contactPhone === `+55${cleanPhoneForSearch}`;
        });
        
        if (foundContact) {
          // Contato existe - salvar dados completos
          setSavedContact({
            name: foundContact.name,
            tags: foundContact.tags || []
          });
        } else {
          // Contato não existe
          setSavedContact(null);
        }
      } catch (error) {
        console.error('Erro ao verificar contato:', error);
        setSavedContact(null);
      } finally {
        setIsCheckingContact(false);
      }
    };
    
    checkContactExists();
  }, [cleanPhoneForSearch]);
  
  // Abrir conversa dentro da aplicação
  const handleStartConversation = async () => {
    if (!cleanPhoneForSearch) {
      showErrorToast('Telefone inválido');
      return;
    }
    
    try {
      const normalizedPhone = cleanPhoneForSearch.startsWith('55') 
        ? `+${cleanPhoneForSearch}` 
        : `+55${cleanPhoneForSearch}`;
      
      // Buscar conversa existente por telefone
      const response = await api.get('/chat/conversations/', {
        params: { search: normalizedPhone }
      });
      
      const conversations = response.data.results || response.data || [];
      let conversation = conversations.find((conv: any) => 
        conv.contact_phone?.replace(/[^\d]/g, '') === cleanPhoneForSearch ||
        conv.contact_phone?.replace(/[^\d]/g, '') === `55${cleanPhoneForSearch}`
      );
      
      // Se não encontrou, criar nova conversa
      if (!conversation) {
        const createResponse = await api.post('/chat/conversations/', {
          contact_phone: normalizedPhone,
          contact_name: name,
          status: 'open'
        });
        conversation = createResponse.data;
        addConversation(conversation);
      }
      
      // Navegar para o chat e selecionar a conversa
      setActiveConversation(conversation);
      
      // Se não estiver na página de chat, navegar
      if (window.location.pathname !== '/chat') {
        navigate('/chat');
      }
    } catch (error: any) {
      console.error('Erro ao iniciar conversa:', error);
      showErrorToast(error.response?.data?.detail || 'Erro ao iniciar conversa');
    }
  };
  
  const handleAddContact = () => {
    onAddContact({ name, phone: cleanPhoneForSearch || phone });
  };
  
  // Dados a exibir: se contato existe, usar dados salvos; senão, usar dados do card
  const displayName = savedContact ? savedContact.name : name;
  const displayPhone = formattedPhone;
  const displayTags = savedContact?.tags || [];
  const contactExists = savedContact !== null;
  
  return (
    <div className="mb-2 border border-gray-200 rounded-lg p-3 bg-white shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center shadow-sm">
          <User className="w-6 h-6 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-gray-500 mb-2 font-medium">📇 Contato compartilhado</div>
          <div className="font-semibold text-gray-900 mb-1 text-base">{displayName}</div>
          
          {/* Mostrar telefone apenas se contato não existir (dados do card) */}
          {!contactExists && displayPhone && (
            <div className="text-sm text-gray-600 mb-3 flex items-center gap-1">
              <Phone className="w-3.5 h-3.5" />
              <span>{displayPhone}</span>
            </div>
          )}
          
          {/* Mostrar tags se contato existir */}
          {contactExists && displayTags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {displayTags.map((tag) => (
                <span
                  key={tag.id}
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                  style={{
                    backgroundColor: `${tag.color}20`,
                    color: tag.color,
                    border: `1px solid ${tag.color}40`
                  }}
                >
                  {tag.name}
                </span>
              ))}
            </div>
          )}
          
          <div className="flex gap-2 flex-wrap">
            {isCheckingContact && (
              <span className="text-xs text-gray-500">Verificando...</span>
            )}
            
            {!isCheckingContact && cleanPhoneForSearch && (
              <button
                onClick={handleStartConversation}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors shadow-sm hover:shadow-md"
              >
                <Phone className="w-4 h-4" />
                Iniciar conversa
              </button>
            )}
            
            {/* Só mostrar "Adicionar" se contato não existir */}
            {!isCheckingContact && !contactExists && cleanPhoneForSearch && (
              <button
                onClick={handleAddContact}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors shadow-sm hover:shadow-md"
              >
                <Plus className="w-4 h-4" />
                Adicionar aos contatos
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

