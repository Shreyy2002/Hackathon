import { useState, useRef, useCallback } from 'react'
import TimelineFilterPills from './TimelineFilterPills'
import TimelineEventCard from './TimelineEventCard'
import { useEmployeeTimeline } from '../../hooks/useEmployeeTimeline'

interface Props {
  employeeId: string
}

export default function TimelineView({ employeeId }: Props) {
  const [filter, setFilter] = useState<string | undefined>(undefined)
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useEmployeeTimeline(employeeId, filter)

  // Reset filter and re-fetch when the pill selection changes
  const handleFilterChange = (newFilter: string | undefined) => {
    setFilter(newFilter)
  }

  // Infinite scroll: IntersectionObserver on a sentinel div at the bottom
  const observer = useRef<IntersectionObserver | null>(null)
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (isFetchingNextPage) return
      if (observer.current) observer.current.disconnect()
      if (!node) return
      observer.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasNextPage) fetchNextPage()
      })
      observer.current.observe(node)
    },
    [isFetchingNextPage, hasNextPage, fetchNextPage]
  )

  const events = data?.pages.flat() ?? []

  return (
    <div className="space-y-4">
      <TimelineFilterPills activeFilter={filter} onChange={handleFilterChange} />

      {isLoading && (
        <p className="text-sm text-gray-500">Loading timeline…</p>
      )}

      {!isLoading && events.length === 0 && (
        <p className="text-sm text-gray-500">No events found.</p>
      )}

      <div className="space-y-3">
        {events.map((event) => (
          <TimelineEventCard key={event.id} event={event} />
        ))}
      </div>

      {/* Sentinel element — triggers next page load when scrolled into view */}
      <div ref={sentinelRef} className="h-4" aria-hidden="true" />

      {isFetchingNextPage && (
        <p className="text-center text-xs text-gray-400">Loading more…</p>
      )}

      {!hasNextPage && events.length > 0 && (
        <p className="text-center text-xs text-gray-400">End of timeline</p>
      )}
    </div>
  )
}
