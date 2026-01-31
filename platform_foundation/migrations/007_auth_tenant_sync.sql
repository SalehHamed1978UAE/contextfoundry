-- ============================================================
-- Migration 007: Auth Tenant Sync
-- Platform Foundation - Sync tenant_id/role to JWT for RLS
-- ============================================================
-- 
-- WHY THIS IS NEEDED:
-- RLS policies check (auth.jwt() -> 'app_metadata' ->> 'tenant_id') 
-- but Supabase doesn't automatically include tenant_id in the JWT.
-- We must copy it from platform.users into auth.users.raw_app_meta_data.
--
-- NOTE: This migration is for Supabase-hosted deployments.
-- For Replit PostgreSQL, RLS policies will use a different pattern
-- based on session variables or passed-in tenant_id.
-- ============================================================

-- Session variable setter for non-Supabase deployments
CREATE OR REPLACE FUNCTION platform.set_current_tenant(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
  PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, false);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION platform.get_current_tenant()
RETURNS UUID AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION platform.set_current_user_role(p_role TEXT)
RETURNS VOID AS $$
BEGIN
  PERFORM set_config('app.current_user_role', p_role, false);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION platform.get_current_user_role()
RETURNS TEXT AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_user_role', true), '');
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION platform.set_current_tenant IS 'Set tenant context for RLS - call at start of each request';
COMMENT ON FUNCTION platform.get_current_tenant IS 'Get current tenant for RLS policies';
COMMENT ON FUNCTION platform.set_current_user_role IS 'Set user role context for RLS';
COMMENT ON FUNCTION platform.get_current_user_role IS 'Get current user role for RLS policies';

-- ============================================================
-- RLS Helper for Supabase JWT extraction
-- Falls back to session variable for non-Supabase environments
-- ============================================================

CREATE OR REPLACE FUNCTION platform.current_tenant_id()
RETURNS UUID AS $$
DECLARE
  v_tenant_id UUID;
BEGIN
  -- Try Supabase JWT first (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  BEGIN
    SELECT (current_setting('request.jwt.claims', true)::jsonb -> 'app_metadata' ->> 'tenant_id')::UUID
    INTO v_tenant_id;
  EXCEPTION
    WHEN OTHERS THEN
      v_tenant_id := NULL;
  END;
  
  -- Fall back to session variable
  IF v_tenant_id IS NULL THEN
    v_tenant_id := platform.get_current_tenant();
  END IF;
  
  RETURN v_tenant_id;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION platform.current_user_role()
RETURNS TEXT AS $$
DECLARE
  v_role TEXT;
BEGIN
  -- Try Supabase JWT first
  BEGIN
    SELECT current_setting('request.jwt.claims', true)::jsonb -> 'app_metadata' ->> 'role'
    INTO v_role;
  EXCEPTION
    WHEN OTHERS THEN
      v_role := NULL;
  END;
  
  -- Fall back to session variable
  IF v_role IS NULL THEN
    v_role := platform.get_current_user_role();
  END IF;
  
  RETURN v_role;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION platform.current_tenant_id IS 'Get tenant_id from JWT or session - use in RLS policies';
COMMENT ON FUNCTION platform.current_user_role IS 'Get user role from JWT or session - use in RLS policies';
