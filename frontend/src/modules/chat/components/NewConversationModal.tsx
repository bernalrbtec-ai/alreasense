import { useState, useEffect, useCallback } from 'react';
import { X, Search, User, Phone, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { showErrorToast } from '@/lib/toastHelper';

interface Contact {
  id: string;
  name: string;
  phone: string;
  tags?: Array<{ id: string; name: string; color: string }>;
}

interface NewConversationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NewConversationModal({ isOpen, onClose }: NewConversationModalProps) {
  const { setActiveConversation, addConversation } = useChatStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [phoneInput, setPhoneInput] = useState('');
  const [isValidPhone, setIsValidPhone] = useState(false);

  // Detectar se query é telefone ou nome
  const isPhoneQuery = useCallback((query: string): boolean => {
    // Remove espaços, parênteses, hífens e outros caracteres
    const clean = query.replace(/[\s\(\)\-\+]/g, '');
    // Se tem mais de 5 dígitos, provavelmente é telefone
    return /^\d{6,}$/.test(clean);
  }, []);

  // Normalizar telefone para formato padrão
  const normalizePhone = useCallback((phone: string): string => {
    // Remove tudo exceto dígitos e +
    let clean = phone.replace(/[^\d+]/g, '');
    
    // Se não começa com +, adicionar +55 (Brasil)
    if (!clean.startsWith('+')) {
      // Se começa com 55, adicionar +
      if (clean.startsWith('55')) {
        clean = '+' + clean;
      } else {
        // Adicionar +55 para números brasileiros
        clean = '+55' + clean;
      }
    }
    
    return clean;
  }, []);

  // Validar telefone
  const validatePhone = useCallback((phone: string): boolean => {
    const normalized = normalizePhone(phone);
    // Telefone válido: +55 seguido de 10 ou 11 dígitos (DDD + número)
    // Ex: +5517999999999 (13 dígitos) ou +5511999999999 (13 dígitos)
    return /^\+55\d{10,11}$/.test(normalized);
  }, [normalizePhone]);

  // Buscar contatos
  useEffect(() => {
    if (!isOpen) {
      setSearchQuery('');
      setContacts([]);
      setPhoneInput('');
      setIsValidPhone(false);
      return;
    }

    const searchContacts = async () => {
      if (!searchQuery || searchQuery.length < 2) {
        setContacts([]);
        return;
      }

      setIsSearching(true);
      try {
        const response = await api.get('/contacts/contacts/', {
          params: { search: searchQuery, page_size: 10 }
        });
        const results = response.data.results || response.data || [];
        setContacts(Array.isArray(results) ? results : []);
      } catch (error) {
        console.error('Erro ao buscar contatos:', error);
        setContacts([]);
      } finally {
        setIsSearching(false);
      }
    };

    // Debounce de 300ms
    const timeoutId = setTimeout(searchContacts, 300);
    return () => clearTimeout(timeoutId);
  }, [searchQuery, isOpen]);

  // Validar telefone quando mudar
  useEffect(() => {
    if (phoneInput && isPhoneQuery(phoneInput)) {
      const valid = validatePhone(phoneInput);
      setIsValidPhone(valid);
    } else {
      setIsValidPhone(false);
    }
  }, [phoneInput, isPhoneQuery, validatePhone]);

  // Iniciar conversa com contato
  const handleStartConversation = async (contact: Contact) => {
    try {
      setIsCreating(true);
      const normalizedPhone = normalizePhone(contact.phone);
      
      // Verificar se conversa já existe
      const response = await api.get('/chat/conversations/', {
        params: { search: normalizedPhone }
      });
      
      const conversations = response.data.results || response.data || [];
      let conversation = conversations.find((conv: any) => {
        const convPhone = conv.contact_phone?.replace(/[^\d]/g, '') || '';
        const contactPhone = contact.phone.replace(/[^\d]/g, '') || '';
        return convPhone === contactPhone || 
               convPhone === `55${contactPhone}` ||
               convPhone === `+55${contactPhone}`;
      });
      
      // Se não encontrou, criar nova conversa
      if (!conversation) {
        // ✅ CORREÇÃO: Usar endpoint /start/ que tem broadcast configurado
        const createResponse = await api.post('/chat/conversations/start/', {
          contact_phone: normalizedPhone,
          contact_name: contact.name
        });
        conversation = createResponse.data.conversation || createResponse.data;
        // ✅ IMPORTANTE: Adicionar ao store para aparecer na lista
        addConversation(conversation);
      }
      
      // ✅ CORREÇÃO CRÍTICA: Selecionar conversa como ativa
      // Isso garante que a conversa apareça no chat e seja setada como ativa
      setActiveConversation(conversation);
      onClose();
    } catch (error: any) {
      console.error('Erro ao iniciar conversa:', error);
      showErrorToast('iniciar', 'Conversa', error);
    } finally {
      setIsCreating(false);
    }
  };

  // Iniciar conversa com telefone direto
  const handleStartConversationWithPhone = async () => {
    if (!isValidPhone) return;

    try {
      setIsCreating(true);
      const normalizedPhone = normalizePhone(phoneInput);
      
      // Verificar se conversa já existe
      const response = await api.get('/chat/conversations/', {
        params: { search: normalizedPhone }
      });
      
      const conversations = response.data.results || response.data || [];
      let conversation = conversations.find((conv: any) => {
        const convPhone = conv.contact_phone?.replace(/[^\d]/g, '') || '';
        const searchPhone = normalizedPhone.replace(/[^\d]/g, '') || '';
        return convPhone === searchPhone || 
               convPhone === `55${searchPhone}` ||
               convPhone === `+55${searchPhone}`;
      });
      
      // Se não encontrou, criar nova conversa
      if (!conversation) {
        // ✅ CORREÇÃO: Usar endpoint /start/ que tem broadcast configurado
        const createResponse = await api.post('/chat/conversations/start/', {
          contact_phone: normalizedPhone,
          contact_name: normalizedPhone // Usar telefone como nome se não tiver contato
        });
        conversation = createResponse.data.conversation || createResponse.data;
        // ✅ IMPORTANTE: Adicionar ao store para aparecer na lista
        addConversation(conversation);
      }
      
      // ✅ CORREÇÃO CRÍTICA: Selecionar conversa como ativa
      // Isso garante que a conversa apareça no chat e seja setada como ativa
      setActiveConversation(conversation);
      onClose();
    } catch (error: any) {
      console.error('Erro ao iniciar conversa:', error);
      showErrorToast('iniciar', 'Conversa', error);
    } finally {
      setIsCreating(false);
    }
  };

  // Formatar telefone para exibição
  const formatPhone = (phone: string): string => {
    let clean = phone.replace(/[^\d]/g, '');
    
    if (clean.startsWith('55') && clean.length >= 12) {
      clean = clean.substring(2);
    }
    
    if (clean.length === 11) {
      return `(${clean.substring(0, 2)}) ${clean.substring(2, 7)}-${clean.substring(7)}`;
    } else if (clean.length === 10) {
      return `(${clean.substring(0, 2)}) ${clean.substring(2, 6)}-${clean.substring(6)}`;
    }
    
    return phone;
  };

  if (!isOpen) return null;

  const isPhone = isPhoneQuery(searchQuery);
  const showPhoneOption = isPhone && isValidPhone && contacts.length === 0;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-bold">Nova Conversa</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Search Input */}
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar por nome ou telefone..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                if (isPhoneQuery(e.target.value)) {
                  setPhoneInput(e.target.value);
                }
              }}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              autoFocus
            />
            {isSearching && (
              <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400 animate-spin" />
            )}
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-4">
          {searchQuery.length < 2 ? (
            <div className="text-center py-8 text-gray-500">
              <Search className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>Digite um nome ou telefone para buscar</p>
            </div>
          ) : contacts.length > 0 ? (
            <div className="space-y-2">
              {contacts.map((contact) => (
                <button
                  key={contact.id}
                  onClick={() => handleStartConversation(contact)}
                  disabled={isCreating}
                  className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 rounded-lg transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
                    <User className="h-5 w-5 text-gray-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 truncate">{contact.name}</div>
                    <div className="text-sm text-gray-500 flex items-center gap-1">
                      <Phone className="h-3 w-3" />
                      <span>{formatPhone(contact.phone)}</span>
                    </div>
                    {contact.tags && contact.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {contact.tags.slice(0, 2).map((tag) => (
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
                        {contact.tags.length > 2 && (
                          <span className="text-xs text-gray-500">+{contact.tags.length - 2}</span>
                        )}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          ) : showPhoneOption ? (
            <div className="text-center py-8">
              <div className="mb-4">
                <Phone className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <p className="text-gray-600 mb-2">Nenhum contato encontrado</p>
                <p className="text-sm text-gray-500 mb-4">
                  Iniciar conversa com <strong>{formatPhone(phoneInput)}</strong>
                </p>
              </div>
              <button
                onClick={handleStartConversationWithPhone}
                disabled={isCreating || !isValidPhone}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
              >
                {isCreating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Criando...</span>
                  </>
                ) : (
                  <>
                    <Phone className="h-4 w-4" />
                    <span>Iniciar Conversa</span>
                  </>
                )}
              </button>
            </div>
          ) : isSearching ? (
            <div className="text-center py-8">
              <Loader2 className="h-8 w-8 mx-auto mb-4 text-gray-400 animate-spin" />
              <p className="text-gray-500">Buscando...</p>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>Nenhum resultado encontrado</p>
              {isPhone && !isValidPhone && (
                <p className="text-sm text-red-500 mt-2">Telefone inválido</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

