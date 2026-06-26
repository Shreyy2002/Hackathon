import { useEffect } from 'react'
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { getTimelineEvents, type TimelineEvent } from '../api/client'

export function useEmployeeTimeline(employeeId: string, eventTypeFilter?: string) {
  const queryClient = useQueryClient()

  // WebSocket subscription — optimistically prepend new events
  useEffect(() => {
    if (!employeeId) return

    const wsUrl = `ws://localhost:8000/ws/${employeeId}`
    const ws = new WebSocket(wsUrl)

    ws.onmessage = (event) => {
      try {
        const data: TimelineEvent = JSON.parse(event.data)
        queryClient.setQueryData(
          ['timeline', employeeId, eventTypeFilter],
          (old: { pages: TimelineEvent[][] } | undefined) => {
            if (!old) return old
            const newPages = [[data, ...old.pages[0]], ...old.pages.slice(1)]
            return { ...old, pages: newPages }
          }
        )
      } catch {
        // Silently ignore malformed messages
      }
    }

    return () => ws.close()
  }, [employeeId, eventTypeFilter, queryClient])

  return useInfiniteQuery({
    queryKey: ['timeline', employeeId, eventTypeFilter],
    queryFn: ({ pageParam = 0 }) =>
      getTimelineEvents({
        employee_id: employeeId,
        offset: pageParam as number,
        limit: 20,
        event_type: eventTypeFilter,
      }),
    getNextPageParam: (lastPage, pages) =>
      lastPage.length === 20 ? pages.length * 20 : undefined,
    initialPageParam: 0,
    enabled: !!employeeId,
  })
}
