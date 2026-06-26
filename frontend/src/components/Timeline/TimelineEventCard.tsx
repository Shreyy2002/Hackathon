import { formatDistanceToNow } from 'date-fns'
import type { TimelineEvent } from '../../api/client'

interface Props {
  event: TimelineEvent
}

/** Returns a border class based on event type */
function getBorderClass(eventType: string): string {
  if (eventType === 'achievement') return 'border-yellow-400'
  return 'border-gray-200'
}

/** Returns an icon prefix for event types that warrant one */
function getEventIcon(eventType: string): string {
  if (eventType === 'feedback' || eventType === 'peer_review') return '💬 '
  if (eventType === 'achievement') return '🏆 '
  if (eventType === 'progress_updated') return '📊 '
  if (eventType === 'check_in') return '📅 '
  if (eventType === 'goal_created') return '🎯 '
  if (eventType === 'goal_submitted') return '📤 '
  if (eventType === 'goal_approved') return '✅ '
  if (eventType === 'goal_rejected') return '❌ '
  return '📌 '
}

/** Produces a human-readable summary from an event's payload */
function getPayloadSummary(eventType: string, payload: Record<string, unknown>): string {
  switch (eventType) {
    case 'goal_created':
      return `Goal "${payload.title ?? 'Untitled'}" created with status "${payload.status ?? 'draft'}".`

    case 'goal_submitted':
      return `Goal "${payload.title ?? 'Untitled'}" submitted for approval.`

    case 'goal_approved': {
      const note = payload.note ? ` Note: ${payload.note}` : ''
      return `Goal "${payload.title ?? 'Untitled'}" approved.${note}`
    }

    case 'goal_rejected': {
      const note = payload.note ? ` Reason: ${payload.note}` : ''
      return `Goal "${payload.title ?? 'Untitled'}" rejected.${note}`
    }

    case 'progress_updated': {
      const prev = payload.previous_progress as number | undefined
      const next = payload.new_progress as number | undefined
      const prevHealth = payload.previous_health as string | undefined
      const nextHealth = payload.new_health as string | undefined
      const note = payload.note ? ` — ${payload.note}` : ''
      if (prev !== undefined && next !== undefined) {
        let summary = `Progress updated from ${prev}% to ${next}%.`
        if (prevHealth && nextHealth && prevHealth !== nextHealth) {
          summary += ` Health changed from ${prevHealth} to ${nextHealth}.`
        }
        return summary + note
      }
      return `Progress updated.${note}`
    }

    case 'feedback':
    case 'peer_review': {
      const text = payload.text as string | undefined
      const anon = payload.is_anonymous ? 'Anonymous' : `From ${payload.from_user_id ?? 'unknown'}`
      return text ? `${anon}: "${text.slice(0, 120)}${text.length > 120 ? '…' : ''}"` : `${anon} submitted ${eventType}.`
    }

    case 'achievement': {
      const desc = payload.description as string | undefined
      return `"${payload.title ?? 'Achievement'}"${desc ? `: ${desc.slice(0, 100)}${desc.length > 100 ? '…' : ''}` : ''}`
    }

    case 'check_in': {
      const items = payload.action_items as string[] | undefined
      const itemCount = items?.length ?? 0
      return `Check-in on ${payload.meeting_date ?? 'unknown date'}. ${itemCount} action item${itemCount !== 1 ? 's' : ''}.`
    }

    case 'evidence_tagged':
      return `Event tagged as evidence for goal.`

    default:
      return Object.entries(payload)
        .slice(0, 3)
        .map(([k, v]) => `${k}: ${String(v)}`)
        .join(', ')
  }
}

/** Human-friendly label for an event type slug */
function getEventTypeLabel(eventType: string): string {
  const labels: Record<string, string> = {
    goal_created: 'Goal Created',
    goal_submitted: 'Goal Submitted',
    goal_approved: 'Goal Approved',
    goal_rejected: 'Goal Rejected',
    progress_updated: 'Progress Update',
    feedback: 'Feedback',
    peer_review: 'Peer Review',
    achievement: 'Achievement',
    check_in: 'Check-in',
    evidence_tagged: 'Evidence Tagged',
  }
  return labels[eventType] ?? eventType.replace(/_/g, ' ')
}

export default function TimelineEventCard({ event }: Props) {
  const borderClass = getBorderClass(event.event_type)
  const icon = getEventIcon(event.event_type)
  const summary = getPayloadSummary(event.event_type, event.payload)
  const timeAgo = formatDistanceToNow(new Date(event.created_at), { addSuffix: true })

  return (
    <article
      className={`rounded-lg border-l-4 bg-white p-4 shadow-sm ${borderClass}`}
      aria-label={`${getEventTypeLabel(event.event_type)} event`}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: icon + type label + summary */}
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-900">
              {icon}{getEventTypeLabel(event.event_type)}
            </span>
            {event.is_evidence && (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                Evidence
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600">{summary}</p>
        </div>

        {/* Right: timestamp */}
        <time
          className="shrink-0 text-xs text-gray-400"
          dateTime={event.created_at}
          title={event.created_at}
        >
          {timeAgo}
        </time>
      </div>
    </article>
  )
}
