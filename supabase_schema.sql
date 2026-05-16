-- ResQNet schema (idempotent). Run in Supabase SQL Editor or: python Backend/setup_schema.py

-- Enums
DO $$ BEGIN
  CREATE TYPE incident_type_enum AS ENUM ('MEDICAL', 'DISASTER');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE incident_status_enum AS ENUM ('PENDING', 'IN_PROGRESS', 'RESOLVED');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Callers (telegram / phone)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id VARCHAR UNIQUE,
    name VARCHAR,
    contact_number VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO users (telegram_id, name)
VALUES ('SYSTEM_DEFAULT', 'Unknown Caller')
ON CONFLICT (telegram_id) DO NOTHING;

-- Agents (linked to Supabase Auth)
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR,
    role VARCHAR DEFAULT 'Agent',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Incidents
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    incident_type incident_type_enum,
    urgency_score FLOAT DEFAULT 0,
    transcript TEXT,
    structured_data JSONB DEFAULT '{}'::jsonb,
    status incident_status_enum DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS incidents_created_at_idx ON incidents (created_at DESC);

-- Hot path for the claim-queue lookup ("PENDING + unassigned, by urgency")
-- and for fetching an agent's own active cases.
CREATE INDEX IF NOT EXISTS incidents_pending_unassigned_idx
  ON incidents (urgency_score DESC, created_at DESC)
  WHERE status = 'PENDING' AND agent_id IS NULL;

CREATE INDEX IF NOT EXISTS incidents_agent_id_idx
  ON incidents (agent_id)
  WHERE agent_id IS NOT NULL;

-- Realtime
DO $$ BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Auto-create agent profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_agent()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.agents (id, name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'role', 'Agent')
  )
  ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    role = EXCLUDED.role;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_agent_created ON auth.users;
CREATE TRIGGER on_auth_agent_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_agent();

-- RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agents read own profile" ON agents;
CREATE POLICY "agents read own profile" ON agents
  FOR SELECT TO authenticated USING (id = auth.uid());

-- Visibility rules for the queue:
--   1. Any registered agent may see PENDING incidents that nobody has claimed
--      yet (the claimable pool).
--   2. An agent may see incidents that are assigned specifically to them
--      (their own active workload).
--   3. Everything else (incidents in progress for a DIFFERENT agent, or
--      already resolved by someone else) is hidden.
-- This policy is also what Supabase Realtime evaluates per subscriber, so
-- when an agent claims a row the row "disappears" from every other agent's
-- live dashboard automatically.
DROP POLICY IF EXISTS "agents read incidents" ON incidents;
DROP POLICY IF EXISTS "agents read claimable or own incidents" ON incidents;
CREATE POLICY "agents read claimable or own incidents" ON incidents
  FOR SELECT TO authenticated
  USING (
    EXISTS (SELECT 1 FROM agents WHERE agents.id = auth.uid())
    AND (
      (status = 'PENDING' AND agent_id IS NULL)
      OR agent_id = auth.uid()
    )
  );

-- Direct UPDATE from the client is intentionally NOT granted. All status /
-- agent_id transitions must go through the claim_incident() function below
-- (or other future RPCs), which take an explicit row lock to prevent two
-- agents from both believing they won the race.
DROP POLICY IF EXISTS "agents update incidents" ON incidents;

DROP POLICY IF EXISTS "agents read callers" ON users;
CREATE POLICY "agents read callers" ON users
  FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM agents WHERE agents.id = auth.uid()));

-- ─── Atomic case-claim RPC ─────────────────────────────────────────────
-- Concurrency model (fastest-agent-wins):
--   * `SELECT ... FOR UPDATE` takes a row-level lock on the target incident.
--     If two agents race, Postgres serializes them through this lock; the
--     first transaction to acquire it commits the claim, the second blocks
--     until the first commits, then re-reads the row and sees status has
--     already flipped to 'IN_PROGRESS' and bails with ALREADY_CLAIMED.
--   * The status / agent_id guard is checked AFTER the lock is held, so
--     there is no time-of-check-to-time-of-use window — a second claimer
--     can never observe the row as PENDING+unassigned after the lock has
--     been transferred.
--   * SECURITY DEFINER lets the function modify `incidents` regardless of
--     RLS write policies. The caller (FastAPI backend) is responsible for
--     verifying the agent JWT and passing the verified `p_agent_id`.
--   * Errors are raised with explicit messages ('INCIDENT_NOT_FOUND',
--     'ALREADY_CLAIMED', 'AGENT_NOT_REGISTERED') so the API layer can map
--     them to 404 / 409 / 403 cleanly.
CREATE OR REPLACE FUNCTION public.claim_incident(
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

  -- Row-level lock. Other concurrent claim_incident() calls for the same
  -- incident_id queue up here; the loser will see the post-claim state.
  SELECT * INTO v_locked
  FROM incidents
  WHERE id = p_incident_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'INCIDENT_NOT_FOUND' USING ERRCODE = 'P0002';
  END IF;

  IF v_locked.status <> 'PENDING' OR v_locked.agent_id IS NOT NULL THEN
    RAISE EXCEPTION 'ALREADY_CLAIMED' USING ERRCODE = '40001';
  END IF;

  RETURN QUERY
    UPDATE incidents
       SET status = 'IN_PROGRESS',
           agent_id = p_agent_id
     WHERE id = p_incident_id
    RETURNING *;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_incident(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.claim_incident(uuid, uuid)
  TO authenticated, service_role;
