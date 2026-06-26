const EVENT_TYPES = [
  { value: undefined, label: 'All' },
  { value: 'goal_created', label: 'Goals' },
  { value: 'feedback', label: 'Feedback' },
  { value: 'peer_review', label: 'Peer Review' },
  { value: 'achievement', label: 'Achievements' },
  { value: 'check_in', label: 'Check-ins' },
  { value: 'progress_updated', label: 'Progress' },
] as const

interface Props {
  activeFilter: string | undefined
  onChange: (filter: string | undefined) => void
}

export default function TimelineFilterPills({ activeFilter, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Filter timeline by event type">
      {EVENT_TYPES.map(({ value, label }) => {
        const isActive = activeFilter === value
        return (
          <button
            key={label}
            onClick={() => onChange(value)}
            aria-pressed={isActive}
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
              isActive
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
