/**
 * Dados da Empresa – formulário completo (TenantCompanyProfile).
 * Planos > Dados da Empresa. Ao salvar, sincroniza chunk para RAG (n8n).
 */
import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast } from '../lib/toastHelper'
import { Building2, ArrowLeft, Save, Upload, X } from 'lucide-react'

const LOGO_MAX_KB = 500
const LOGO_MAX_BYTES = LOGO_MAX_KB * 1024
const LOGO_ACCEPT = 'image/png,image/jpeg,image/jpg,image/webp'

interface CompanyProfile {
  id: string | null
  razao_social: string | null
  cnpj: string | null
  endereco: string | null
  endereco_latitude: number | null
  endereco_longitude: number | null
  telefone: string | null
  email_principal: string | null
  ramo_atuacao: string | null
  data_fundacao: string | null
  missao: string | null
  sobre_empresa: string | null
  produtos_servicos: string | null
  logo_url: string | null
  created_at: string | null
  updated_at: string | null
}

const emptyProfile: CompanyProfile = {
  id: null,
  razao_social: null,
  cnpj: null,
  endereco: null,
  endereco_latitude: null,
  endereco_longitude: null,
  telefone: null,
  email_principal: null,
  ramo_atuacao: null,
  data_fundacao: null,
  missao: null,
  sobre_empresa: null,
  produtos_servicos: null,
  logo_url: null,
  created_at: null,
  updated_at: null,
}

function toFormValue(v: string | number | null | undefined): string {
  if (v == null) return ''
  return String(v)
}

