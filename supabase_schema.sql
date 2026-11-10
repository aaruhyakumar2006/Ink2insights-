-- ==============================================================================
-- I2 insights — Supabase Cloud Database Schema v2
-- Run this in your Supabase Dashboard: SQL Editor -> New Query -> Run
-- ==============================================================================

-- 1. Doctors / Users Profile Table
CREATE TABLE IF NOT EXISTS public.doctors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_id UUID UNIQUE,                          -- links to auth.users.id
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    specialization TEXT DEFAULT 'General Physician',
    phone TEXT,
    avatar_url TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Screening Health Camps Table
CREATE TABLE IF NOT EXISTS public.camps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date_str TEXT DEFAULT 'Today',
    location TEXT,
    expected_records INTEGER DEFAULT 100,
    created_by UUID REFERENCES public.doctors(id),
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Patient Intake Records Table (Strictly isolated by camp_id)
CREATE TABLE IF NOT EXISTS public.records (
    id TEXT PRIMARY KEY,
    camp_id TEXT NOT NULL REFERENCES public.camps(id) ON DELETE CASCADE,
    person_name TEXT NOT NULL,
    age TEXT,
    gender TEXT,
    dob TEXT,
    blood_group TEXT,
    mobile_number TEXT,
    address TEXT,
    height TEXT,
    weight TEXT,
    blood_pressure TEXT,
    pulse TEXT,
    rbs TEXT,
    waist_circumference TEXT,
    known_allergies TEXT,
    examination_details TEXT,
    referral_details TEXT,
    missing_fields JSONB DEFAULT '[]'::jsonb,
    uncertain_fields JSONB DEFAULT '[]'::jsonb,
    extraction_notes TEXT,
    structured_record JSONB,
    status TEXT DEFAULT 'needs_review',             -- 'needs_review' | 'reviewed' | 'failed'
    page1_preview TEXT,
    page2_preview TEXT,
    scanned_by UUID REFERENCES public.doctors(id),  -- doctor who scanned
    reviewer_notes TEXT,
    reviewed_by TEXT,                                -- doctor name who reviewed
    reviewed_by_id UUID REFERENCES public.doctors(id),
    reviewed_at TIMESTAMPTZ,
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. High Performance Indexes
CREATE INDEX IF NOT EXISTS idx_records_camp_id ON public.records(camp_id);
CREATE INDEX IF NOT EXISTS idx_records_status ON public.records(status);
CREATE INDEX IF NOT EXISTS idx_records_created_at ON public.records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_records_scanned_by ON public.records(scanned_by);
CREATE INDEX IF NOT EXISTS idx_records_person_name ON public.records(person_name);
CREATE INDEX IF NOT EXISTS idx_records_is_deleted ON public.records(is_deleted);
CREATE INDEX IF NOT EXISTS idx_camps_is_deleted ON public.camps(is_deleted);
CREATE INDEX IF NOT EXISTS idx_camps_created_by ON public.camps(created_by);
CREATE INDEX IF NOT EXISTS idx_doctors_email ON public.doctors(email);
CREATE INDEX IF NOT EXISTS idx_doctors_auth_id ON public.doctors(auth_id);

-- 5. Enable Row Level Security (RLS) as a Second Defense Layer
ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.camps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.records ENABLE ROW LEVEL SECURITY;

-- Ensure tenant linkage columns exist on tables
ALTER TABLE public.camps ADD COLUMN IF NOT EXISTS community_id TEXT;
ALTER TABLE public.records ADD COLUMN IF NOT EXISTS community_id TEXT;
ALTER TABLE public.records ADD COLUMN IF NOT EXISTS org_id TEXT;
ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS community_id TEXT;

-- 6. Multi-Tenant Access Policies (Strictly scoped by app_metadata -> org_id)
-- Admin role is intra-org only; cross-org bypass (OR role = 'admin') is removed.

-- Camps RLS:
CREATE POLICY "Tenant read camps" ON public.camps
    FOR SELECT TO authenticated
    USING (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant insert camps" ON public.camps
    FOR INSERT TO authenticated
    WITH CHECK (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant update camps" ON public.camps
    FOR UPDATE TO authenticated
    USING (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    )
    WITH CHECK (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant delete camps" ON public.camps
    FOR DELETE TO authenticated
    USING (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

-- Records RLS:
CREATE POLICY "Tenant read records" ON public.records
    FOR SELECT TO authenticated
    USING (
        COALESCE(community_id, org_id) = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant insert records" ON public.records
    FOR INSERT TO authenticated
    WITH CHECK (
        COALESCE(community_id, org_id) = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant update records" ON public.records
    FOR UPDATE TO authenticated
    USING (
        COALESCE(community_id, org_id) = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    )
    WITH CHECK (
        COALESCE(community_id, org_id) = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant delete records" ON public.records
    FOR DELETE TO authenticated
    USING (
        COALESCE(community_id, org_id) = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

-- Doctors RLS:
CREATE POLICY "Tenant read doctors" ON public.doctors
    FOR SELECT TO authenticated
    USING (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant insert doctors" ON public.doctors
    FOR INSERT TO authenticated
    WITH CHECK (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant update doctors" ON public.doctors
    FOR UPDATE TO authenticated
    USING (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    )
    WITH CHECK (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

CREATE POLICY "Tenant delete doctors" ON public.doctors
    FOR DELETE TO authenticated
    USING (
        community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id')
    );

-- Communities table RLS:
CREATE TABLE IF NOT EXISTS public.communities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    creator_name TEXT NOT NULL,
    creator_email TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);
ALTER TABLE public.communities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant read communities" ON public.communities
    FOR SELECT TO authenticated
    USING (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant insert communities" ON public.communities
    FOR INSERT TO authenticated
    WITH CHECK (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant update communities" ON public.communities
    FOR UPDATE TO authenticated
    USING (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant delete communities" ON public.communities
    FOR DELETE TO authenticated
    USING (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

-- Usage Ledger & Orgs tables RLS:
CREATE TABLE IF NOT EXISTS public.orgs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT DEFAULT 'outreach_10k',
    papers_included INTEGER DEFAULT 10000,
    papers_used INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.orgs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant read orgs" ON public.orgs
    FOR SELECT TO authenticated
    USING (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant insert orgs" ON public.orgs
    FOR INSERT TO authenticated
    WITH CHECK (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant update orgs" ON public.orgs
    FOR UPDATE TO authenticated
    USING (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant delete orgs" ON public.orgs
    FOR DELETE TO authenticated
    USING (id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE TABLE IF NOT EXISTS public.usage_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL REFERENCES public.orgs(id),
    record_id TEXT,
    event_type TEXT NOT NULL,
    paper_delta INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.usage_ledger ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant read usage_ledger" ON public.usage_ledger
    FOR SELECT TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant insert usage_ledger" ON public.usage_ledger
    FOR INSERT TO authenticated
    WITH CHECK (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant update usage_ledger" ON public.usage_ledger
    FOR UPDATE TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant delete usage_ledger" ON public.usage_ledger
    FOR DELETE TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

-- Files table RLS:
CREATE TABLE IF NOT EXISTS public.files (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    record_id TEXT,
    file_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant read files" ON public.files
    FOR SELECT TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant insert files" ON public.files
    FOR INSERT TO authenticated
    WITH CHECK (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant update files" ON public.files
    FOR UPDATE TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE POLICY "Tenant delete files" ON public.files
    FOR DELETE TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

-- 7. Supabase Storage Bucket for Scanned Page Images (Private & Authenticated)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'intake-scans',
    'intake-scans',
    false,  -- Private PHI bucket
    15728640,  -- 15 MB
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/heic']
)
ON CONFLICT (id) DO UPDATE SET public = false;

-- Secure Storage policies for intake-scans bucket
DROP POLICY IF EXISTS "Allow public upload intake-scans" ON storage.objects;
DROP POLICY IF EXISTS "Allow public read intake-scans" ON storage.objects;
DROP POLICY IF EXISTS "Allow public delete intake-scans" ON storage.objects;

CREATE POLICY "Tenant upload intake-scans" ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (bucket_id = 'intake-scans');

CREATE POLICY "Tenant read intake-scans" ON storage.objects
    FOR SELECT TO authenticated
    USING (bucket_id = 'intake-scans');

CREATE POLICY "Tenant delete intake-scans" ON storage.objects
    FOR DELETE TO authenticated
    USING (bucket_id = 'intake-scans');

-- 8. Missing Segregated Intake & Audit Tables
CREATE TABLE IF NOT EXISTS public.adult_records (
    id TEXT PRIMARY KEY REFERENCES public.records(id) ON DELETE CASCADE,
    camp_id TEXT NOT NULL REFERENCES public.camps(id) ON DELETE CASCADE,
    community_id TEXT,
    person_name TEXT NOT NULL,
    age TEXT,
    gender TEXT,
    blood_pressure TEXT,
    height TEXT,
    weight TEXT,
    examination_details TEXT,
    referral_details TEXT,
    missing_fields JSONB DEFAULT '[]'::jsonb,
    uncertain_fields JSONB DEFAULT '[]'::jsonb,
    structured_record JSONB,
    status TEXT DEFAULT 'needs_review',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.adult_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Tenant adult_records access" ON public.adult_records
    FOR ALL TO authenticated
    USING (community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE TABLE IF NOT EXISTS public.paediatric_records (
    id TEXT PRIMARY KEY REFERENCES public.records(id) ON DELETE CASCADE,
    camp_id TEXT NOT NULL REFERENCES public.camps(id) ON DELETE CASCADE,
    community_id TEXT,
    person_name TEXT NOT NULL,
    age TEXT,
    gender TEXT,
    blood_pressure TEXT,
    height TEXT,
    weight TEXT,
    paediatric_alerts JSONB DEFAULT '[]'::jsonb,
    examination_details TEXT,
    referral_details TEXT,
    missing_fields JSONB DEFAULT '[]'::jsonb,
    uncertain_fields JSONB DEFAULT '[]'::jsonb,
    structured_record JSONB,
    status TEXT DEFAULT 'needs_review',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.paediatric_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Tenant paediatric_records access" ON public.paediatric_records
    FOR ALL TO authenticated
    USING (community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (community_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE TABLE IF NOT EXISTS public.record_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_role TEXT NOT NULL,
    action TEXT NOT NULL,
    changes JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.record_audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Tenant audit log access" ON public.record_audit_log
    FOR ALL TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE TABLE IF NOT EXISTS public.payments (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES public.orgs(id),
    amount_rs NUMERIC(10, 2) NOT NULL,
    gst_rs NUMERIC(10, 2) NOT NULL,
    papers_credited INTEGER NOT NULL,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Tenant payments access" ON public.payments
    FOR ALL TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

CREATE TABLE IF NOT EXISTS public.invoices (
    id TEXT PRIMARY KEY,
    number TEXT UNIQUE NOT NULL,
    org_id TEXT NOT NULL REFERENCES public.orgs(id),
    amount_rs NUMERIC(10, 2) NOT NULL,
    pdf_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Tenant invoices access" ON public.invoices
    FOR ALL TO authenticated
    USING (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'))
    WITH CHECK (org_id = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

-- 9. Enable Realtime Publications for Multi-Doctor Live Sync
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.camps, public.records, public.doctors;
  END IF;
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- 10. Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_doctors_updated_at BEFORE UPDATE ON public.doctors
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_camps_updated_at BEFORE UPDATE ON public.camps
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_records_updated_at BEFORE UPDATE ON public.records
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_adult_records_updated_at BEFORE UPDATE ON public.adult_records
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_paediatric_records_updated_at BEFORE UPDATE ON public.paediatric_records
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
