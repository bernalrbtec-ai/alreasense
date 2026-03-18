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
    // Campo "Número" deve aceitar apenas o número (DDD/país já estão no dropdown).
    const raw = e.target.value.replace(/\D/g, '').slice(0, 11)
    setNumberPart(raw)
    notifyBrazil(effectiveDdd, raw)
  }

  const handleNationalNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 15)
    setNationalNumber(raw)
    notifyInternational(selectedCountryDial, raw)
  }

  const inputBaseCn = cn(
    'h-9 sm:h-10 rounded-md border border-border bg-background text-foreground px-2 py-2 text-sm',
    'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ring-offset-background',
    'disabled:cursor-not-allowed disabled:opacity-50',
    inputClassName
  )

  return (
    <div className={cn('flex flex-nowrap items-stretch gap-2', className)}>
      <div className="flex flex-col gap-1 flex-shrink-0 w-[90px] sm:w-[100px]">
        <label htmlFor={id ? `${id}-country` : undefined} className="sr-only">
          País
        </label>
        <select
          id={id ? `${id}-country` : undefined}
          value={selectedCountryDial}
          onChange={handleCountryChange}
          disabled={disabled}
          className={cn('truncate', inputBaseCn)}
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
              className={cn('w-[64px] sm:w-[72px]', inputBaseCn)}
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
            <div className="flex flex-col gap-1 flex-shrink-0 w-[52px] sm:w-[60px]">
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
          <div className="flex-1 min-w-0 flex flex-col gap-1">
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
        <div className="flex-1 min-w-0 flex flex-col gap-1">
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
