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

DROP POLICY IF EXISTS "agents read incidents" ON incidents;
CREATE POLICY "agents read incidents" ON incidents
  FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM agents WHERE agents.id = auth.uid()));

DROP POLICY IF EXISTS "agents read callers" ON users;
CREATE POLICY "agents read callers" ON users
  FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM agents WHERE agents.id = auth.uid()));
