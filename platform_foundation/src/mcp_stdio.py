#!/usr/bin/env python3
"""
MCP Stdio Transport Server for Claude Desktop Integration.

Wraps the existing MCPServer class with stdio transport for Model Context Protocol.
Connect via Claude Desktop by adding this server to claude_desktop_config.json.
"""

import sys
import json
import os
import logging
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from platform_foundation.src.mcp_server import MCPServer, AuthContext

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('/tmp/mcp_stdio.log')]
)
logger = logging.getLogger(__name__)

MCP_VERSION = "2024-11-05"
SERVER_NAME = "context-foundry"
SERVER_VERSION = "1.0.0"


class MCPStdioServer:
    """
    Stdio transport wrapper for MCPServer.
    Implements MCP protocol over stdin/stdout for Claude Desktop.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.mcp = MCPServer(
            database_url=os.environ.get("DATABASE_URL"),
            brain_url=os.environ.get("BRAIN_URL", "http://localhost:3000")
        )
        self.api_key = api_key or os.environ.get("CF_API_KEY")
        self.auth_context = None
        self._initialized = False
        
    def _authenticate(self) -> bool:
        """Authenticate with stored API key."""
        if not self.api_key:
            logger.error("No API key configured")
            return False
            
        auth, error = self.mcp.authenticate(self.api_key)
        if error:
            logger.error(f"Authentication failed: {error.message}")
            return False
            
        self.auth_context = auth
        return True
    
    def _read_message(self) -> Optional[Dict[str, Any]]:
        """Read a JSON-RPC message from stdin using MCP Content-Length framing (binary I/O)."""
        try:
            stdin = sys.stdin.buffer
            content_length = None
            
            while True:
                header_line = b""
                while True:
                    char = stdin.read(1)
                    if not char:
                        return None
                    if char == b"\n":
                        break
                    header_line += char
                
                header_line = header_line.rstrip(b"\r")
                if not header_line:
                    break
                    
                header_str = header_line.decode("utf-8")
                if header_str.lower().startswith("content-length:"):
                    content_length = int(header_str.split(":", 1)[1].strip())
            
            if content_length is None:
                logger.error("No Content-Length header found")
                return None
            
            content_bytes = stdin.read(content_length)
            if not content_bytes or len(content_bytes) < content_length:
                return None
            
            content = content_bytes.decode("utf-8")
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
            return None
        except Exception as e:
            logger.error(f"Read error: {e}")
            return None
    
    def _write_message(self, msg: Dict[str, Any]):
        """Write a JSON-RPC message to stdout using MCP Content-Length framing (binary I/O)."""
        try:
            stdout = sys.stdout.buffer
            content = json.dumps(msg)
            content_bytes = content.encode("utf-8")
            header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
            stdout.write(header.encode("utf-8"))
            stdout.write(content_bytes)
            stdout.flush()
        except Exception as e:
            logger.error(f"Write error: {e}")
    
    def _make_response(self, id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": id, "result": result}
    
    def _make_error(self, id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    
    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        self._initialized = True
        return {
            "protocolVersion": MCP_VERSION,
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION
            },
            "capabilities": {
                "tools": {},
                "resources": {}
            }
        }
    
    def handle_tools_list(self) -> Dict[str, Any]:
        """Return available tools."""
        return {
            "tools": [
                {
                    "name": "query_context",
                    "description": "Query the Context Foundry knowledge graph for entities, relationships, and facts. Returns grounded answers with evidence chains.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language query about the knowledge graph"
                            },
                            "entity_types": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional filter for entity types (e.g., ['PERSON', 'ORGANIZATION'])"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum results to return (default: 10)"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "verify_statement",
                    "description": "Verify a factual statement against the knowledge graph. Returns verification status with supporting evidence.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "statement": {
                                "type": "string",
                                "description": "Statement to verify"
                            },
                            "confidence_threshold": {
                                "type": "number",
                                "description": "Minimum confidence for verification (default: 0.7)"
                            }
                        },
                        "required": ["statement"]
                    }
                },
                {
                    "name": "list_entity_types",
                    "description": "List available entity types from the ontology schema.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "get_document_status",
                    "description": "Get extraction status for a document.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": "Document UUID"
                            }
                        },
                        "required": ["document_id"]
                    }
                }
            ]
        }
    
    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call."""
        if not self.auth_context:
            if not self._authenticate():
                return {
                    "content": [{"type": "text", "text": "Authentication failed. Check CF_API_KEY environment variable."}],
                    "isError": True
                }
        
        try:
            if name == "query_context":
                result = self.mcp.query_context(
                    auth=self.auth_context,
                    query=arguments.get("query", ""),
                    entity_types=arguments.get("entity_types"),
                    limit=arguments.get("limit", 10),
                    include_relationships=True
                )
            elif name == "verify_statement":
                result = self.mcp.verify_statement(
                    auth=self.auth_context,
                    statement=arguments.get("statement", ""),
                    confidence_threshold=arguments.get("confidence_threshold", 0.7)
                )
            elif name == "list_entity_types":
                result = self.mcp.list_entity_types(auth=self.auth_context)
            elif name == "get_document_status":
                result = self.mcp.get_document_status(
                    auth=self.auth_context,
                    document_id=arguments.get("document_id", "")
                )
            else:
                return {
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True
                }
            
            if result.success:
                return {
                    "content": [{"type": "text", "text": json.dumps(result.data, indent=2)}]
                }
            else:
                error_msg = result.error.message if result.error else "Unknown error"
                return {
                    "content": [{"type": "text", "text": f"Error: {error_msg}"}],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return {
                "content": [{"type": "text", "text": f"Error executing {name}: {str(e)}"}],
                "isError": True
            }
    
    def handle_resources_list(self) -> Dict[str, Any]:
        """Return available resources."""
        return {
            "resources": [
                {
                    "uri": "context://schema",
                    "name": "Ontology Schema",
                    "description": "The complete ontology schema including entity types and relationships",
                    "mimeType": "application/json"
                },
                {
                    "uri": "context://usage",
                    "name": "API Usage",
                    "description": "Current quota usage for this API key",
                    "mimeType": "application/json"
                }
            ]
        }
    
    def handle_resource_read(self, uri: str) -> Dict[str, Any]:
        """Read a resource."""
        if not self.auth_context:
            if not self._authenticate():
                return {
                    "contents": [{"uri": uri, "text": "Authentication failed", "mimeType": "text/plain"}]
                }
        
        try:
            if uri == "context://schema":
                result = self.mcp.get_schema(auth=self.auth_context)
                if result.success:
                    return {
                        "contents": [{
                            "uri": uri,
                            "text": json.dumps(result.data, indent=2),
                            "mimeType": "application/json"
                        }]
                    }
            elif uri == "context://usage":
                result = self.mcp.get_usage(auth=self.auth_context)
                if result.success:
                    return {
                        "contents": [{
                            "uri": uri,
                            "text": json.dumps(result.data, indent=2),
                            "mimeType": "application/json"
                        }]
                    }
            
            return {
                "contents": [{"uri": uri, "text": f"Resource not found: {uri}", "mimeType": "text/plain"}]
            }
        except Exception as e:
            return {
                "contents": [{"uri": uri, "text": f"Error: {str(e)}", "mimeType": "text/plain"}]
            }
    
    def run(self):
        """Main event loop - read messages from stdin, write responses to stdout."""
        logger.info("MCP Stdio Server starting...")
        
        while True:
            try:
                msg = self._read_message()
                if msg is None:
                    break
                
                method = msg.get("method", "")
                params = msg.get("params", {})
                msg_id = msg.get("id")
                
                logger.info(f"Received: {method}")
                
                if method == "initialize":
                    result = self.handle_initialize(params)
                    self._write_message(self._make_response(msg_id, result))
                    
                elif method == "notifications/initialized":
                    pass
                    
                elif method == "tools/list":
                    result = self.handle_tools_list()
                    self._write_message(self._make_response(msg_id, result))
                    
                elif method == "tools/call":
                    name = params.get("name", "")
                    arguments = params.get("arguments", {})
                    result = self.handle_tool_call(name, arguments)
                    self._write_message(self._make_response(msg_id, result))
                    
                elif method == "resources/list":
                    result = self.handle_resources_list()
                    self._write_message(self._make_response(msg_id, result))
                    
                elif method == "resources/read":
                    uri = params.get("uri", "")
                    result = self.handle_resource_read(uri)
                    self._write_message(self._make_response(msg_id, result))
                    
                elif method == "ping":
                    self._write_message(self._make_response(msg_id, {}))
                    
                else:
                    logger.warning(f"Unknown method: {method}")
                    if msg_id:
                        self._write_message(self._make_error(msg_id, -32601, f"Method not found: {method}"))
                        
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                continue
        
        logger.info("MCP Stdio Server shutting down")


def main():
    api_key = os.environ.get("CF_API_KEY")
    if not api_key:
        print("Error: CF_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)
    
    server = MCPStdioServer(api_key=api_key)
    server.run()


if __name__ == "__main__":
    main()