export default function CompanyProfilePage() {
  const [profile, setProfile] = useState<CompanyProfile>(emptyProfile)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const logoInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchProfile()
  }, [])

  const fetchProfile = async () => {
    try {
      setLoading(true)
      const res = await api.get('/tenants/company-profile/')
      const data = res.data || {}
      setProfile({
        id: data.id ?? null,
        razao_social: data.razao_social ?? null,
        cnpj: data.cnpj ?? null,
        endereco: data.endereco ?? null,
        endereco_latitude: data.endereco_latitude != null ? Number(data.endereco_latitude) : null,
        endereco_longitude: data.endereco_longitude != null ? Number(data.endereco_longitude) : null,
        telefone: data.telefone ?? null,
        email_principal: data.email_principal ?? null,
        ramo_atuacao: data.ramo_atuacao ?? null,
        data_fundacao: data.data_fundacao ?? null,
        missao: data.missao ?? null,
        sobre_empresa: data.sobre_empresa ?? null,
        produtos_servicos: data.produtos_servicos ?? null,
        logo_url: data.logo_url ?? null,
        created_at: data.created_at ?? null,
        updated_at: data.updated_at ?? null,
      })
    } catch (e) {
      console.error('Erro ao carregar dados da empresa:', e)
      showErrorToast('Erro ao carregar dados da empresa')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (field: keyof CompanyProfile, value: string | number | null) => {
    setProfile((p) => ({ ...p, [field]: value || null }))
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      const payload: Record<string, unknown> = {
        razao_social: profile.razao_social || null,
        cnpj: profile.cnpj || null,
        endereco: profile.endereco || null,
        endereco_latitude: profile.endereco_latitude ?? null,
        endereco_longitude: profile.endereco_longitude ?? null,
        telefone: profile.telefone || null,
        email_principal: profile.email_principal || null,
        ramo_atuacao: profile.ramo_atuacao || null,
        data_fundacao: profile.data_fundacao || null,
        missao: profile.missao || null,
        sobre_empresa: profile.sobre_empresa || null,
        produtos_servicos: profile.produtos_servicos || null,
        logo_url: profile.logo_url || null,
      }
      await api.put('/tenants/company-profile/', payload)
      showSuccessToast('Dados da empresa salvos')
      fetchProfile()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { [k: string]: unknown } } }
      const msg = err.response?.data
        ? (typeof msg === 'object' && msg && 'error' in msg ? String((msg as { error: string }).error) : JSON.stringify(msg))
        : 'Erro ao salvar'
      showErrorToast(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleLogoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > LOGO_MAX_BYTES) {
      showErrorToast(`Arquivo muito grande. Máximo ${LOGO_MAX_KB} KB.`)
      return
    }
    const fd = new FormData()
    fd.append('logo', file)
    try {
      setUploadingLogo(true)
      const res = await api.post('/tenants/company-profile/upload-logo/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const logoUrl = (res.data as { logo_url?: string })?.logo_url
      if (logoUrl) {
        setProfile((p) => ({ ...p, logo_url: logoUrl }))
        showSuccessToast('Logo enviado')
      }
    } catch (err) {
      showErrorToast('Erro ao enviar logo')
    } finally {
      setUploadingLogo(false)
      e.target.value = ''
    }
  }

  const removeLogo = () => {
    setProfile((p) => ({ ...p, logo_url: null }))
    showSuccessToast('Clique em Salvar para confirmar a remoção da logo')
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <Link
        to="/billing"
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar para Planos
      </Link>

      <Card className="p-6">
        <h1 className="text-xl font-semibold text-gray-900 mb-6 flex items-center gap-2">
          <Building2 className="h-6 w-6 text-blue-600" />
          Dados da Empresa
        </h1>
        <p className="text-sm text-gray-600 mb-6">
          Preencha os dados usados para cobrança, faturamento e contexto da BIA (secretária virtual).
        </p>

        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="razao_social">Razão Social</Label>
              <Input
                id="razao_social"
                value={toFormValue(profile.razao_social)}
                onChange={(e) => handleChange('razao_social', e.target.value)}
                placeholder="Empresa Ltda"
              />
            </div>
            <div>
              <Label htmlFor="cnpj">CNPJ</Label>
              <Input
                id="cnpj"
                value={toFormValue(profile.cnpj)}
                onChange={(e) => handleChange('cnpj', e.target.value)}
                placeholder="00.000.000/0001-00"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="endereco">Endereço</Label>
            <Input
              id="endereco"
              value={toFormValue(profile.endereco)}
              onChange={(e) => handleChange('endereco', e.target.value)}
              placeholder="Rua, número, bairro, cidade - UF"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="endereco_latitude">Latitude</Label>
              <Input
                id="endereco_latitude"
                type="number"
                step="any"
                value={toFormValue(profile.endereco_latitude)}
                onChange={(e) =>
                  handleChange('endereco_latitude', e.target.value ? Number(e.target.value) : null)
                }
                placeholder="-23.5505"
              />
            </div>
            <div>
              <Label htmlFor="endereco_longitude">Longitude</Label>
              <Input
                id="endereco_longitude"
                type="number"
                step="any"
                value={toFormValue(profile.endereco_longitude)}
                onChange={(e) =>
                  handleChange('endereco_longitude', e.target.value ? Number(e.target.value) : null)
                }
                placeholder="-46.6333"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="telefone">Telefone</Label>
              <Input
                id="telefone"
                value={toFormValue(profile.telefone)}
                onChange={(e) => handleChange('telefone', e.target.value)}
                placeholder="(11) 99999-9999"
              />
            </div>
            <div>
              <Label htmlFor="email_principal">Email</Label>
              <Input
                id="email_principal"
                type="email"
                value={toFormValue(profile.email_principal)}
                onChange={(e) => handleChange('email_principal', e.target.value)}
                placeholder="contato@empresa.com"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="ramo_atuacao">Ramo de Atuação</Label>
              <Input
                id="ramo_atuacao"
                value={toFormValue(profile.ramo_atuacao)}
                onChange={(e) => handleChange('ramo_atuacao', e.target.value)}
                placeholder="Tecnologia, Varejo..."
              />
            </div>
            <div>
              <Label htmlFor="data_fundacao">Data de Fundação</Label>
              <Input
                id="data_fundacao"
                type="date"
                value={toFormValue(profile.data_fundacao)}
                onChange={(e) => handleChange('data_fundacao', e.target.value || null)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="missao">Missão</Label>
            <textarea
              id="missao"
              rows={3}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
              value={toFormValue(profile.missao)}
              onChange={(e) => handleChange('missao', e.target.value)}
              placeholder="Nossa missão é..."
            />
          </div>

          <div>
            <Label htmlFor="sobre_empresa">Sobre a Empresa</Label>
            <textarea
              id="sobre_empresa"
              rows={3}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
              value={toFormValue(profile.sobre_empresa)}
              onChange={(e) => handleChange('sobre_empresa', e.target.value)}
              placeholder="Histórico e descrição..."
            />
          </div>

          <div>
            <Label htmlFor="produtos_servicos">Produtos / Serviços</Label>
            <textarea
              id="produtos_servicos"
              rows={4}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
              value={toFormValue(profile.produtos_servicos)}
              onChange={(e) => handleChange('produtos_servicos', e.target.value)}
              placeholder="Liste os principais produtos ou serviços oferecidos..."
            />
          </div>

          <div>
            <Label>Logo</Label>
            <p className="text-xs text-gray-500 mb-2">
              Máx. {LOGO_MAX_KB} KB. PNG, JPEG ou WebP.
            </p>
            {profile.logo_url ? (
              <div className="flex items-center gap-4 mt-2">
                <img
                  src={profile.logo_url}
                  alt="Logo"
                  className="h-20 w-20 object-contain border rounded"
                />
                <div className="flex gap-2">
                  <input
                    ref={logoInputRef}
                    type="file"
                    accept={LOGO_ACCEPT}
                    className="hidden"
                    onChange={handleLogoChange}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => logoInputRef.current?.click()}
                    disabled={uploadingLogo}
                  >
                    <Upload className="h-4 w-4 mr-1" />
                    {uploadingLogo ? 'Enviando...' : 'Trocar'}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={removeLogo}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Remover
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-2">
                <input
                  ref={logoInputRef}
                  type="file"
                  accept={LOGO_ACCEPT}
                  className="hidden"
                  onChange={handleLogoChange}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => logoInputRef.current?.click()}
                  disabled={uploadingLogo}
                >
                  <Upload className="h-4 w-4 mr-2" />
                  {uploadingLogo ? 'Enviando...' : 'Enviar logo'}
                </Button>
              </div>
            )}
          </div>
        </div>

        <div className="mt-8 flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            <Save className="h-4 w-4 mr-2" />
            {saving ? 'Salvando...' : 'Salvar'}
          </Button>
        </div>
      </Card>
    </div>
  )
}
