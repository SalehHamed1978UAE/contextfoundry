"""
MCP Server - Model Context Protocol for AI Agents

Provides query surface for AI agents (Claude, GPT) to interact with Context Foundry.
Handles API key auth, quota enforcement, and usage logging.
"""

import logging
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from dataclasses import dataclass, asdict
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class Scope(Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


TOOL_SCOPES = {
    "query_context": [Scope.READ],
    "verify_statement": [Scope.READ],
    "get_document_status": [Scope.READ],
    "list_entity_types": [Scope.READ],
    "ingest_document": [Scope.WRITE],
}

SCOPE_HIERARCHY = {
    Scope.ADMIN: [Scope.ADMIN, Scope.WRITE, Scope.READ],
    Scope.WRITE: [Scope.WRITE, Scope.READ],
    Scope.READ: [Scope.READ],
}


@dataclass
class MCPError:
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class MCPResponse:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None
    tokens_consumed: int = 0


@dataclass
class AuthContext:
    tenant_id: str
    api_key_id: str
    scopes: List[str]
    rate_limit: int


class MCPServer:
    """
    MCP Server for AI agent interactions.
    
    Handles:
    - API key authentication and scope validation
    - Quota enforcement (before calling Brain)
    - Query routing to Brain /internal/v1/query
    - Usage logging for every call
    """
    
    def __init__(self, database_url: Optional[str] = None, brain_url: str = "http://localhost:5000"):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        self.brain_url = brain_url
        
    def _get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def authenticate(self, api_key: str) -> Tuple[Optional[AuthContext], Optional[MCPError]]:
        """
        Validate API key and extract auth context.
        
        Returns:
            (AuthContext, None) on success
            (None, MCPError) on failure
        """
        if not api_key:
            return None, MCPError(
                code="MISSING_API_KEY",
                message="API key required"
            )
        
        if not (api_key.startswith("cf_live_") or api_key.startswith("cf_test_")):
            return None, MCPError(
                code="INVALID_API_KEY_FORMAT",
                message="API key must start with cf_live_ or cf_test_"
            )
        
        from platform_foundation.src.auth_service import AuthService
        auth_service = AuthService(self.database_url)
        
        key_data = auth_service.validate_api_key(api_key)
        if not key_data:
            return None, MCPError(
                code="INVALID_API_KEY",
                message="API key is invalid or expired"
            )
        
        return AuthContext(
            tenant_id=key_data['tenant_id'],
            api_key_id=key_data.get('key_id', ''),
            scopes=key_data.get('scopes', ['read']),
            rate_limit=key_data.get('rate_limit', 60)
        ), None
    
    def check_scope(self, auth: AuthContext, tool_name: str) -> Optional[MCPError]:
        """
        Check if the API key has permission to call the given tool.
        
        Returns:
            None if authorized
            MCPError if insufficient scope
        """
        required_scopes = TOOL_SCOPES.get(tool_name, [Scope.READ])
        
        user_scopes = []
        for scope_str in auth.scopes:
            try:
                scope = Scope(scope_str)
                user_scopes.extend(SCOPE_HIERARCHY.get(scope, [scope]))
            except ValueError:
                continue
        
        for required in required_scopes:
            if required in user_scopes:
                return None
        
        return MCPError(
            code="INSUFFICIENT_SCOPE",
            message=f"Tool '{tool_name}' requires scope: {required_scopes[0].value}",
            details={"required": required_scopes[0].value, "available": auth.scopes}
        )
    
    def check_quota(self, tenant_id: str, estimated_tokens: int = 1000) -> Tuple[bool, Dict[str, Any], Optional[MCPError]]:
        """
        Check if tenant has query quota remaining.
        
        Returns:
            (has_quota, quota_info, error)
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT query_tokens_daily, query_tokens_monthly
                    FROM platform.tenant_quotas
                    WHERE tenant_id = %s
                """, (tenant_id,))
                
                quota = cur.fetchone()
                if not quota:
                    quota = {'query_tokens_daily': 50000, 'query_tokens_monthly': 1000000}
                
                today = datetime.utcnow().date()
                first_of_month = today.replace(day=1)
                
                cur.execute("""
                    SELECT COALESCE(SUM(tokens_consumed), 0) as daily_used
                    FROM platform.usage_events
                    WHERE tenant_id = %s 
                    AND event_type = 'query'
                    AND created_at >= %s
                """, (tenant_id, today))
                daily_used = cur.fetchone()['daily_used']
                
                cur.execute("""
                    SELECT COALESCE(SUM(tokens_consumed), 0) as monthly_used
                    FROM platform.usage_events
                    WHERE tenant_id = %s 
                    AND event_type = 'query'
                    AND created_at >= %s
                """, (tenant_id, first_of_month))
                monthly_used = cur.fetchone()['monthly_used']
                
                quota_info = {
                    'daily_limit': quota['query_tokens_daily'],
                    'daily_used': daily_used,
                    'daily_remaining': quota['query_tokens_daily'] - daily_used,
                    'monthly_limit': quota['query_tokens_monthly'],
                    'monthly_used': monthly_used,
                    'monthly_remaining': quota['query_tokens_monthly'] - monthly_used
                }
                
                if daily_used + estimated_tokens > quota['query_tokens_daily']:
                    return False, quota_info, MCPError(
                        code="DAILY_QUOTA_EXCEEDED",
                        message="Daily query token quota exceeded",
                        details=quota_info
                    )
                
                if monthly_used + estimated_tokens > quota['query_tokens_monthly']:
                    return False, quota_info, MCPError(
                        code="MONTHLY_QUOTA_EXCEEDED",
                        message="Monthly query token quota exceeded",
                        details=quota_info
                    )
                
                return True, quota_info, None
    
    def log_usage(
        self,
        tenant_id: str,
        api_key_id: str,
        event_type: str,
        tokens_consumed: int,
        tool_name: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a usage event."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.usage_events
                    (tenant_id, api_key_id, event_type, tokens_consumed, request_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    tenant_id,
                    api_key_id if api_key_id else None,
                    event_type,
                    tokens_consumed,
                    request_id,
                    psycopg2.extras.Json({
                        'tool': tool_name,
                        **(metadata or {})
                    })
                ))
                conn.commit()
    
    def query_context(
        self,
        auth: AuthContext,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
        include_relationships: bool = True
    ) -> MCPResponse:
        """
        Query the knowledge graph for relevant context.
        
        Args:
            auth: Authentication context
            query: Natural language query
            entity_types: Optional filter for entity types
            limit: Maximum results to return
            include_relationships: Whether to include relationships
            
        Returns:
            MCPResponse with entities and relationships
        """
        scope_error = self.check_scope(auth, "query_context")
        if scope_error:
            return MCPResponse(success=False, error=scope_error)
        
        has_quota, quota_info, quota_error = self.check_quota(auth.tenant_id)
        if not has_quota:
            return MCPResponse(success=False, error=quota_error)
        
        try:
            import uuid
            query_id = str(uuid.uuid4())
            query_request = {
                "query_id": query_id,
                "tenant_id": auth.tenant_id,
                "query_type": "semantic_search",
                "query_text": query,
                "entity_type": entity_types[0] if entity_types else None,
                "max_results": limit,
                "include_provenance": include_relationships,
            }
            
            response = requests.post(
                f"{self.brain_url}/internal/v1/query",
                json=query_request,
                timeout=30
            )
            
            if response.status_code != 200:
                return MCPResponse(
                    success=False,
                    error=MCPError(
                        code="BRAIN_ERROR",
                        message=f"Brain query failed: {response.status_code}",
                        details={"status": response.status_code}
                    )
                )
            
            result = response.json()
            tokens_consumed = result.get('tokens_consumed', {}).get('total_tokens', 0)
            
            self.log_usage(
                tenant_id=auth.tenant_id,
                api_key_id=auth.api_key_id,
                event_type="query",
                tokens_consumed=tokens_consumed,
                tool_name="query_context",
                request_id=query_id,
                metadata={"query_length": len(query), "results": len(result.get('entities', []))}
            )
            
            return MCPResponse(
                success=True,
                data={
                    "entities": result.get('entities', []),
                    "relationships": result.get('relationships', []),
                    "query_id": query_id
                },
                tokens_consumed=tokens_consumed
            )
            
        except requests.exceptions.Timeout:
            return MCPResponse(
                success=False,
                error=MCPError(code="TIMEOUT", message="Query timed out")
            )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return MCPResponse(
                success=False,
                error=MCPError(code="INTERNAL_ERROR", message=str(e))
            )
    
    def verify_statement(
        self,
        auth: AuthContext,
        statement: str,
        confidence_threshold: float = 0.7
    ) -> MCPResponse:
        """
        Verify a statement against the knowledge base.
        
        Args:
            auth: Authentication context
            statement: Statement to verify
            confidence_threshold: Minimum confidence for verification
            
        Returns:
            MCPResponse with verification result
        """
        scope_error = self.check_scope(auth, "verify_statement")
        if scope_error:
            return MCPResponse(success=False, error=scope_error)
        
        has_quota, quota_info, quota_error = self.check_quota(auth.tenant_id)
        if not has_quota:
            return MCPResponse(success=False, error=quota_error)
        
        try:
            import uuid
            query_id = str(uuid.uuid4())
            query_request = {
                "query_id": query_id,
                "tenant_id": auth.tenant_id,
                "query_type": "verify_statement",
                "statement": statement,
                "max_results": 5,
                "include_provenance": True,
                "include_confidence": True
            }
            
            response = requests.post(
                f"{self.brain_url}/internal/v1/query",
                json=query_request,
                timeout=30
            )
            
            if response.status_code != 200:
                return MCPResponse(
                    success=False,
                    error=MCPError(code="BRAIN_ERROR", message="Verification failed")
                )
            
            result = response.json()
            tokens_consumed = result.get('tokens_consumed', {}).get('total_tokens', 0)
            
            entities = result.get('entities', [])
            supporting_evidence = []
            max_confidence = 0.0
            
            for entity in entities:
                conf = entity.get('confidence', 0)
                if conf > max_confidence:
                    max_confidence = conf
                if conf >= confidence_threshold:
                    supporting_evidence.append({
                        "entity": entity.get('name'),
                        "type": entity.get('entity_type'),
                        "confidence": conf
                    })
            
            verified = max_confidence >= confidence_threshold and len(supporting_evidence) > 0
            
            self.log_usage(
                tenant_id=auth.tenant_id,
                api_key_id=auth.api_key_id,
                event_type="query",
                tokens_consumed=tokens_consumed,
                tool_name="verify_statement",
                request_id=query_id,
                metadata={"verified": verified, "confidence": max_confidence}
            )
            
            return MCPResponse(
                success=True,
                data={
                    "verified": verified,
                    "confidence": max_confidence,
                    "supporting_evidence": supporting_evidence,
                    "reasoning": result.get('reasoning'),
                    "query_id": query_request['query_id']
                },
                tokens_consumed=tokens_consumed
            )
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return MCPResponse(
                success=False,
                error=MCPError(code="INTERNAL_ERROR", message=str(e))
            )
    
    def ingest_document(
        self,
        auth: AuthContext,
        filename: str,
        content: bytes,
        mime_type: str = "text/plain",
        priority: str = "normal"
    ) -> MCPResponse:
        """
        Ingest a document for extraction.
        
        Args:
            auth: Authentication context
            filename: Document filename
            content: Document content as bytes
            mime_type: MIME type
            priority: Extraction priority
            
        Returns:
            MCPResponse with document ID and extraction request ID
        """
        scope_error = self.check_scope(auth, "ingest_document")
        if scope_error:
            return MCPResponse(success=False, error=scope_error)
        
        try:
            from platform_foundation.src.document_service import DocumentService
            doc_service = DocumentService(self.database_url)
            
            document = doc_service.upload_document(
                tenant_id=UUID(auth.tenant_id),
                filename=filename,
                mime_type=mime_type,
                file_content=content,
                auto_extract=True,
                priority=priority
            )
            
            return MCPResponse(
                success=True,
                data={
                    "document_id": str(document['id']),
                    "extraction_request_id": document.get('extraction_request_id'),
                    "status": document['status'],
                    "message": "Document queued for extraction"
                }
            )
            
        except ValueError as e:
            return MCPResponse(
                success=False,
                error=MCPError(code="VALIDATION_ERROR", message=str(e))
            )
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            return MCPResponse(
                success=False,
                error=MCPError(code="INTERNAL_ERROR", message=str(e))
            )
    
    def get_document_status(
        self,
        auth: AuthContext,
        document_id: str
    ) -> MCPResponse:
        """
        Get document extraction status.
        
        Args:
            auth: Authentication context
            document_id: Document UUID
            
        Returns:
            MCPResponse with document status
        """
        scope_error = self.check_scope(auth, "get_document_status")
        if scope_error:
            return MCPResponse(success=False, error=scope_error)
        
        try:
            from platform_foundation.src.document_service import DocumentService
            doc_service = DocumentService(self.database_url)
            
            document = doc_service.get_document(UUID(document_id), UUID(auth.tenant_id))
            
            if not document:
                return MCPResponse(
                    success=False,
                    error=MCPError(code="NOT_FOUND", message="Document not found")
                )
            
            return MCPResponse(
                success=True,
                data={
                    "document_id": str(document['id']),
                    "name": document['name'],
                    "status": document['status'],
                    "mime_type": document['mime_type'],
                    "size_bytes": document['size_bytes'],
                    "created_at": document['created_at'].isoformat() if document.get('created_at') else None,
                    "updated_at": document['updated_at'].isoformat() if document.get('updated_at') else None
                }
            )
            
        except ValueError:
            return MCPResponse(
                success=False,
                error=MCPError(code="INVALID_ID", message="Invalid document ID format")
            )
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return MCPResponse(
                success=False,
                error=MCPError(code="INTERNAL_ERROR", message=str(e))
            )
    
    def list_entity_types(self, auth: AuthContext) -> MCPResponse:
        """
        List available entity types from ontology.
        
        Args:
            auth: Authentication context
            
        Returns:
            MCPResponse with list of entity types
        """
        scope_error = self.check_scope(auth, "list_entity_types")
        if scope_error:
            return MCPResponse(success=False, error=scope_error)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT name, description, lifecycle_state
                        FROM ontology.types
                        WHERE lifecycle_state = 'ACTIVE'
                        ORDER BY name
                    """)
                    
                    types = [dict(row) for row in cur.fetchall()]
                    
                    return MCPResponse(
                        success=True,
                        data={
                            "entity_types": types,
                            "count": len(types)
                        }
                    )
                    
        except Exception as e:
            logger.error(f"List types failed: {e}")
            return MCPResponse(
                success=False,
                error=MCPError(code="INTERNAL_ERROR", message=str(e))
            )
    
    def get_schema(self, auth: AuthContext, domain: Optional[str] = None) -> MCPResponse:
        """
        Get ontology schema for the given domain.
        
        Args:
            auth: Authentication context
            domain: Optional domain filter
            
        Returns:
            MCPResponse with schema definition
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT t.name, t.description, t.parent_type, t.properties, t.lifecycle_state
                        FROM ontology.types t
                        WHERE t.lifecycle_state = 'ACTIVE'
                        ORDER BY t.name
                    """)
                    types = [dict(row) for row in cur.fetchall()]
                    
                    cur.execute("""
                        SELECT r.name, r.description, r.source_type, r.target_type, r.cardinality
                        FROM ontology.relations r
                        ORDER BY r.name
                    """)
                    relations = [dict(row) for row in cur.fetchall()]
                    
                    return MCPResponse(
                        success=True,
                        data={
                            "domain": domain or "default",
                            "types": types,
                            "relations": relations,
                            "version": "1.0"
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Get schema failed: {e}")
            return MCPResponse(
                success=False,
                error=MCPError(code="INTERNAL_ERROR", message=str(e))
            )
    
    def get_usage(self, auth: AuthContext) -> MCPResponse:
        """
        Get current quota usage for the tenant.
        
        Args:
            auth: Authentication context
            
        Returns:
            MCPResponse with usage statistics
        """
        try:
            has_quota, quota_info, _ = self.check_quota(auth.tenant_id, estimated_tokens=0)
            
            return MCPResponse(
                success=True,
                data={
                    "quota": {
                        "daily": {
                            "limit": quota_info['daily_limit'],
                            "used": quota_info['daily_used'],
                            "remaining": quota_info['daily_remaining']
                        },
                        "monthly": {
                            "limit": quota_info['monthly_limit'],
                            "used": quota_info['monthly_used'],
                            "remaining": quota_info['monthly_remaining']
                        }
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Get usage failed: {e}")
            return MCPResponse(
                success=False,
                error=MCPError(code="INTERNAL_ERROR", message=str(e))
            )
    
    def handle_tool_call(self, api_key: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for MCP tool calls.
        
        Args:
            api_key: API key for authentication
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            JSON-serializable response
        """
        auth, auth_error = self.authenticate(api_key)
        if auth_error:
            return {"success": False, "error": asdict(auth_error)}
        
        tool_handlers = {
            "query_context": lambda: self.query_context(
                auth,
                query=arguments.get("query", ""),
                entity_types=arguments.get("entity_types"),
                limit=arguments.get("limit", 10),
                include_relationships=arguments.get("include_relationships", True)
            ),
            "verify_statement": lambda: self.verify_statement(
                auth,
                statement=arguments.get("statement", ""),
                confidence_threshold=arguments.get("confidence_threshold", 0.7)
            ),
            "ingest_document": lambda: self.ingest_document(
                auth,
                filename=arguments.get("filename", "document.txt"),
                content=arguments.get("content", b"").encode() if isinstance(arguments.get("content"), str) else arguments.get("content", b""),
                mime_type=arguments.get("mime_type", "text/plain"),
                priority=arguments.get("priority", "normal")
            ),
            "get_document_status": lambda: self.get_document_status(
                auth,
                document_id=arguments.get("document_id", "")
            ),
            "list_entity_types": lambda: self.list_entity_types(auth)
        }
        
        if tool_name not in tool_handlers:
            return {
                "success": False,
                "error": {"code": "UNKNOWN_TOOL", "message": f"Tool '{tool_name}' not found"}
            }
        
        response = tool_handlers[tool_name]()
        
        result = {"success": response.success}
        if response.data:
            result["data"] = response.data
        if response.error:
            result["error"] = asdict(response.error)
        if response.tokens_consumed:
            result["tokens_consumed"] = response.tokens_consumed
        
        return result
    
    def handle_resource_request(self, api_key: str, resource_uri: str) -> Dict[str, Any]:
        """
        Handle MCP resource requests.
        
        Args:
            api_key: API key for authentication
            resource_uri: Resource URI (e.g., context://schema/default)
            
        Returns:
            JSON-serializable response
        """
        auth, auth_error = self.authenticate(api_key)
        if auth_error:
            return {"success": False, "error": asdict(auth_error)}
        
        if resource_uri.startswith("context://schema"):
            parts = resource_uri.split("/")
            domain = parts[-1] if len(parts) > 2 else None
            response = self.get_schema(auth, domain)
        elif resource_uri == "context://usage":
            response = self.get_usage(auth)
        else:
            return {
                "success": False,
                "error": {"code": "UNKNOWN_RESOURCE", "message": f"Resource '{resource_uri}' not found"}
            }
        
        result = {"success": response.success}
        if response.data:
            result["data"] = response.data
        if response.error:
            result["error"] = asdict(response.error)
        
        return result
