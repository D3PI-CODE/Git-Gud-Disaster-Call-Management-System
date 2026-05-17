-- Deploy resolve_incident RPC (run via Supabase SQL Editor or supabase db push)
CREATE OR REPLACE FUNCTION public.resolve_incident(
  p_incident_id UUID,
  p_agent_id UUID
)
RETURNS SETOF incidents
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_locked incidents%ROWTYPE;
BEGIN
  IF p_agent_id IS NULL THEN
    RAISE EXCEPTION 'AGENT_NOT_REGISTERED' USING ERRCODE = '28000';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM agents WHERE id = p_agent_id) THEN
    RAISE EXCEPTION 'AGENT_NOT_REGISTERED' USING ERRCODE = '28000';
  END IF;

  SELECT * INTO v_locked
  FROM incidents
  WHERE id = p_incident_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'INCIDENT_NOT_FOUND' USING ERRCODE = 'P0002';
  END IF;

  IF v_locked.status <> 'IN_PROGRESS' OR v_locked.agent_id IS DISTINCT FROM p_agent_id THEN
    RAISE EXCEPTION 'NOT_OWNED_OR_NOT_ACTIVE' USING ERRCODE = '40001';
  END IF;

  RETURN QUERY
    UPDATE incidents
       SET status = 'RESOLVED'
     WHERE id = p_incident_id
    RETURNING *;
END;
$$;

REVOKE ALL ON FUNCTION public.resolve_incident(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.resolve_incident(uuid, uuid)
  TO authenticated, service_role;

NOTIFY pgrst, 'reload schema';
