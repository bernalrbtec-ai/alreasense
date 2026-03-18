import { useState, useEffect, useMemo } from 'react'
import {
  COUNTRY_OPTIONS_FOR_DROPDOWN,
  DEFAULT_COUNTRY_DIAL,
  parseE164ToCountryAndNational,
  buildE164International,
} from '../lib/countryCodes'
import { BRAZIL_DDD_LIST, DEFAULT_DDD, VALUE_OTHER_DDD, parseE164ToDDDAndNumber, buildE164 } from '../lib/phoneDDD'
import { cn } from '../lib/utils'

interface PhoneInputWithDDDProps {
  value: string
  onChange: (e164: string) => void
  defaultDdd?: string
  defaultCountryDial?: string
  id?: string
  className?: string
  inputClassName?: string
  required?: boolean
  placeholder?: string
  disabled?: boolean
}

export function PhoneInputWithDDD({
  value,
  onChange,
  defaultDdd = DEFAULT_DDD,
  defaultCountryDial = DEFAULT_COUNTRY_DIAL,
  id,
  className,
  inputClassName,
  required,
  placeholder = '99999-9999',
  disabled,
}: PhoneInputWithDDDProps) {
  const isBrazil = (dial: string) => dial === '55'

  const countryAndNational = useMemo(() => parseE164ToCountryAndNational(value || ''), [value])
  const parsedBr = useMemo(
    () => (countryAndNational.dial === '55' ? parseE164ToDDDAndNumber(value || '') : { ddd: defaultDdd, number: '' }),
    [value, countryAndNational.dial, defaultDdd]
  )

  const [selectedCountryDial, setSelectedCountryDial] = useState(countryAndNational.dial || defaultCountryDial)
  const [selectedDddKey, setSelectedDddKey] = useState<string>(parsedBr.ddd || defaultDdd)
  const [otherDdd, setOtherDdd] = useState(
    parsedBr.ddd && !BRAZIL_DDD_LIST.includes(parsedBr.ddd as any) ? parsedBr.ddd : ''
  )
  const [numberPart, setNumberPart] = useState(parsedBr.number || '')
  const [nationalNumber, setNationalNumber] = useState(
    !isBrazil(countryAndNational.dial) ? countryAndNational.national : ''
  )

  const isOther = selectedDddKey === VALUE_OTHER_DDD
  const effectiveDdd = isOther ? otherDdd.replace(/\D/g, '').slice(0, 2) : selectedDddKey
  const showBrazilFields = isBrazil(selectedCountryDial)

  useEffect(() => {
    const { dial, national } = parseE164ToCountryAndNational(value || '')
    if (value && value.trim() !== '') {
      setSelectedCountryDial(dial)
      if (isBrazil(dial)) {
        const p = parseE164ToDDDAndNumber(value || '')
        setNumberPart(p.number)
        setNationalNumber('')
        if (BRAZIL_DDD_LIST.includes(p.ddd as any)) {
          setSelectedDddKey(p.ddd)
          setOtherDdd('')
        } else if (p.ddd) {
          setSelectedDddKey(VALUE_OTHER_DDD)
          setOtherDdd(p.ddd)
        } else {
          setSelectedDddKey(defaultDdd)
          setOtherDdd('')
        }
      } else {
        setNationalNumber(national)
        setNumberPart('')
        setSelectedDddKey(defaultDdd)
        setOtherDdd('')
      }
    }
  }, [value, defaultDdd])

  const notifyBrazil = (ddd: string, num: string) => {
    onChange(buildE164(ddd, num))
  }

  const notifyInternational = (dial: string, national: string) => {
    onChange(buildE164International(dial, national))
  }

  /**
   * Autodetecção ao digitar diretamente no campo:
   * - Se começar com "55" (sem +), tenta detectar: 55 + DDD(2) + número
   * - Se tiver 10-11 dígitos, tenta detectar: DDD(2) + número (sem país)
   *
   * Devolve null quando não faz sentido ainda (evita inferir errado enquanto digita).
   */
  const inferBrazilFromDigits = (digitsRaw: string): { ddd: string; number: string } | null => {
    const digits = (digitsRaw || '').replace(/\D/g, '')
    if (!digits) return null

    // Caso A: país "55" incluso (sem '+'): 55 + ddd + number
    if (digits.startsWith('55') && digits.length >= 4) {
      const ddd = digits.slice(2, 4)
      if (BRAZIL_DDD_LIST.includes(ddd as any)) {
        const number = digits.slice(4, 4 + 9) // 8 ou 9 dígitos
        return { ddd, number }
      }
    }

    // Caso B: DDD + number (sem país): 10-11 dígitos completos
    if (digits.length >= 10 && digits.length <= 11) {
      const ddd = digits.slice(0, 2)
      if (BRAZIL_DDD_LIST.includes(ddd as any)) {
        const number = digits.slice(2, 2 + 9) // 8 ou 9 dígitos
        return { ddd, number }
      }
    }

    return null
  }

  const handleCountryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const dial = e.target.value
    setSelectedCountryDial(dial)
    if (isBrazil(dial)) {
      setNationalNumber('')
      notifyBrazil(selectedDddKey === VALUE_OTHER_DDD ? otherDdd : selectedDddKey, numberPart)
    } else {
      setNumberPart('')
      setSelectedDddKey(defaultDdd)
      setOtherDdd('')
      notifyInternational(dial, nationalNumber)
    }
  }

  const handleDddSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value
    setSelectedDddKey(v)
    if (v !== VALUE_OTHER_DDD) {
      setOtherDdd('')
      notifyBrazil(v, numberPart)
    } else {
      notifyBrazil('', numberPart)
    }
  }

  const handleOtherDddChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 2)
    setOtherDdd(raw)
    notifyBrazil(raw, numberPart)
  }

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // O componente está no modo Brasil: campo "Número" (que pode receber DDD completo também)
    const digits = e.target.value.replace(/\D/g, '').slice(0, 15)
    const inferred = inferBrazilFromDigits(digits)
    if (inferred) {
      setSelectedCountryDial('55')
      setSelectedDddKey(inferred.ddd)
      setOtherDdd('')
      setNumberPart(inferred.number)
      notifyBrazil(inferred.ddd, inferred.number)
      return
    }

    // Fallback: trata como "só o número" (sem DDD) e mantém o DDD selecionado
    const numberOnly = digits.slice(0, 9)
    setNumberPart(numberOnly)
    notifyBrazil(effectiveDdd, numberOnly)
  }

  const handleNationalNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const digits = e.target.value.replace(/\D/g, '').slice(0, 15)
    // Se o usuário começar a digitar "55..." ou "DDD+numero" mesmo estando em outro país,
    // tenta automaticamente migrar para Brasil (UX mais amigável).
    const inferred = inferBrazilFromDigits(digits)
    if (inferred) {
      setSelectedCountryDial('55')
      setSelectedDddKey(inferred.ddd)
      setOtherDdd('')
      setNationalNumber('')
      setNumberPart(inferred.number)
      notifyBrazil(inferred.ddd, inferred.number)
      return
    }

    setNationalNumber(digits.slice(0, 15))
    notifyInternational(selectedCountryDial, digits.slice(0, 15))
  }

  const inputBaseCn = cn(
    'h-9 sm:h-10 rounded-md border border-border bg-background text-foreground px-2 py-2 text-sm',
    'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ring-offset-background',
    'disabled:cursor-not-allowed disabled:opacity-50',
    inputClassName
  )

  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      <div className="flex flex-col gap-1 flex-shrink-0 w-[140px]">
        <label htmlFor={id ? `${id}-country` : undefined} className="sr-only">
          País
        </label>
        <select
          id={id ? `${id}-country` : undefined}
          value={selectedCountryDial}
          onChange={handleCountryChange}
          disabled={disabled}
          className={inputBaseCn}
          aria-label="País"
        >
          {COUNTRY_OPTIONS_FOR_DROPDOWN.map((c) => (
            <option key={c.dial} value={c.dial}>
              {c.label} (+{c.dial})
            </option>
          ))}
        </select>
      </div>

      {showBrazilFields ? (
        <>
          <div className="flex flex-col gap-1 flex-shrink-0">
            <label htmlFor={id ? `${id}-ddd` : undefined} className="sr-only">
              DDD
            </label>
            <select
              id={id ? `${id}-ddd` : undefined}
              value={selectedDddKey}
              onChange={handleDddSelect}
              disabled={disabled}
              className={cn('w-[72px]', inputBaseCn)}
              aria-label="DDD"
            >
              {BRAZIL_DDD_LIST.map((ddd) => (
                <option key={ddd} value={ddd}>
                  {ddd}
                </option>
              ))}
              <option value={VALUE_OTHER_DDD}>Outro</option>
            </select>
          </div>
          {isOther && (
            <div className="flex flex-col gap-1 flex-shrink-0 w-[60px]">
              <label htmlFor={id ? `${id}-other-ddd` : undefined} className="sr-only">
                DDD (outro)
              </label>
              <input
                id={id ? `${id}-other-ddd` : undefined}
                type="tel"
                inputMode="numeric"
                maxLength={2}
                value={otherDdd}
                onChange={handleOtherDddChange}
                disabled={disabled}
                placeholder="DD"
                className={cn('text-center', inputBaseCn)}
                aria-label="DDD (outro)"
              />
            </div>
          )}
          <div className="flex-1 min-w-[120px] flex flex-col gap-1">
            <label htmlFor={id ? `${id}-number` : undefined} className="sr-only">
              Número
            </label>
            <input
              id={id ? `${id}-number` : undefined}
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              value={numberPart}
              onChange={handleNumberChange}
              disabled={disabled}
              required={required}
              placeholder={placeholder}
              className={cn('placeholder:text-muted-foreground', inputBaseCn)}
              aria-label="Número do telefone"
            />
          </div>
        </>
      ) : (
        <div className="flex-1 min-w-[160px] flex flex-col gap-1">
          <label htmlFor={id ? `${id}-national` : undefined} className="sr-only">
            Número (com código de área)
          </label>
          <input
            id={id ? `${id}-national` : undefined}
            type="tel"
            inputMode="numeric"
            autoComplete="tel"
            value={nationalNumber}
            onChange={handleNationalNumberChange}
            disabled={disabled}
            required={required}
            placeholder="Ex.: 11 1234-5678"
            className={cn('placeholder:text-muted-foreground', inputBaseCn)}
            aria-label="Número com código de área"
          />
        </div>
      )}
    </div>
  )
}
