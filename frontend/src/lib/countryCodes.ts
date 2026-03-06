/**
 * Códigos de país E.164 para dropdown de telefone internacional.
 * Brasil primeiro (padrão); depois América do Sul, América do Norte e outros comuns.
 * dial = código de discagem (sem +); usado para montar E.164 (+dial + número nacional).
 */

export interface CountryOption {
  dial: string
  label: string
  code: string
}

/** Países: Brasil primeiro, depois ordenados por nome. Ordenados por dial length desc para parse correto (595 antes de 59). */
export const COUNTRY_OPTIONS: CountryOption[] = [
  { dial: '55', label: 'Brasil', code: 'BR' },
  { dial: '54', label: 'Argentina', code: 'AR' },
  { dial: '595', label: 'Paraguai', code: 'PY' },
  { dial: '598', label: 'Uruguai', code: 'UY' },
  { dial: '56', label: 'Chile', code: 'CL' },
  { dial: '57', label: 'Colômbia', code: 'CO' },
  { dial: '51', label: 'Peru', code: 'PE' },
  { dial: '593', label: 'Equador', code: 'EC' },
  { dial: '591', label: 'Bolívia', code: 'BO' },
  { dial: '58', label: 'Venezuela', code: 'VE' },
  { dial: '1', label: 'EUA / Canadá', code: 'US' },
  { dial: '52', label: 'México', code: 'MX' },
  { dial: '351', label: 'Portugal', code: 'PT' },
  { dial: '34', label: 'Espanha', code: 'ES' },
  { dial: '39', label: 'Itália', code: 'IT' },
  { dial: '49', label: 'Alemanha', code: 'DE' },
  { dial: '33', label: 'França', code: 'FR' },
  { dial: '44', label: 'Reino Unido', code: 'GB' },
  { dial: '81', label: 'Japão', code: 'JP' },
  { dial: '86', label: 'China', code: 'CN' },
  { dial: '91', label: 'Índia', code: 'IN' },
  { dial: '353', label: 'Irlanda', code: 'IE' },
  { dial: '31', label: 'Países Baixos', code: 'NL' },
  { dial: '41', label: 'Suíça', code: 'CH' },
  { dial: '43', label: 'Áustria', code: 'AT' },
  { dial: '32', label: 'Bélgica', code: 'BE' },
  { dial: '48', label: 'Polônia', code: 'PL' },
  { dial: '7', label: 'Rússia / Cazaquistão', code: 'RU' },
  { dial: '61', label: 'Austrália', code: 'AU' },
  { dial: '64', label: 'Nova Zelândia', code: 'NZ' },
  { dial: '27', label: 'África do Sul', code: 'ZA' },
  { dial: '972', label: 'Israel', code: 'IL' },
]

const uniqueByDial = (list: CountryOption[]): CountryOption[] => {
  const seen = new Set<string>()
  return list.filter((c) => {
    if (seen.has(c.dial)) return false
    seen.add(c.dial)
    return true
  })
}

/** Para exibição no dropdown: Brasil primeiro, depois os demais. */
export const COUNTRY_OPTIONS_FOR_DROPDOWN: CountryOption[] = (() => {
  const list = uniqueByDial(COUNTRY_OPTIONS)
  const br = list.find((c) => c.dial === '55')
  const rest = list.filter((c) => c.dial !== '55').sort((a, b) => a.label.localeCompare(b.label))
  return br ? [br, ...rest] : list
})()

/** Para parse E.164: length desc (595 antes de 59), depois dial asc (54 antes de 55 para 54...). */
export const COUNTRY_OPTIONS_SORTED_BY_DIAL_LENGTH: CountryOption[] = [
  ...COUNTRY_OPTIONS_FOR_DROPDOWN,
].sort((a, b) => b.dial.length - a.dial.length || a.dial.localeCompare(b.dial))

/** País padrão (Brasil). */
export const DEFAULT_COUNTRY_DIAL = '55'

/** Extrai código do país e o restante dos dígitos (número nacional) a partir de E.164. */
export function parseE164ToCountryAndNational(e164: string): { dial: string; national: string } {
  const digits = (e164 || '').replace(/\D/g, '')
  if (!digits.length) return { dial: DEFAULT_COUNTRY_DIAL, national: '' }
  for (const c of COUNTRY_OPTIONS_SORTED_BY_DIAL_LENGTH) {
    if (digits.startsWith(c.dial)) {
      const national = digits.slice(c.dial.length)
      return { dial: c.dial, national }
    }
  }
  return { dial: DEFAULT_COUNTRY_DIAL, national: digits }
}

/** Retorna true se o código de país está na lista (parse reconheceu país conhecido). */
export function isKnownCountryDial(dial: string): boolean {
  return COUNTRY_OPTIONS_FOR_DROPDOWN.some((c) => c.dial === dial)
}

/** Mínimo de dígitos no número nacional para considerar E.164 internacional válido. */
const MIN_NATIONAL_DIGITS = 6

/** Monta E.164: +dial + nationalDigits (apenas dígitos). Exige mínimo de dígitos no nacional. */
export function buildE164International(dial: string, nationalDigits: string): string {
  const d = (dial || '').replace(/\D/g, '')
  const n = (nationalDigits || '').replace(/\D/g, '')
  if (!d || !n || n.length < MIN_NATIONAL_DIGITS) return ''
  return `+${d}${n}`
}

/** Retorna a opção de país pelo código de discagem. */
export function getCountryByDial(dial: string): CountryOption | undefined {
  return COUNTRY_OPTIONS.find((c) => c.dial === dial)
}
