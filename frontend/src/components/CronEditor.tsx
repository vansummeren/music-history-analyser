/**
 * CronEditor — a human-friendly builder for standard 5-part cron expressions.
 *
 * Provides quick presets plus a free-text field for advanced expressions.
 */

interface Props {
  value: string
  onChange: (cron: string) => void
}

const PRESETS = [
  { label: 'Every Monday 08:00', value: '0 8 * * 1' },
  { label: 'Every day 08:00', value: '0 8 * * *' },
  { label: 'Every Sunday 10:00', value: '0 10 * * 0' },
  { label: 'Every Friday 17:00', value: '0 17 * * 5' },
  { label: 'First of the month 09:00', value: '0 9 1 * *' },
  { label: 'Custom…', value: 'custom' },
]

export default function CronEditor({ value, onChange }: Props) {
  const isPreset = PRESETS.some((p) => p.value === value && p.value !== 'custom')
  const selectValue = isPreset ? value : 'custom'

  function handlePresetChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const v = e.target.value
    if (v !== 'custom') {
      onChange(v)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <select
        value={selectValue}
        onChange={handlePresetChange}
        className="w-full rounded bg-white/10 px-3 py-2 text-white focus:outline-none"
      >
        {PRESETS.map((p) => (
          <option key={p.value} value={p.value} className="text-black">
            {p.label}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. 0 8 * * 1"
        className="w-full rounded bg-white/10 px-3 py-2 font-mono text-sm text-white placeholder-brand-400 focus:outline-none"
        aria-label="Cron expression"
      />
      <p className="text-xs text-brand-400">
        Format: <code>minute hour day-of-month month day-of-week</code> (UTC)
      </p>
    </div>
  )
}
