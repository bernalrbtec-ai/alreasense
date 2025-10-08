import { useState, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import { api } from '../lib/api'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import { 
  User, 
  Mail, 
  Phone, 
  Calendar, 
  Edit, 
  Save, 
  Lock, 
  X,
  Crown
} from 'lucide-react'

interface ProfileData {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name: string
  phone: string
  birth_date: string
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
  const [isEditing, setIsEditing] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(true)
  
  const [profileData, setProfileData] = useState<ProfileData>({
    id: '',
    email: '',
    first_name: '',
    last_name: '',
    display_name: '',
    phone: '',
    birth_date: '',
  })

  const [passwordData, setPasswordData] = useState<PasswordData>({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })

  // Initialize profile data from user
  useEffect(() => {
    if (user) {
      setProfileData({
        id: user.id.toString(),
        email: user.email || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        display_name: user.display_name || '',
        phone: user.phone || '',
        birth_date: user.birth_date || '',
      })
    }
  }, [user])

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    setMessage(null)

    try {
      console.log('🔍 Updating profile with data:', profileData)
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
      setUser(response.data)
      console.log('✅ User updated in store')
      
      setMessage({ type: 'success', text: 'Perfil atualizado com sucesso!' })
      setIsEditing(false)
    } catch (error: any) {
      console.error('❌ Error updating profile:', error)
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
    setIsSaving(true)
    setMessage(null)

    if (passwordData.new_password !== passwordData.confirm_password) {
      setMessage({ type: 'error', text: 'As senhas não coincidem' })
      setIsSaving(false)
      return
    }

    try {
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
      console.error('❌ Error changing password:', error)
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || 'Erro ao alterar senha' 
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setIsEditing(false)
    // Optionally navigate away or refresh parent if needed
  }

  if (!user) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Meu Perfil</h1>
            <Button variant="ghost" size="icon" onClick={handleCloseModal}>
              <X className="h-5 w-5" />
            </Button>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Gerencie suas informações pessoais e configurações de conta.
          </p>
        </div>

        <div className="p-6 space-y-6">
          {/* User Info Header */}
          <div className="flex items-center gap-4">
            <div className="h-20 w-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold">
              <User className="h-10 w-10" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {profileData.display_name || user.username}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {user.role === 'admin' ? 'Administrador' : 'Operador'}
                </span>
                {user.is_superuser && (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                    <Crown className="h-3 w-3 mr-1" /> Super Admin
                  </span>
                )}
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${user.tenant.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {user.tenant.status === 'active' ? 'Ativo' : 'Inativo'}
                </span>
              </div>
            </div>
          </div>

          {/* Message Alert */}
          {message && (
            <div className={`p-4 rounded-md ${message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
              {message.text}
            </div>
          )}

          {/* Profile Edit Form */}
          <form onSubmit={handleProfileSubmit} className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Informações Pessoais</h3>
              {!isEditing ? (
                <Button 
                  type="button" 
                  variant="outline" 
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-2"
                >
                  <Edit className="h-4 w-4" />
                  Editar
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button 
                    type="submit" 
                    disabled={isSaving}
                    className="flex items-center gap-2"
                  >
                    <Save className="h-4 w-4" />
                    {isSaving ? 'Salvando...' : 'Salvar'}
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={() => setIsEditing(false)}
                  >
                    Cancelar
                  </Button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="first_name">Nome</Label>
                {isEditing ? (
                  <Input
                    id="first_name"
                    value={profileData.first_name}
                    onChange={(e) => setProfileData({ ...profileData, first_name: e.target.value })}
                    placeholder="Seu nome"
                  />
                ) : (
                  <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-md">
                    <User className="h-4 w-4 text-gray-500" />
                    <span>{profileData.first_name || 'Não informado'}</span>
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="last_name">Sobrenome</Label>
                {isEditing ? (
                  <Input
                    id="last_name"
                    value={profileData.last_name}
                    onChange={(e) => setProfileData({ ...profileData, last_name: e.target.value })}
                    placeholder="Seu sobrenome"
                  />
                ) : (
                  <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-md">
                    <User className="h-4 w-4 text-gray-500" />
                    <span>{profileData.last_name || 'Não informado'}</span>
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="display_name">Nome de Exibição</Label>
                {isEditing ? (
                  <Input
                    id="display_name"
                    value={profileData.display_name}
                    onChange={(e) => setProfileData({ ...profileData, display_name: e.target.value })}
                    placeholder="Como você quer ser chamado"
                  />
                ) : (
                  <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-md">
                    <User className="h-4 w-4 text-gray-500" />
                    <span>{profileData.display_name || 'Não informado'}</span>
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="email">Email</Label>
                {isEditing ? (
                  <Input
                    id="email"
                    type="email"
                    value={profileData.email}
                    onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
                    placeholder="seu@email.com"
                  />
                ) : (
                  <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-md">
                    <Mail className="h-4 w-4 text-gray-500" />
                    <span>{profileData.email || 'Não informado'}</span>
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="phone">Telefone</Label>
                {isEditing ? (
                  <Input
                    id="phone"
                    value={profileData.phone}
                    onChange={(e) => setProfileData({ ...profileData, phone: e.target.value })}
                    placeholder="(11) 99999-9999"
                  />
                ) : (
                  <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-md">
                    <Phone className="h-4 w-4 text-gray-500" />
                    <span>{profileData.phone || 'Não informado'}</span>
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="birth_date">Data de Nascimento</Label>
                {isEditing ? (
                  <Input
                    id="birth_date"
                    type="date"
                    value={profileData.birth_date}
                    onChange={(e) => setProfileData({ ...profileData, birth_date: e.target.value })}
                  />
                ) : (
                  <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-md">
                    <Calendar className="h-4 w-4 text-gray-500" />
                    <span>{profileData.birth_date || 'Não informado'}</span>
                  </div>
                )}
              </div>
            </div>
          </form>

          {/* Change Password Form */}
          <div className="pt-6 border-t">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Lock className="h-5 w-5" />
              Alterar Senha
            </h3>
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div>
                <Label htmlFor="current_password">Senha Atual</Label>
                <Input
                  id="current_password"
                  type="password"
                  value={passwordData.current_password}
                  onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                  placeholder="Digite sua senha atual"
                />
              </div>
              <div>
                <Label htmlFor="new_password">Nova Senha</Label>
                <Input
                  id="new_password"
                  type="password"
                  value={passwordData.new_password}
                  onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                  placeholder="Digite sua nova senha"
                />
              </div>
              <div>
                <Label htmlFor="confirm_password">Confirmar Nova Senha</Label>
                <Input
                  id="confirm_password"
                  type="password"
                  value={passwordData.confirm_password}
                  onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                  placeholder="Confirme sua nova senha"
                />
              </div>
              <div className="flex justify-end pt-4">
                <Button type="submit" disabled={isSaving}>
                  {isSaving ? 'Alterando...' : 'Alterar Senha'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}