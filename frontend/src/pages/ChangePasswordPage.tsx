import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import Toast from '../components/ui/Toast'
import { useToast } from '../hooks/useToast'
import { Lock, Eye, EyeOff, ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'

export default function ChangePasswordPage() {
  const navigate = useNavigate()
  const { toast, showToast, hideToast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  
  const [formData, setFormData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const validateForm = () => {
    if (!formData.current_password) {
      showToast('Por favor, informe sua senha atual', 'error')
      return false
    }
    
    if (!formData.new_password) {
      showToast('Por favor, informe a nova senha', 'error')
      return false
    }
    
    if (formData.new_password.length < 8) {
      showToast('A nova senha deve ter pelo menos 8 caracteres', 'error')
      return false
    }
    
    if (formData.new_password !== formData.confirm_password) {
      showToast('As senhas não coincidem', 'error')
      return false
    }
    
    if (formData.current_password === formData.new_password) {
      showToast('A nova senha deve ser diferente da senha atual', 'error')
      return false
    }
    
    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) return
    
    setIsLoading(true)
    
    try {
      await api.post('/auth/change-password/', {
        current_password: formData.current_password,
        new_password: formData.new_password
      })
      
      showToast('✅ Senha alterada com sucesso!', 'success')
      
      // Limpar formulário
      setFormData({
        current_password: '',
        new_password: '',
        confirm_password: ''
      })
      
      // Redirecionar para o perfil após 2 segundos
      setTimeout(() => {
        navigate('/profile')
      }, 2000)
      
    } catch (error: any) {
      console.error('Error changing password:', error)
      const errorMessage = error.response?.data?.detail || 
                          error.response?.data?.current_password?.[0] ||
                          'Erro ao alterar senha. Verifique os dados e tente novamente.'
      showToast(errorMessage, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={() => navigate('/profile')}
          className="mb-4 p-0 h-auto text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Voltar ao Perfil
        </Button>
        
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
            <Lock className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Alterar Senha</h1>
            <p className="text-gray-600">Mantenha sua conta segura</p>
          </div>
        </div>
      </div>

      {/* Form */}
      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Senha Atual */}
          <div>
            <Label htmlFor="current_password">Senha Atual</Label>
            <div className="relative">
              <Input
                id="current_password"
                name="current_password"
                type={showCurrentPassword ? 'text' : 'password'}
                value={formData.current_password}
                onChange={handleInputChange}
                placeholder="Digite sua senha atual"
                required
                className="pr-10"
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
              >
                {showCurrentPassword ? (
                  <EyeOff className="h-4 w-4 text-gray-400" />
                ) : (
                  <Eye className="h-4 w-4 text-gray-400" />
                )}
              </button>
            </div>
          </div>

          {/* Nova Senha */}
          <div>
            <Label htmlFor="new_password">Nova Senha</Label>
            <div className="relative">
              <Input
                id="new_password"
                name="new_password"
                type={showNewPassword ? 'text' : 'password'}
                value={formData.new_password}
                onChange={handleInputChange}
                placeholder="Digite a nova senha (mín. 8 caracteres)"
                required
                className="pr-10"
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
                onClick={() => setShowNewPassword(!showNewPassword)}
              >
                {showNewPassword ? (
                  <EyeOff className="h-4 w-4 text-gray-400" />
                ) : (
                  <Eye className="h-4 w-4 text-gray-400" />
                )}
              </button>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              A senha deve ter pelo menos 8 caracteres
            </p>
          </div>

          {/* Confirmar Nova Senha */}
          <div>
            <Label htmlFor="confirm_password">Confirmar Nova Senha</Label>
            <div className="relative">
              <Input
                id="confirm_password"
                name="confirm_password"
                type={showConfirmPassword ? 'text' : 'password'}
                value={formData.confirm_password}
                onChange={handleInputChange}
                placeholder="Confirme a nova senha"
                required
                className="pr-10"
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              >
                {showConfirmPassword ? (
                  <EyeOff className="h-4 w-4 text-gray-400" />
                ) : (
                  <Eye className="h-4 w-4 text-gray-400" />
                )}
              </button>
            </div>
          </div>

          {/* Botões */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/profile')}
              className="flex-1"
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={isLoading}
              className="flex-1"
            >
              {isLoading ? 'Alterando...' : 'Alterar Senha'}
            </Button>
          </div>
        </form>
      </Card>

      {/* Toast Notification */}
      <Toast
        show={toast.show}
        message={toast.message}
        type={toast.type}
        onClose={hideToast}
      />
    </div>
  )
}
