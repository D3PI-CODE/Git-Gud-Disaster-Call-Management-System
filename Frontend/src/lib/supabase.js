import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_ANON) {
  throw new Error(
    'Missing Supabase environment variables: VITE_SUPABASE_URL and/or VITE_SUPABASE_ANON_KEY. Check your .env file and restart the dev server.'
  )
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