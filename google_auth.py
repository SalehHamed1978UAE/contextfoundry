# Google OAuth authentication with auto-provisioning
# Based on flask_google_oauth blueprint

import json
import os
import secrets
import re
from datetime import datetime

import requests
from flask import Blueprint, redirect, request, url_for, session, flash
from oauthlib.oauth2 import WebApplicationClient

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

PRODUCTION_DOMAIN = "https://context-foundry.replit.app"

def get_redirect_url():
    """Get the correct redirect URL for dev or production."""
    # Check if running in production (no dev domain means production deployment)
    if not os.environ.get("REPLIT_DEV_DOMAIN"):
        return f'{PRODUCTION_DOMAIN}/google_login/callback'
    # Development uses REPLIT_DEV_DOMAIN
    return f'https://{os.environ.get("REPLIT_DEV_DOMAIN")}/google_login/callback'

# For logging at startup
_startup_redirect = get_redirect_url()
if GOOGLE_CLIENT_ID:
    print(f"""Google OAuth configured.
Redirect URI: {_startup_redirect}
""")

client = WebApplicationClient(GOOGLE_CLIENT_ID) if GOOGLE_CLIENT_ID else None

google_auth = Blueprint("google_auth", __name__)


def generate_unique_slug(email: str, name: str = None) -> str:
    """
    Generate a unique slug for a tenant.
    Handles collisions by appending random suffix.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    base = name.lower() if name else email.split('@')[0].lower()
    base = re.sub(r'[^a-z0-9]+', '-', base)
    base = base.strip('-')[:30]
    
    if not base:
        base = "space"
    
    slug = base
    suffix_length = 4
    
    database_url = os.environ.get("DATABASE_URL")
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            for attempt in range(10):
                cur.execute("SELECT 1 FROM platform.tenants WHERE slug = %s", (slug,))
                if not cur.fetchone():
                    return slug
                suffix = secrets.token_hex(suffix_length)
                slug = f"{base}-{suffix}"
    
    return f"{base}-{secrets.token_hex(8)}"


def auto_provision_user(google_email: str, google_name: str):
    """
    Auto-provision a new user with their own space (tenant).
    Returns (user_id, tenant_id) tuple.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import uuid
    
    database_url = os.environ.get("DATABASE_URL")
    
    with psycopg2.connect(database_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, tenant_id FROM platform.users WHERE email = %s", (google_email,))
            existing = cur.fetchone()
            
            if existing:
                return str(existing['id']), str(existing['tenant_id'])
            
            tenant_id = str(uuid.uuid4())
            tenant_name = f"{google_name}'s Space"
            tenant_slug = generate_unique_slug(google_email, google_name)
            
            cur.execute("""
                INSERT INTO platform.tenants (id, name, slug, type, status, created_at, updated_at)
                VALUES (%s, %s, %s, 'personal_sandbox', 'active', NOW(), NOW())
            """, (tenant_id, tenant_name, tenant_slug))
            
            cur.execute("""
                INSERT INTO platform.tenant_quotas (
                    tenant_id, 
                    extraction_tokens_daily, 
                    extraction_tokens_monthly,
                    query_tokens_daily, 
                    query_tokens_monthly,
                    document_limit, 
                    storage_gb_limit
                ) VALUES (%s, 50000, 500000, 25000, 250000, 100, 1)
            """, (tenant_id,))
            
            user_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO platform.users (id, tenant_id, email, name, role, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'tenant_admin', 'active', NOW(), NOW())
            """, (user_id, tenant_id, google_email, google_name))
            
            conn.commit()
            
            print(f"[Auth] Auto-provisioned user {google_email} with space '{tenant_name}' (slug: {tenant_slug})")
            
            return user_id, tenant_id


@google_auth.route("/google_login")
def login():
    """Initiate Google OAuth flow."""
    if not client:
        return "Google OAuth not configured. Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.", 500
    
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=get_redirect_url(),
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@google_auth.route("/google_login/callback")
def callback():
    """Handle Google OAuth callback with auto-provisioning."""
    if not client:
        return "Google OAuth not configured.", 500
    
    code = request.args.get("code")
    if not code:
        return "No authorization code received.", 400
    
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url.replace("http://", "https://"),
        redirect_url=get_redirect_url(),
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    userinfo = userinfo_response.json()
    if not userinfo.get("email_verified"):
        return "User email not available or not verified by Google.", 400

    users_email = userinfo["email"]
    users_name = userinfo.get("name") or userinfo.get("given_name") or users_email.split('@')[0]

    user_id, tenant_id = auto_provision_user(users_email, users_name)

    session['user_id'] = user_id
    session['tenant_id'] = tenant_id
    session['user_email'] = users_email
    session['user_name'] = users_name
    session.permanent = True

    return redirect(url_for("user_dashboard"))


@google_auth.route("/logout")
def logout():
    """Clear session and redirect to landing."""
    session.clear()
    return redirect(url_for("landing"))
