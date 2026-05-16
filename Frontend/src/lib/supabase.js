import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_ANON) {
  console.error('Missing Supabase env vars. Check your .env file.')
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON)

/**
 * Fetch all incidents ordered by creation time (newest first).
 */
export async function fetchIncidents() {
  const { data, error } = await supabase
    .from('incidents')
    .select('*')
    .order('created_at', { ascending: false })

  if (error) console.error('fetchIncidents error:', error)
  return data ?? []
}

/**
 * Subscribe to new incidents being inserted.
 * @param {(incident: object) => void} onInsert
 * @returns Supabase channel (call supabase.removeChannel(channel) to unsubscribe)
 */
export function subscribeToIncidents(onInsert) {
  return supabase
    .channel('incidents-realtime')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'incidents' },
      payload => onInsert(payload.new)
    )
    .subscribe()
}