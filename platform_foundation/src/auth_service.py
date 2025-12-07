"""
AuthService - Platform Foundation Authentication
Handles magic link flow, API key management, JWT tokens, and session management.
"""

import os
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import logging

try:
    import jwt
except ImportError:
    jwt = None

try:
    import bcrypt
except ImportError:
    bcrypt = None

logger = logging.getLogger(__name__)

@dataclass
class AuthUser:
    id: str
    email: str
    name: Optional[str]
    role: str
    tenant_id: Optional[str]
    status: str

@dataclass
class MagicLinkResult:
    success: bool
    token: Optional[str] = None
    link: Optional[str] = None
    error: Optional[str] = None
    expires_at: Optional[datetime] = None

@dataclass  
class AuthResult:
    success: bool
    user: Optional[AuthUser] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    error: Optional[str] = None
    expires_at: Optional[datetime] = None

@dataclass
class APIKeyResult:
    success: bool
    key_id: Optional[str] = None
    api_key: Optional[str] = None
    key_prefix: Optional[str] = None
    error: Optional[str] = None


class AuthService:
    """Authentication service for Platform Foundation."""
    
    MAGIC_LINK_EXPIRY_MINUTES = 15
    JWT_EXPIRY_HOURS = 24
    JWT_REFRESH_EXPIRY_DAYS = 30
    API_KEY_PREFIX_LENGTH = 8
    
    def __init__(self, database_url: Optional[str] = None, jwt_secret: Optional[str] = None, base_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        self.jwt_secret = jwt_secret or os.environ.get('SESSION_SECRET', 'dev-secret-change-in-production')
        self.base_url = base_url or os.environ.get('REPLIT_DEV_DOMAIN', 'http://localhost:5000')
        if not self.base_url.startswith('http'):
            self.base_url = f'https://{self.base_url}'
        self._engine = None
        self._session_factory = None
    
    def _get_session(self):
        """Get a database session."""
        if self._engine is None:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            self._engine = create_engine(self.database_url)
            self._session_factory = sessionmaker(bind=self._engine)
        return self._session_factory()
    
    def _hash_token(self, token: str) -> str:
        """Hash a token using SHA-256."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _hash_api_key(self, key: str) -> str:
        """Hash an API key using bcrypt."""
        if bcrypt:
            return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()
        return self._hash_token(key)
    
    def _verify_api_key(self, key: str, key_hash: str) -> bool:
        """Verify an API key against its hash."""
        if bcrypt:
            try:
                return bcrypt.checkpw(key.encode(), key_hash.encode())
            except Exception:
                return False
        return self._hash_token(key) == key_hash
    
    def create_magic_link(self, email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> MagicLinkResult:
        """
        Generate a magic link token for passwordless authentication.
        Returns the token and full URL for email sending.
        """
        from sqlalchemy import text
        
        email = email.lower().strip()
        if not email or '@' not in email:
            return MagicLinkResult(success=False, error="Invalid email address")
        
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)
        expires_at = datetime.utcnow() + timedelta(minutes=self.MAGIC_LINK_EXPIRY_MINUTES)
        
        session = self._get_session()
        try:
            session.execute(text("""
                INSERT INTO platform.magic_links (email, token_hash, expires_at, ip_address, user_agent)
                VALUES (:email, :token_hash, :expires_at, :ip_address, :user_agent)
            """), {
                'email': email,
                'token_hash': token_hash,
                'expires_at': expires_at,
                'ip_address': ip_address,
                'user_agent': user_agent
            })
            session.commit()
            
            link = f"{self.base_url}/auth/verify?token={token}"
            
            logger.info(f"[AuthService] Magic link created for {email}, expires at {expires_at}")
            
            return MagicLinkResult(
                success=True,
                token=token,
                link=link,
                expires_at=expires_at
            )
        except Exception as e:
            session.rollback()
            logger.error(f"[AuthService] Failed to create magic link: {e}")
            return MagicLinkResult(success=False, error=str(e))
        finally:
            session.close()
    
    def verify_magic_link(self, token: str) -> AuthResult:
        """
        Verify a magic link token and authenticate the user.
        Creates user if not exists, returns JWT tokens.
        """
        from sqlalchemy import text
        
        if not token:
            return AuthResult(success=False, error="Token required")
        
        token_hash = self._hash_token(token)
        session = self._get_session()
        
        try:
            result = session.execute(text("""
                SELECT id, email, expires_at, used_at
                FROM platform.magic_links
                WHERE token_hash = :token_hash
            """), {'token_hash': token_hash}).fetchone()
            
            if not result:
                return AuthResult(success=False, error="Invalid or expired token")
            
            link_id, email, expires_at, used_at = result
            
            if used_at:
                return AuthResult(success=False, error="Token already used")
            
            from datetime import timezone
            now = datetime.now(timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                return AuthResult(success=False, error="Token expired")
            
            session.execute(text("""
                UPDATE platform.magic_links 
                SET used_at = NOW() 
                WHERE id = :id
            """), {'id': link_id})
            
            user_result = session.execute(text("""
                SELECT id, email, name, role, tenant_id, status
                FROM platform.users
                WHERE email = :email
            """), {'email': email}).fetchone()
            
            if user_result:
                user = AuthUser(
                    id=str(user_result[0]),
                    email=user_result[1],
                    name=user_result[2],
                    role=user_result[3],
                    tenant_id=str(user_result[4]) if user_result[4] else None,
                    status=user_result[5]
                )
                session.execute(text("""
                    UPDATE platform.users SET last_login = NOW() WHERE id = :id
                """), {'id': user.id})
            else:
                new_user = session.execute(text("""
                    INSERT INTO platform.users (email, role, status)
                    VALUES (:email, 'user', 'active')
                    RETURNING id, email, name, role, tenant_id, status
                """), {'email': email}).fetchone()
                
                user = AuthUser(
                    id=str(new_user[0]),
                    email=new_user[1],
                    name=new_user[2],
                    role=new_user[3],
                    tenant_id=str(new_user[4]) if new_user[4] else None,
                    status=new_user[5]
                )
            
            session.commit()
            
            access_token, access_expires = self._generate_jwt(user)
            refresh_token, _ = self._generate_refresh_token(user)
            
            logger.info(f"[AuthService] User {email} authenticated via magic link")
            
            return AuthResult(
                success=True,
                user=user,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=access_expires
            )
            
        except Exception as e:
            session.rollback()
            logger.error(f"[AuthService] Magic link verification failed: {e}")
            return AuthResult(success=False, error=str(e))
        finally:
            session.close()
    
    def _generate_jwt(self, user: AuthUser) -> Tuple[str, datetime]:
        """Generate a JWT access token for a user."""
        if not jwt:
            token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=self.JWT_EXPIRY_HOURS)
            return token, expires
        
        expires = datetime.utcnow() + timedelta(hours=self.JWT_EXPIRY_HOURS)
        payload = {
            'sub': user.id,
            'email': user.email,
            'role': user.role,
            'tenant_id': user.tenant_id,
            'iat': datetime.utcnow(),
            'exp': expires,
            'type': 'access'
        }
        token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        return token, expires
    
    def _generate_refresh_token(self, user: AuthUser) -> Tuple[str, datetime]:
        """Generate a refresh token for a user."""
        if not jwt:
            token = secrets.token_urlsafe(48)
            expires = datetime.utcnow() + timedelta(days=self.JWT_REFRESH_EXPIRY_DAYS)
            return token, expires
        
        expires = datetime.utcnow() + timedelta(days=self.JWT_REFRESH_EXPIRY_DAYS)
        payload = {
            'sub': user.id,
            'iat': datetime.utcnow(),
            'exp': expires,
            'type': 'refresh'
        }
        token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        return token, expires
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate a JWT token and return the payload."""
        if not token:
            return None
        
        if not jwt:
            return None
        
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            if payload.get('type') != 'access':
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("[AuthService] Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"[AuthService] Invalid token: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> AuthResult:
        """Refresh an access token using a refresh token."""
        if not jwt:
            return AuthResult(success=False, error="JWT not available")
        
        try:
            payload = jwt.decode(refresh_token, self.jwt_secret, algorithms=['HS256'])
            if payload.get('type') != 'refresh':
                return AuthResult(success=False, error="Invalid refresh token")
            
            user_id = payload.get('sub')
            user = self._get_user_by_id(user_id)
            if not user:
                return AuthResult(success=False, error="User not found")
            
            access_token, access_expires = self._generate_jwt(user)
            
            return AuthResult(
                success=True,
                user=user,
                access_token=access_token,
                expires_at=access_expires
            )
            
        except jwt.ExpiredSignatureError:
            return AuthResult(success=False, error="Refresh token expired")
        except jwt.InvalidTokenError:
            return AuthResult(success=False, error="Invalid refresh token")
    
    def _get_user_by_id(self, user_id: str) -> Optional[AuthUser]:
        """Get a user by ID."""
        from sqlalchemy import text
        
        session = self._get_session()
        try:
            result = session.execute(text("""
                SELECT id, email, name, role, tenant_id, status
                FROM platform.users
                WHERE id = :id
            """), {'id': user_id}).fetchone()
            
            if not result:
                return None
            
            return AuthUser(
                id=str(result[0]),
                email=result[1],
                name=result[2],
                role=result[3],
                tenant_id=str(result[4]) if result[4] else None,
                status=result[5]
            )
        finally:
            session.close()
    
    def create_api_key(self, tenant_id: str, name: str, scopes: List[str] = None, 
                       created_by: Optional[str] = None, rate_limit: int = 60,
                       expires_in_days: Optional[int] = None) -> APIKeyResult:
        """
        Create a new API key for a tenant.
        Returns the full key ONCE - it cannot be retrieved later.
        """
        from sqlalchemy import text
        
        if not tenant_id or not name:
            return APIKeyResult(success=False, error="Tenant ID and name required")
        
        key_suffix = secrets.token_urlsafe(32)
        key_prefix = f"cf_live_{secrets.token_hex(4)}"
        full_key = f"{key_prefix}_{key_suffix}"
        key_hash = self._hash_api_key(full_key)
        
        scopes = scopes or ['read']
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        session = self._get_session()
        try:
            result = session.execute(text("""
                INSERT INTO platform.api_keys (tenant_id, name, key_hash, key_prefix, scopes, rate_limit_per_min, expires_at, created_by)
                VALUES (:tenant_id, :name, :key_hash, :key_prefix, :scopes, :rate_limit, :expires_at, :created_by)
                RETURNING id
            """), {
                'tenant_id': tenant_id,
                'name': name,
                'key_hash': key_hash,
                'key_prefix': key_prefix,
                'scopes': scopes,
                'rate_limit': rate_limit,
                'expires_at': expires_at,
                'created_by': created_by
            }).fetchone()
            
            session.commit()
            
            logger.info(f"[AuthService] API key created: {key_prefix} for tenant {tenant_id}")
            
            return APIKeyResult(
                success=True,
                key_id=str(result[0]),
                api_key=full_key,
                key_prefix=key_prefix
            )
            
        except Exception as e:
            session.rollback()
            logger.error(f"[AuthService] Failed to create API key: {e}")
            return APIKeyResult(success=False, error=str(e))
        finally:
            session.close()
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return its metadata.
        Returns None if invalid, revoked, or expired.
        """
        from sqlalchemy import text
        
        if not api_key or '_' not in api_key:
            return None
        
        parts = api_key.split('_')
        if len(parts) < 3:
            return None
        key_prefix = f"{parts[0]}_{parts[1]}_{parts[2]}"
        
        session = self._get_session()
        try:
            result = session.execute(text("""
                SELECT id, tenant_id, name, key_hash, scopes, rate_limit_per_min, expires_at, revoked_at
                FROM platform.api_keys
                WHERE key_prefix = :key_prefix
            """), {'key_prefix': key_prefix}).fetchone()
            
            if not result:
                return None
            
            key_id, tenant_id, name, key_hash, scopes, rate_limit, expires_at, revoked_at = result
            
            if revoked_at:
                logger.debug(f"[AuthService] API key {key_prefix} is revoked")
                return None
            
            if expires_at and datetime.utcnow() > expires_at:
                logger.debug(f"[AuthService] API key {key_prefix} is expired")
                return None
            
            if not self._verify_api_key(api_key, key_hash):
                logger.debug(f"[AuthService] API key {key_prefix} hash mismatch")
                return None
            
            session.execute(text("""
                UPDATE platform.api_keys SET last_used_at = NOW() WHERE id = :id
            """), {'id': key_id})
            session.commit()
            
            return {
                'key_id': str(key_id),
                'tenant_id': str(tenant_id),
                'name': name,
                'scopes': scopes,
                'rate_limit_per_min': rate_limit
            }
            
        except Exception as e:
            logger.error(f"[AuthService] API key validation failed: {e}")
            return None
        finally:
            session.close()
    
    def list_api_keys(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all API keys for a tenant (without the actual keys)."""
        from sqlalchemy import text
        
        session = self._get_session()
        try:
            results = session.execute(text("""
                SELECT id, name, key_prefix, scopes, rate_limit_per_min, expires_at, last_used_at, created_at, revoked_at
                FROM platform.api_keys
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC
            """), {'tenant_id': tenant_id}).fetchall()
            
            return [
                {
                    'id': str(r[0]),
                    'name': r[1],
                    'key_prefix': r[2],
                    'scopes': r[3],
                    'rate_limit_per_min': r[4],
                    'expires_at': r[5].isoformat() if r[5] else None,
                    'last_used_at': r[6].isoformat() if r[6] else None,
                    'created_at': r[7].isoformat() if r[7] else None,
                    'revoked': r[8] is not None
                }
                for r in results
            ]
        finally:
            session.close()
    
    def revoke_api_key(self, key_id: str, tenant_id: str) -> bool:
        """Revoke an API key."""
        from sqlalchemy import text
        
        session = self._get_session()
        try:
            result = session.execute(text("""
                UPDATE platform.api_keys 
                SET revoked_at = NOW() 
                WHERE id = :id AND tenant_id = :tenant_id AND revoked_at IS NULL
                RETURNING id
            """), {'id': key_id, 'tenant_id': tenant_id}).fetchone()
            
            session.commit()
            
            if result:
                logger.info(f"[AuthService] API key {key_id} revoked")
                return True
            return False
            
        except Exception as e:
            session.rollback()
            logger.error(f"[AuthService] Failed to revoke API key: {e}")
            return False
        finally:
            session.close()
    
    def set_tenant_context(self, session, tenant_id: str, role: str = None):
        """
        Set the tenant context for RLS using PostgreSQL session variables.
        Call this at the start of every authenticated request.
        """
        from sqlalchemy import text
        
        session.execute(text("SELECT platform.set_current_tenant(:tenant_id)"), {'tenant_id': tenant_id})
        if role:
            session.execute(text("SELECT platform.set_current_user_role(:role)"), {'role': role})
    
    def clear_tenant_context(self, session):
        """Clear the tenant context at the end of a request."""
        from sqlalchemy import text
        
        try:
            session.execute(text("RESET app.current_tenant_id"))
            session.execute(text("RESET app.current_user_role"))
        except Exception:
            pass
