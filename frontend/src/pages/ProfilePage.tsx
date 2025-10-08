import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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
  Save, 
  Lock, 
  X,
  Crown,
  Bell,
  MessageSquare
} from 'lucide-react'

interface ProfileData {
  id: string
  email: string
  first_name: string
  last_name: string
  phone: string
  birth_date: string
  notify_email: boolean
  notify_whatsapp: boolean
}

interface PasswordData {
  current_password: string
  new_password: string
  confirm_password: string
}

export default function ProfilePage() {
  const { user, setUser } = useAuthStore()
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  
  const [profileData, setProfileData] = useState<ProfileData>({
    id: '',
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
    birth_date: '',
    notify_email: true,
    notify_whatsapp: true,
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
        phone: user.phone || '',
        birth_date: user.birth_date || '',
        notify_email: user.notify_email ?? true,
        notify_whatsapp: user.notify_whatsapp ?? true,
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
        phone: profileData.phone,
        birth_date: profileData.birth_date,
        notify_email: profileData.notify_email,
        notify_whatsapp: profileData.notify_whatsapp,
      })
      
      console.log('✅ Profile update response:', response.data)
      
      // Update user in store
      setUser(response.data)
      console.log('✅ User updated in store')
      
      setMessage({ type: 'success', text: 'Perfil atualizado com sucesso!' })
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
    navigate('/dashboard')
  }

  if (!user) return null

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={handleCloseModal}
    >
      <div 
        className="bg-white rounded-lg shadow-xl w-full max-w-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-gray-900">Meu Perfil</h1>
            <Button variant="ghost" size="icon" onClick={handleCloseModal}>
              <X className="h-5 w-5" />
            </Button>
          </div>
        </div>

        <div className="p-4 space-y-4">
          {/* User Info Header */}
          <div className="flex items-center gap-3">
            <div className="h-16 w-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xl font-bold">
              <User className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {`${profileData.first_name} ${profileData.last_name}`.trim() || user.username}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {user.role === 'admin' ? 'Administrador' : 'Operador'}
                </span>
                {user.is_superuser && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                    <Crown className="h-3 w-3 mr-1" /> Super Admin
                  </span>
                )}
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${user.tenant.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
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
          <form onSubmit={handleProfileSubmit} className="space-y-3">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-gray-900">Informações Pessoais</h3>
              <Button 
                type="submit" 
                disabled={isSaving}
                className="flex items-center gap-2"
                size="sm"
              >
                <Save className="h-4 w-4" />
                {isSaving ? 'Salvando...' : 'Salvar'}
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <Label htmlFor="first_name">Nome</Label>
                <Input
                  id="first_name"
                  value={profileData.first_name}
                  onChange={(e) => setProfileData({ ...profileData, first_name: e.target.value })}
                  placeholder="Seu nome"
                />
              </div>

              <div>
                <Label htmlFor="last_name">Sobrenome</Label>
                <Input
                  id="last_name"
                  value={profileData.last_name}
                  onChange={(e) => setProfileData({ ...profileData, last_name: e.target.value })}
                  placeholder="Seu sobrenome"
                />
              </div>

              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={profileData.email}
                  onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
                  placeholder="seu@email.com"
                />
              </div>

              <div>
                <Label htmlFor="phone">Telefone</Label>
                <Input
                  id="phone"
                  value={profileData.phone}
                  onChange={(e) => setProfileData({ ...profileData, phone: e.target.value })}
                  placeholder="(11) 99999-9999"
                />
              </div>

              <div>
                <Label>Data de Nascimento</Label>
                <div className="grid grid-cols-3 gap-2">
                  <select
                    value={profileData.birth_date ? new Date(profileData.birth_date).getDate() : ''}
                    onChange={(e) => {
                      const day = e.target.value
                      const currentDate = profileData.birth_date ? new Date(profileData.birth_date) : new Date()
                      const month = currentDate.getMonth() + 1
                      const year = currentDate.getFullYear()
                      const newDate = `${year}-${month.toString().padStart(2, '0')}-${day.padStart(2, '0')}`
                      setProfileData({ ...profileData, birth_date: newDate })
                    }}
                    className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">Dia</option>
                    {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                      <option key={day} value={day}>{day}</option>
                    ))}
                  </select>
                  
                  <select
                    value={profileData.birth_date ? new Date(profileData.birth_date).getMonth() + 1 : ''}
                    onChange={(e) => {
                      const month = e.target.value
                      const currentDate = profileData.birth_date ? new Date(profileData.birth_date) : new Date()
                      const day = currentDate.getDate()
                      const year = currentDate.getFullYear()
                      const newDate = `${year}-${month.padStart(2, '0')}-${day.toString().padStart(2, '0')}`
                      setProfileData({ ...profileData, birth_date: newDate })
                    }}
                    className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">Mês</option>
                    {[
                      'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                      'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
                    ].map((month, index) => (
                      <option key={index} value={index + 1}>{month}</option>
                    ))}
                  </select>
                  
                  <select
                    value={profileData.birth_date ? new Date(profileData.birth_date).getFullYear() : ''}
                    onChange={(e) => {
                      const year = e.target.value
                      const currentDate = profileData.birth_date ? new Date(profileData.birth_date) : new Date()
                      const day = currentDate.getDate()
                      const month = currentDate.getMonth() + 1
                      const newDate = `${year}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`
                      setProfileData({ ...profileData, birth_date: newDate })
                    }}
                    className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">Ano</option>
                    {Array.from({ length: 100 }, (_, i) => new Date().getFullYear() - i).map(year => (
                      <option key={year} value={year}>{year}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Notification Settings - Vertical */}
              <div className="space-y-3">
                <Label>Notificações</Label>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="notify_email"
                      checked={profileData.notify_email}
                      onChange={(e) => setProfileData({ ...profileData, notify_email: e.target.checked })}
                      className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <Label htmlFor="notify_email" className="!mb-0 flex items-center gap-1">
                      <Mail className="h-4 w-4 text-gray-500" />
                      Notificar via Email
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="notify_whatsapp"
                      checked={profileData.notify_whatsapp}
                      onChange={(e) => setProfileData({ ...profileData, notify_whatsapp: e.target.checked })}
                      className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <Label htmlFor="notify_whatsapp" className="!mb-0 flex items-center gap-1">
                      <MessageSquare className="h-4 w-4 text-gray-500" />
                      Notificar via WhatsApp
                    </Label>
                  </div>
                </div>
              </div>
            </div>
          </form>

          {/* Change Password Form */}
          <div className="pt-4 border-t">
            <h3 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Lock className="h-4 w-4" />
              Alterar Senha
            </h3>
            <form onSubmit={handlePasswordSubmit} className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <Label htmlFor="current_password">Senha Atual</Label>
                  <Input
                    id="current_password"
                    type="password"
                    value={passwordData.current_password}
                    onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                    placeholder="Senha atual"
                  />
                </div>
                <div>
                  <Label htmlFor="new_password">Nova Senha</Label>
                  <Input
                    id="new_password"
                    type="password"
                    value={passwordData.new_password}
                    onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                    placeholder="Nova senha"
                  />
                </div>
                <div>
                  <Label htmlFor="confirm_password">Confirmar</Label>
                  <Input
                    id="confirm_password"
                    type="password"
                    value={passwordData.confirm_password}
                    onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                    placeholder="Confirmar senha"
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <Button type="submit" disabled={isSaving} size="sm">
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