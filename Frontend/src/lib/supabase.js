import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_ANON) {
  throw new Error('[ResQNet] Missing Supabase env vars — check your .env file.')
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON)

export async function fetchIncidents() {
  const { data, error } = await supabase
    .from('incidents')
    .select('*, users(name, contact_number)')
    .order('created_at', { ascending: false })
  if (error) console.error('fetchIncidents:', error)
  return data ?? []
}

export function subscribeToIncidents(onInsert) {
  return supabase
    .channel('resqnet-incidents')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'incidents' },
      payload => onInsert(payload.new)
    )
    .subscribe()
}