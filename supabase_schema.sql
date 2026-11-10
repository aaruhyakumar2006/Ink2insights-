-- I2I Medical Records System - Supabase PostgreSQL Schema
-- Generated for: https://wiwclaxgwxnblsltdkym.supabase.co
-- This schema defines all tables, relationships, and indexes for the I2I system
-- Compatible with PostgreSQL 12+

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. COMMUNITIES TABLE (Team Workspace / Clinic Organization)
-- ============================================================================
CREATE TABLE IF NOT EXISTS communities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    creator_name TEXT NOT NULL,
    creator_email TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_communities_code ON communities(code);

-- ============================================================================
-- 2. DOCTORS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS doctors (
    id TEXT PRIMARY KEY,
    auth_id TEXT UNIQUE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    specialization TEXT DEFAULT 'General Physician',
    avatar_url TEXT,
    phone TEXT,
    community_id TEXT REFERENCES communities(id) ON DELETE SET NULL,
    community_code TEXT,
    community_role TEXT DEFAULT 'doctor',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_doctors_email ON doctors(email);
CREATE INDEX idx_doctors_auth_id ON doctors(auth_id);
CREATE INDEX idx_doctors_community ON doctors(community_id);

-- ============================================================================
-- 3. CAMPS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS camps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date_str TEXT NOT NULL,
    expected_records INTEGER NOT NULL DEFAULT 100,
    location TEXT DEFAULT 'Chennai Health Camp',
    created_by TEXT,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    target_group TEXT NOT NULL DEFAULT 'adult',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_camps_community ON camps(community_id);
CREATE INDEX idx_camps_target_group ON camps(target_group);

-- ============================================================================
-- 4. ADULT RECORDS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS adult_records (
    id TEXT PRIMARY KEY,
    camp_id TEXT NOT NULL REFERENCES camps(id) ON DELETE CASCADE,
    person_name TEXT NOT NULL,
    age TEXT,
    gender TEXT,
    height TEXT,
    weight TEXT,
    blood_pressure TEXT,
    pulse TEXT,
    rbs TEXT,
    waist_circumference TEXT,
    ecg_notes TEXT,
    echo_notes TEXT,
    examination_details TEXT,
    referral_details TEXT,
    marital_status TEXT,
    parent_spouse_name TEXT,
    no_of_children TEXT,
    address TEXT,
    mobile_number TEXT,
    blood_group TEXT,
    dob TEXT,
    admission_id TEXT,
    moc_doc_id TEXT,
    school_college_name TEXT,
    staff_student_type TEXT,
    shift TEXT,
    year_of_study TEXT,
    course_dept TEXT,
    section TEXT,
    medical_history TEXT DEFAULT '{}',
    family_history TEXT DEFAULT '{}',
    vision_category TEXT,
    distant_vision_right TEXT,
    distant_vision_left TEXT,
    dental_status TEXT,
    dental_abnormality TEXT,
    dental_advice TEXT,
    consent_given INTEGER DEFAULT 1,
    consent_signature TEXT,
    status TEXT NOT NULL CHECK(status IN ('needs_review', 'reviewed', 'approved', 'failed')) DEFAULT 'needs_review',
    missing_fields TEXT NOT NULL DEFAULT '[]',
    uncertain_fields TEXT NOT NULL DEFAULT '[]',
    extraction_notes TEXT,
    structured_record TEXT,
    page1_preview TEXT,
    page2_preview TEXT,
    reviewer_notes TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    approved_by TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    scanned_by TEXT,
    community_id TEXT,
    edit_history TEXT DEFAULT '[]',
    version INTEGER DEFAULT 1,
    confidence_scores TEXT DEFAULT '{}',
    locked_by TEXT,
    locked_at TIMESTAMP WITH TIME ZONE,
    original_ai_extraction TEXT,
    quality_warning_bypassed TEXT DEFAULT '[]',
    quality_bypassed INTEGER DEFAULT 0,
    template_id TEXT,
    template_version TEXT,
    form_family TEXT DEFAULT 'adult',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_adult_records_camp ON adult_records(camp_id);
CREATE INDEX idx_adult_records_status ON adult_records(status);
CREATE INDEX idx_adult_records_community ON adult_records(community_id);

-- ============================================================================
-- 5. PAEDIATRIC RECORDS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS paediatric_records (
    id TEXT PRIMARY KEY,
    camp_id TEXT NOT NULL REFERENCES camps(id) ON DELETE CASCADE,
    person_name TEXT NOT NULL,
    age TEXT,
    gender TEXT,
    height TEXT,
    weight TEXT,
    bmi TEXT,
    bmi_centile REAL,
    bmi_classification TEXT,
    blood_pressure TEXT,
    bp_percentile REAL,
    bp_classification TEXT,
    pulse TEXT,
    spinal_caliper_atr REAL,
    head_circumference TEXT,
    muac TEXT,
    screening_type TEXT,
    school_name TEXT,
    class_and_section TEXT,
    admission_id TEXT,
    moc_doc_id TEXT,
    dob TEXT,
    blood_group TEXT,
    parent_guardian_name TEXT,
    emergency_contact_phone TEXT,
    address TEXT,
    birth_history TEXT,
    milestones TEXT,
    immunization_status TEXT,
    dietary_habits TEXT,
    known_allergies TEXT,
    vital_signs_status TEXT,
    gait_status TEXT,
    ears_hearing_status TEXT,
    otoscopy_findings TEXT,
    oral_cavity_throat TEXT,
    lymph_nodes TEXT,
    systemic_findings TEXT DEFAULT '{}',
    vision_distant_right TEXT,
    vision_distant_left TEXT,
    color_vision TEXT,
    squint_strabismus TEXT,
    dental_caries TEXT,
    malocclusion TEXT,
    oral_hygiene TEXT,
    examination_details TEXT,
    referral_specialist TEXT,
    referral_reason TEXT,
    referral_details TEXT,
    paediatric_alerts TEXT DEFAULT '[]',
    consent_given INTEGER DEFAULT 1,
    consent_signature TEXT,
    status TEXT NOT NULL CHECK(status IN ('needs_review', 'reviewed', 'approved', 'failed')) DEFAULT 'needs_review',
    missing_fields TEXT NOT NULL DEFAULT '[]',
    uncertain_fields TEXT NOT NULL DEFAULT '[]',
    extraction_notes TEXT,
    structured_record TEXT,
    page1_preview TEXT,
    page2_preview TEXT,
    reviewer_notes TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    approved_by TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    scanned_by TEXT,
    community_id TEXT,
    edit_history TEXT DEFAULT '[]',
    version INTEGER DEFAULT 1,
    confidence_scores TEXT DEFAULT '{}',
    locked_by TEXT,
    locked_at TIMESTAMP WITH TIME ZONE,
    original_ai_extraction TEXT,
    quality_warning_bypassed TEXT DEFAULT '[]',
    quality_bypassed INTEGER DEFAULT 0,
    template_id TEXT,
    template_version TEXT,
    form_family TEXT DEFAULT 'paediatric',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_paediatric_records_camp ON paediatric_records(camp_id);
CREATE INDEX idx_paediatric_records_status ON paediatric_records(status);
CREATE INDEX idx_paediatric_records_community ON paediatric_records(community_id);

-- ============================================================================
-- 6. UNIFIED RECORDS TABLE (Legacy Compatible)
-- ============================================================================
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    camp_id TEXT NOT NULL REFERENCES camps(id) ON DELETE CASCADE,
    person_name TEXT NOT NULL,
    age TEXT,
    gender TEXT,
    height TEXT,
    weight TEXT,
    blood_pressure TEXT,
    examination_details TEXT,
    referral_details TEXT,
    missing_fields TEXT NOT NULL DEFAULT '[]',
    uncertain_fields TEXT NOT NULL DEFAULT '[]',
    extraction_notes TEXT,
    structured_record TEXT,
    status TEXT NOT NULL CHECK(status IN ('needs_review', 'reviewed', 'approved', 'failed')),
    page1_preview TEXT,
    page2_preview TEXT,
    reviewer_notes TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    scanned_by TEXT,
    community_id TEXT,
    target_group TEXT NOT NULL DEFAULT 'adult',
    is_paediatric INTEGER DEFAULT 0,
    paediatric_alerts TEXT DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_records_camp ON records(camp_id);
CREATE INDEX idx_records_status ON records(status);
CREATE INDEX idx_records_community ON records(community_id);

-- ============================================================================
-- 7. INVITES TABLE (Single-use tokenized invites)
-- ============================================================================
CREATE TABLE IF NOT EXISTS invites (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    email TEXT,
    role TEXT DEFAULT 'doctor',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invites_code ON invites(code);
CREATE INDEX idx_invites_community ON invites(community_id);

-- ============================================================================
-- 8. APP SETTINGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 9. ORGANIZATIONS TABLE (Phase 3 - Quota & Metering)
-- ============================================================================
CREATE TABLE IF NOT EXISTS orgs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT DEFAULT 'outreach_10k',
    papers_included INTEGER NOT NULL DEFAULT 10000,
    addon_papers INTEGER NOT NULL DEFAULT 0,
    papers_used INTEGER NOT NULL DEFAULT 0,
    renews_on TIMESTAMP WITH TIME ZONE,
    rollover_papers INTEGER NOT NULL DEFAULT 0,
    ai_paused INTEGER NOT NULL DEFAULT 0,
    daily_cap INTEGER NOT NULL DEFAULT 2000
);

-- ============================================================================
-- 10. USAGE LEDGER TABLE (Phase 3)
-- ============================================================================
CREATE TABLE IF NOT EXISTS usage_ledger (
    id SERIAL PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    record_id TEXT,
    action TEXT NOT NULL,
    model TEXT,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    tokens_think INTEGER DEFAULT 0,
    seconds REAL DEFAULT 0.0,
    cost_rs REAL DEFAULT 0.0,
    provider TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_usage_ledger_org ON usage_ledger(org_id);
CREATE INDEX idx_usage_ledger_record ON usage_ledger(record_id);
CREATE INDEX idx_usage_ledger_created ON usage_ledger(created_at);

-- ============================================================================
-- 11. PAYMENTS TABLE (Phase 3)
-- ============================================================================
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    razorpay_payment_id TEXT UNIQUE,
    papers INTEGER NOT NULL,
    amount_rs REAL NOT NULL,
    gst_rs REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payments_org ON payments(org_id);

-- ============================================================================
-- 12. INVOICES TABLE (Phase 3)
-- ============================================================================
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    number TEXT UNIQUE NOT NULL,
    period TEXT NOT NULL,
    amount_rs REAL NOT NULL,
    gst_rs REAL NOT NULL,
    status TEXT NOT NULL,
    pdf_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_org ON invoices(org_id);

-- ============================================================================
-- 13. SCAN HASHES TABLE (Phase 3 - Deduplication)
-- ============================================================================
CREATE TABLE IF NOT EXISTS scan_hashes (
    hash TEXT NOT NULL,
    org_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, hash),
    FOREIGN KEY (org_id) REFERENCES orgs(id) ON DELETE CASCADE
);

-- ============================================================================
-- 14. AUTH LOCKOUTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS auth_lockouts (
    account_key TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 15. AUTH OTPs TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS auth_otps (
    recipient TEXT PRIMARY KEY,
    otp_code TEXT DEFAULT 'HASHED',
    otp_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_otps_expires ON auth_otps(expires_at);

-- ============================================================================
-- 16. RECORD AUDIT LOG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS record_audit_log (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_role TEXT NOT NULL,
    action TEXT NOT NULL,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_record ON record_audit_log(record_id);
CREATE INDEX idx_audit_org ON record_audit_log(org_id);
CREATE INDEX idx_audit_created ON record_audit_log(created_at);

-- ============================================================================
-- 17. FILES TABLE (Cloud Storage Metadata)
-- ============================================================================
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    record_id TEXT,
    file_type TEXT NOT NULL,
    original_filename TEXT,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_files_org ON files(org_id);
CREATE INDEX idx_files_record ON files(record_id);

-- ============================================================================
-- DONE - Schema successfully created
-- ============================================================================
-- Next Steps:
-- 1. Run this SQL in Supabase SQL Editor
-- 2. Update backend/.env with new Supabase URL and keys
-- 3. Test connection: python backend/app.py
-- 4. Verify all tables appear in Supabase UI
-- 5. Configure Row Level Security (RLS) policies if needed
