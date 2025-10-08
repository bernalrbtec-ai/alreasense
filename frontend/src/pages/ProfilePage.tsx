import { useState, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import { api } from '../lib/api'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { 
  User, 
  Mail, 
  Phone, 
  Calendar, 
  Edit, 
  Save, 
  Lock, 
  Camera,
  X
} from 'lucide-react'

interface ProfileData {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name: string
  phone: string
  birth_date: string
  avatar?: string
}

interface PasswordData {
  current_password: string
  new_password: string
  confirm_password: string
}

export default function ProfilePage() {
  const { user, setUser } = useAuthStore()
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  
  const [profileData, setProfileData] = useState<ProfileData>({
    id: '',
    email: '',
    first_name: '',
    last_name: '',
    display_name: '',
    phone: '',
    birth_date: '',
    avatar: '',
  })
  const [passwordData, setPasswordData] = useState<PasswordData>({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })

  useEffect(() => {
    if (user) {
      setProfileData({
        id: user.id || '',
        email: user.email || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        display_name: user.display_name || '',
        phone: user.phone || '',
        birth_date: user.birth_date || '',
        avatar: user.avatar || '',
      })
    }
  }, [user])

  // Debug avatar
  useEffect(() => {
    console.log('🔍 Profile data updated:', profileData)
    console.log('🔍 User data:', user)
    console.log('🔍 Avatar URL:', profileData.avatar)
  }, [profileData, user])

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setIsSaving(true)
      setMessage(null)

      console.log('🔍 Updating profile with data:', {
        first_name: profileData.first_name,
        last_name: profileData.last_name,
        email: profileData.email,
        display_name: profileData.display_name,
        phone: profileData.phone,
        birth_date: profileData.birth_date,
      })

      const response = await api.patch('/auth/profile/', {
        first_name: profileData.first_name,
        last_name: profileData.last_name,
        email: profileData.email,
        display_name: profileData.display_name,
        phone: profileData.phone,
        birth_date: profileData.birth_date,
      })

      console.log('✅ Profile update response:', response.data)

      // Update user in store
      console.log('🔍 Updating user in store with:', response.data)
      setUser(response.data)
      console.log('✅ User updated in store')

      setMessage({ type: 'success', text: 'Perfil atualizado com sucesso!' })
      handleCloseEditModal()
    } catch (error: any) {
      console.error('❌ Error updating profile:', error)
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      })
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || 'Erro ao atualizar perfil' 
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (passwordData.new_password !== passwordData.confirm_password) {
      setMessage({ type: 'error', text: 'As senhas não coincidem' })
      return
    }

    try {
      setIsSaving(true)
      setMessage(null)

      await api.post('/auth/change-password/', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      })

      setMessage({ type: 'success', text: 'Senha alterada com sucesso!' })
      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: '',
      })
    } catch (error: any) {
      console.error('Error changing password:', error)
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || 'Erro ao alterar senha' 
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const formData = new FormData()
      formData.append('avatar', file)

      const response = await api.post('/auth/avatar/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setProfileData({ ...profileData, avatar: response.data.avatar })
      setUser({ ...user, avatar: response.data.avatar })
      setMessage({ type: 'success', text: 'Avatar atualizado com sucesso!' })
    } catch (error: any) {
      console.error('Error uploading avatar:', error)
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || 'Erro ao fazer upload do avatar' 
      })
    }
  }

  const handleOpenEditModal = () => {
    setIsEditModalOpen(true)
  }

  const handleCloseEditModal = () => {
    setIsEditModalOpen(false)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-4 rounded-md ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-800 border border-green-200' 
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Profile Modal */}
      <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
        <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white">
          <div className="mt-3">
            {/* Header with Account Type and Status */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900">Perfil do Usuário</h3>
                <div className="flex items-center gap-4 mt-2">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    {user?.role === 'admin' ? 'Administrador' : 'Operador'}
                  </span>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    user?.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {user?.is_active ? 'Ativo' : 'Inativo'}
                  </span>
                  {user?.is_superuser && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                      Super Admin
                    </span>
                  )}
                </div>
              </div>
              <Button 
                variant="outline"
                onClick={() => window.history.back()}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Profile Information */}
            <div className="flex items-center gap-6 mb-6">
              <div className="relative">
                <div className="h-24 w-24 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-3xl font-bold overflow-hidden">
                  {profileData.avatar ? (
                    <img 
                      src={profileData.avatar} 
                      alt="Avatar" 
                      className="h-full w-full object-cover"
                      onError={(e) => {
                        console.log('❌ Avatar image failed to load:', profileData.avatar)
                        e.currentTarget.style.display = 'none'
                      }}
                    />
                  ) : (
                    <span>
                      {profileData.first_name?.[0]?.toUpperCase() || profileData.email?.[0]?.toUpperCase() || 'U'}
                    </span>
                  )}
                </div>
                <label 
                  htmlFor="avatar-upload" 
                  className="absolute bottom-0 right-0 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-2 cursor-pointer shadow-lg transition-colors"
                >
                  <Camera className="h-4 w-4" />
                  <input
                    id="avatar-upload"
                    type="file"
                    accept="image/*"
                    onChange={handleAvatarUpload}
                    className="hidden"
                  />
                </label>
              </div>
              
              <div className="flex-1">
                <h2 className="text-2xl font-bold text-gray-900">
                  {profileData.display_name || `${profileData.first_name} ${profileData.last_name}`.trim() || 'Usuário'}
                </h2>
                <p className="text-gray-600">{profileData.email}</p>
                <Button 
                  onClick={handleOpenEditModal}
                  className="mt-2"
                >
                  <Edit className="h-4 w-4 mr-2" />
                  Editar Perfil
                </Button>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  <User className="h-4 w-4 inline mr-1" />
                  Nome Completo
                </label>
                <p className="mt-1 text-sm text-gray-900">
                  {profileData.first_name} {profileData.last_name}
                </p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  <Mail className="h-4 w-4 inline mr-1" />
                  Email
                </label>
                <p className="mt-1 text-sm text-gray-900">{profileData.email}</p>
              </div>
              
              {profileData.phone && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    <Phone className="h-4 w-4 inline mr-1" />
                    Telefone
                  </label>
                  <p className="mt-1 text-sm text-gray-900">{profileData.phone}</p>
                </div>
              )}
              
              {profileData.birth_date && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    <Calendar className="h-4 w-4 inline mr-1" />
                    Data de Nascimento
                  </label>
                  <p className="mt-1 text-sm text-gray-900">
                    {new Date(profileData.birth_date).toLocaleDateString('pt-BR')}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Change Password */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          <Lock className="h-5 w-5 inline mr-2" />
          Alterar Senha
        </h3>
        
        <form onSubmit={handlePasswordSubmit} className="space-y-4">
          <div>
            <label htmlFor="current_password" className="block text-sm font-medium text-gray-700">
              Senha Atual
            </label>
            <input
              type="password"
              id="current_password"
              value={passwordData.current_password}
              onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
              placeholder="Digite sua senha atual"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="new_password" className="block text-sm font-medium text-gray-700">
                Nova Senha
              </label>
              <input
                type="password"
                id="new_password"
                value={passwordData.new_password}
                onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                placeholder="Digite a nova senha"
                required
              />
            </div>
            <div>
              <label htmlFor="confirm_password" className="block text-sm font-medium text-gray-700">
                Confirmar Senha
              </label>
              <input
                type="password"
                id="confirm_password"
                value={passwordData.confirm_password}
                onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                placeholder="Confirme a nova senha"
                required
              />
            </div>
          </div>

          <Button type="submit" disabled={isSaving}>
            <Lock className={`h-4 w-4 mr-2 ${isSaving ? 'animate-pulse' : ''}`} />
            {isSaving ? 'Alterando...' : 'Alterar Senha'}
          </Button>
        </form>
      </Card>

      {/* Edit Profile Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Editar Perfil</h3>
                <Button variant="outline" onClick={handleCloseEditModal}>
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <form onSubmit={handleProfileSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="first_name" className="block text-sm font-medium text-gray-700">
                      Nome
                    </label>
                    <input
                      type="text"
                      id="first_name"
                      value={profileData.first_name}
                      onChange={(e) => setProfileData({ ...profileData, first_name: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      placeholder="Seu nome"
                      required
                    />
                  </div>

                  <div>
                    <label htmlFor="last_name" className="block text-sm font-medium text-gray-700">
                      Sobrenome
                    </label>
                    <input
                      type="text"
                      id="last_name"
                      value={profileData.last_name}
                      onChange={(e) => setProfileData({ ...profileData, last_name: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      placeholder="Seu sobrenome"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="display_name" className="block text-sm font-medium text-gray-700">
                    Nome de Exibição
                  </label>
                  <input
                    type="text"
                    id="display_name"
                    value={profileData.display_name}
                    onChange={(e) => setProfileData({ ...profileData, display_name: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    placeholder="Como você quer ser chamado"
                  />
                </div>

                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                    Email
                  </label>
                  <input
                    type="email"
                    id="email"
                    value={profileData.email}
                    onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    placeholder="seu@email.com"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="phone" className="block text-sm font-medium text-gray-700">
                      <Phone className="h-4 w-4 inline mr-1" />
                      Telefone
                    </label>
                    <input
                      type="tel"
                      id="phone"
                      value={profileData.phone}
                      onChange={(e) => setProfileData({ ...profileData, phone: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      placeholder="(11) 99999-9999"
                    />
                  </div>

                  <div>
                    <label htmlFor="birth_date" className="block text-sm font-medium text-gray-700">
                      <Calendar className="h-4 w-4 inline mr-1" />
                      Data de Nascimento
                    </label>
                    <input
                      type="date"
                      id="birth_date"
                      value={profileData.birth_date}
                      onChange={(e) => setProfileData({ ...profileData, birth_date: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    />
                  </div>
                </div>
              </form>

              <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
                <Button type="submit" disabled={isSaving} onClick={handleProfileSubmit}>
                  <Save className={`h-4 w-4 mr-2 ${isSaving ? 'animate-pulse' : ''}`} />
                  {isSaving ? 'Salvando...' : 'Salvar Alterações'}
                </Button>
                <Button type="button" variant="outline" onClick={handleCloseEditModal}>
                  Cancelar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}