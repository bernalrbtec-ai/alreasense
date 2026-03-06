import { useState, useEffect, useMemo } from 'react'
import { BRAZIL_DDD_LIST, DEFAULT_DDD, VALUE_OTHER_DDD, parseE164ToDDDAndNumber, buildE164 } from '../lib/phoneDDD'
import { cn } from '../lib/utils'

interface PhoneInputWithDDDProps {
  value: string
  onChange: (e164: string) => void
  defaultDdd?: string
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
  id,
  className,
  inputClassName,
  required,
  placeholder = '99999-9999',
  disabled
}: PhoneInputWithDDDProps) {
  const parsed = useMemo(() => parseE164ToDDDAndNumber(value || ''), [value])
  const [selectedDddKey, setSelectedDddKey] = useState<string>(parsed.ddd || defaultDdd)
  const [otherDdd, setOtherDdd] = useState(parsed.ddd && !BRAZIL_DDD_LIST.includes(parsed.ddd as any) ? parsed.ddd : '')
  const [numberPart, setNumberPart] = useState(parsed.number || '')

  const isOther = selectedDddKey === VALUE_OTHER_DDD
  const effectiveDdd = isOther ? otherDdd.replace(/\D/g, '').slice(0, 2) : selectedDddKey

  useEffect(() => {
    const p = parseE164ToDDDAndNumber(value || '')
    setNumberPart(p.number)
    if (value && value.trim() !== '') {
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
    }
  }, [value, defaultDdd])

  const notify = (ddd: string, num: string) => {
    const e164 = buildE164(ddd, num)
    onChange(e164)
  }

  const handleDddSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value
    setSelectedDddKey(v)
    if (v !== VALUE_OTHER_DDD) {
      setOtherDdd('')
      notify(v, numberPart)
    } else {
      notify('', numberPart)
    }
  }

  const handleOtherDddChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 2)
    setOtherDdd(raw)
    notify(raw, numberPart)
  }

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 11)
    setNumberPart(raw)
    notify(effectiveDdd, raw)
  }

  return (
    <div className={cn('flex gap-2', className)}>
      <div className="flex flex-col gap-1 flex-shrink-0">
        <label htmlFor={id ? `${id}-ddd` : undefined} className="sr-only">DDD</label>
        <select
          id={id ? `${id}-ddd` : undefined}
          value={selectedDddKey}
          onChange={handleDddSelect}
          disabled={disabled}
          className={cn(
            'h-9 sm:h-10 w-[90px] rounded-md border border-border bg-background text-foreground px-2 py-2 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ring-offset-background',
            'disabled:cursor-not-allowed disabled:opacity-50',
            inputClassName
          )}
          aria-label="DDD"
        >
          {BRAZIL_DDD_LIST.map((ddd) => (
            <option key={ddd} value={ddd}>{ddd}</option>
          ))}
          <option value={VALUE_OTHER_DDD}>Outro</option>
        </select>
      </div>
      {isOther && (
        <div className="flex flex-col gap-1 flex-shrink-0 w-[70px]">
          <label htmlFor={id ? `${id}-other-ddd` : undefined} className="sr-only">DDD (outro)</label>
          <input
            id={id ? `${id}-other-ddd` : undefined}
            type="tel"
            inputMode="numeric"
            maxLength={2}
            value={otherDdd}
            onChange={handleOtherDddChange}
            disabled={disabled}
            placeholder="DD"
            className={cn(
              'h-9 sm:h-10 w-full rounded-md border border-border bg-background text-foreground px-2 py-2 text-sm text-center',
              'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ring-offset-background',
              'disabled:cursor-not-allowed disabled:opacity-50',
              inputClassName
            )}
            aria-label="DDD (outro)"
          />
        </div>
      )}
      <div className="flex-1 min-w-0 flex flex-col gap-1">
        <label htmlFor={id ? `${id}-number` : undefined} className="sr-only">Número</label>
        <input
          id={id ? `${id}-number` : undefined}
          type="tel"
          inputMode="numeric"
          value={numberPart}
          onChange={handleNumberChange}
          disabled={disabled}
          required={required}
          placeholder={placeholder}
          className={cn(
            'h-9 sm:h-10 w-full rounded-md border border-border bg-background text-foreground placeholder:text-muted-foreground px-3 py-2 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ring-offset-background',
            'disabled:cursor-not-allowed disabled:opacity-50',
            inputClassName
          )}
          aria-label="Número do telefone"
        />
      </div>
    </div>
  )
}
