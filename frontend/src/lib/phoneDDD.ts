/**
 * DDDs do Brasil (códigos de área) para uso em dropdown.
 * Fonte: Anatel / códigos em uso.
 * 17 como primeiro item (padrão sugerido); depois ordenados; "Outro" no final é tratado no componente.
 */
export const BRAZIL_DDD_LIST = [
  '17', // padrão (ex.: região de Rio Preto)
  '11', '12', '13', '14', '15', '16', '18', '19',
  '21', '22', '24', '27', '28',
  '31', '32', '33', '34', '35', '37', '38',
  '41', '42', '43', '44', '45', '46', '47', '48', '49',
  '51', '53', '54', '55', // 55 é DDD do RS (não confundir com +55 do país)
  '61', '62', '63', '64', '65', '66', '67', '68', '69',
  '71', '73', '74', '75', '77', '79',
  '81', '82', '83', '84', '85', '86', '87', '88', '89',
  '91', '92', '93', '94', '95', '96', '97', '98', '99'
] as const

export const DEFAULT_DDD = '17'

export const VALUE_OTHER_DDD = '__outro__'

/** Converte valor E.164 (+5517999999999) em { ddd, number } (só dígitos no number). */
export function parseE164ToDDDAndNumber(e164: string): { ddd: string; number: string } {
  const digits = (e164 || '').replace(/\D/g, '')
  if (digits.startsWith('55') && digits.length >= 12) {
    const ddd = digits.slice(2, 4)
    const number = digits.slice(4)
    return { ddd, number }
  }
  if (digits.length >= 10) {
    const ddd = digits.slice(0, 2)
    const number = digits.slice(2)
    return { ddd, number }
  }
  return { ddd: DEFAULT_DDD, number: digits }
}

/** Monta E.164 a partir de DDD (exatamente 2 dígitos) e número (só dígitos). */
export function buildE164(ddd: string, number: string): string {
  const d = (ddd || '').replace(/\D/g, '').slice(0, 2)
  const n = (number || '').replace(/\D/g, '')
  if (d.length !== 2 || !n) return ''
  return `+55${d}${n}`
}

/**
 * Converte input parcial (ex: "999991234" ou "17999991234") em E.164.
 * Se já for E.164, devolve como está. Se 8–9 dígitos, usa defaultDdd (ex: 17).
 */
export function rawInputToE164(input: string, defaultDdd: string = DEFAULT_DDD): string {
  const digits = (input || '').replace(/\D/g, '')
  if (digits.startsWith('55') && digits.length >= 12) return '+' + digits
  if (digits.length >= 10) return '+55' + digits
  if (digits.length >= 8) return `+55${defaultDdd}${digits}`
  return ''
}

/** Regex para telefone brasileiro E.164: +55 + DDD (2) + número (8 ou 9 dígitos). */
export const E164_BR_REGEX = /^\+55\d{10,11}$/

/** Retorna true se o valor for um E.164 brasileiro válido (para validação de submit). */
export function isValidBrazilianE164(phone: string): boolean {
  return typeof phone === 'string' && E164_BR_REGEX.test(phone.replace(/\s/g, ''))
}
