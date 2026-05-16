-- 1. Create Enums
CREATE TYPE incident_type_enum AS ENUM ('MEDICAL', 'DISASTER');
CREATE TYPE incident_status_enum AS ENUM ('PENDING', 'IN_PROGRESS', 'RESOLVED');

-- 2. Create Users Table (Callers)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id VARCHAR UNIQUE,
    name VARCHAR,
    contact_number VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert a default "Unknown Caller" for testing MVP without Telegram
INSERT INTO users (telegram_id, name) VALUES ('SYSTEM_DEFAULT', 'Unknown Caller');

-- 3. Create Agents Table (Responders/Doctors)
-- Links directly to Supabase Auth table
CREATE TABLE agents (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR,
    role VARCHAR DEFAULT 'Responder',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Create Incidents Table
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    incident_type incident_type_enum,
    urgency_score FLOAT,
    transcript TEXT,
    structured_data JSONB,
    status incident_status_enum DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Enable Realtime on Incidents
ALTER PUBLICATION supabase_realtime ADD TABLE incidents;

-- 6. Trigger to auto-create Agent on Auth Signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.agents (id, name, role)
    VALUES (new.id, split_part(new.email, '@', 1), 'Responder');
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
