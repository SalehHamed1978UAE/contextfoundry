-- ============================================================
-- Migration 009: Magic Links
-- Platform Foundation - Passwordless Authentication
-- ============================================================

CREATE TABLE platform.magic_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  ip_address INET,
  user_agent TEXT
);

CREATE INDEX idx_magic_links_email ON platform.magic_links(email);
CREATE INDEX idx_magic_links_token ON platform.magic_links(token_hash) WHERE used_at IS NULL;
CREATE INDEX idx_magic_links_expires ON platform.magic_links(expires_at) WHERE used_at IS NULL;

COMMENT ON TABLE platform.magic_links IS 'Magic link tokens for passwordless authentication';
COMMENT ON COLUMN platform.magic_links.token_hash IS 'SHA-256 hash of token - never store plaintext';
COMMENT ON COLUMN platform.magic_links.expires_at IS 'Token valid for 15 minutes by default';
