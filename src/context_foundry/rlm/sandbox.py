"""
REPLSandbox - Secure code execution environment for RLM.

Executes LLM-generated Python code in a restricted namespace with:
- Access to Memory APIs (semantic, episodic, symbolic)
- Safe subset of Python builtins
- stdout capture
- Timeout enforcement
- Progress tracking integration
"""

import re
import sys
import time
import signal
import traceback
from io import StringIO
from typing import Dict, Any, Optional, Callable, List
from contextlib import contextmanager

from .schemas import REPLExecutionResult


SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "frozenset": frozenset,
    "hasattr": hasattr,
    "hash": hash,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}

RESTRICTED_PATTERNS = [
    r"\bimport\b",
    r"__import__",
    r"\beval\b",
    r"\bexec\b",
    r"\bcompile\b",
    r"\bopen\b",
    r"\bfile\b",
    r"\bos\.",
    r"\bsys\.",
    r"\bsubprocess",
    r"__builtins__",
    r"__class__",
    r"__bases__",
    r"__subclasses__",
    r"__mro__",
    r"__globals__",
    r"__code__",
    r"__reduce__",
    r"__getattribute__",
    r"__setattr__",
    r"__delattr__",
    r"__dict__",
    r"__slots__",
    r"\bbreakpoint\b",
    r"\binput\b",
    r"\bgetattr\b",
    r"\bsetattr\b",
    r"\bdelattr\b",
    r"\._session\b",
    r"\._tenant_id\b",
    r"['\"]\s*_session\s*['\"]",
    r"['\"]\s*_tenant_id\s*['\"]",
]


class SandboxSecurityError(Exception):
    """Raised when code contains restricted patterns."""
    pass


class SandboxTimeoutError(Exception):
    """Raised when code execution times out."""
    pass


class REPLSandbox:
    """
    Secure execution environment for RLM-generated code.
    
    Provides:
    - Restricted namespace with safe builtins
    - Access to Memory APIs as named objects
    - stdout capture for print() statements
    - Timeout enforcement
    - Entity/relationship discovery tracking
    """
    
    def __init__(
        self, 
        memory_apis: Dict[str, Any],
        llm_apis: Dict[str, Callable] = None,
        timeout_seconds: int = 30
    ):
        """
        Initialize sandbox environment.
        
        Args:
            memory_apis: Dict of memory API instances {'semantic': ..., 'episodic': ..., 'symbolic': ...}
            llm_apis: Dict of LLM API functions {'llm_query': ..., 'llm_verify': ...}
            timeout_seconds: Default execution timeout
        """
        self.memory_apis = memory_apis
        self.llm_apis = llm_apis or {}
        self.timeout_seconds = timeout_seconds
        self.output_buffer: List[str] = []
        self.globals_namespace = self._create_safe_globals()
        self.locals_namespace: Dict[str, Any] = {}
        
        self._discovered_entities: List[str] = []
        self._discovered_relationships: List[str] = []
    
    def _create_safe_globals(self) -> Dict[str, Any]:
        """Create restricted globals namespace."""
        safe_globals = {
            "__builtins__": SAFE_BUILTINS.copy(),
            "print": self._capture_print,
        }
        
        safe_globals["semantic"] = self.memory_apis.get("semantic")
        safe_globals["episodic"] = self.memory_apis.get("episodic")
        safe_globals["symbolic"] = self.memory_apis.get("symbolic")
        
        for name, func in self.llm_apis.items():
            safe_globals[name] = func
        
        safe_globals["answer"] = None
        safe_globals["evidence"] = []
        safe_globals["notes"] = []
        
        return safe_globals
    
    def _capture_print(self, *args, **kwargs):
        """Capture print statements to output buffer."""
        output = StringIO()
        kwargs['file'] = output
        print(*args, **kwargs)
        self.output_buffer.append(output.getvalue().rstrip('\n'))
    
    def _validate_code(self, code: str) -> Optional[str]:
        """
        Validate code against security restrictions.
        
        Returns:
            Error message if code is unsafe, None if safe
        """
        for pattern in RESTRICTED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return f"Restricted pattern detected: '{pattern}' - This operation is not allowed in the sandbox"
        
        try:
            compile(code, '<sandbox>', 'exec')
        except SyntaxError as e:
            return f"Syntax error: {e.msg} at line {e.lineno}"
        
        return None
    
    @contextmanager
    def _timeout_handler(self, seconds: int):
        """Context manager for timeout enforcement using signal."""
        def handler(signum, frame):
            raise SandboxTimeoutError(f"Code execution timed out after {seconds} seconds")
        
        old_handler = None
        try:
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, handler)
                signal.alarm(seconds)
            yield
        finally:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                if old_handler:
                    signal.signal(signal.SIGALRM, old_handler)
    
    def _collect_discovered_ids(self) -> tuple:
        """Collect newly discovered entity and relationship IDs from memory APIs."""
        new_entities = []
        new_relationships = []
        
        if 'semantic' in self.memory_apis and self.memory_apis['semantic']:
            api = self.memory_apis['semantic']
            if hasattr(api, 'get_accessed_entity_ids'):
                new_entities.extend(api.get_accessed_entity_ids())
        
        if 'symbolic' in self.memory_apis and self.memory_apis['symbolic']:
            api = self.memory_apis['symbolic']
            if hasattr(api, 'get_accessed_relationship_ids'):
                new_relationships.extend(api.get_accessed_relationship_ids())
        
        unique_entities = list(set(new_entities) - set(self._discovered_entities))
        unique_relationships = list(set(new_relationships) - set(self._discovered_relationships))
        
        self._discovered_entities.extend(unique_entities)
        self._discovered_relationships.extend(unique_relationships)
        
        return unique_entities, unique_relationships
    
    def execute(self, code: str, timeout_seconds: int = None) -> REPLExecutionResult:
        """
        Execute code in the sandbox.
        
        Args:
            code: Python code to execute
            timeout_seconds: Override default timeout
        
        Returns:
            REPLExecutionResult with execution details
        """
        timeout = timeout_seconds or self.timeout_seconds
        start_time = time.time()
        
        validation_error = self._validate_code(code)
        if validation_error:
            return REPLExecutionResult(
                success=False,
                output="",
                error=validation_error,
                retry_hint="Remove restricted operations and try again",
                execution_time_ms=int((time.time() - start_time) * 1000),
                new_entities_discovered=[],
                new_relationships_discovered=[]
            )
        
        self.output_buffer = []
        
        try:
            with self._timeout_handler(timeout):
                exec(code, self.globals_namespace, self.locals_namespace)
            
            output = "\n".join(self.output_buffer) if self.output_buffer else ""
            
            new_entities, new_relationships = self._collect_discovered_ids()
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return REPLExecutionResult(
                success=True,
                output=output,
                error=None,
                retry_hint=None,
                execution_time_ms=execution_time_ms,
                new_entities_discovered=new_entities,
                new_relationships_discovered=new_relationships
            )
            
        except SandboxTimeoutError as e:
            return REPLExecutionResult(
                success=False,
                output="\n".join(self.output_buffer),
                error=str(e),
                retry_hint="Code took too long. Simplify the operation or use smaller limits.",
                execution_time_ms=timeout * 1000,
                new_entities_discovered=[],
                new_relationships_discovered=[]
            )
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"{type(e).__name__}: {str(e)}"
            retry_hint = generate_retry_hint(e, code)
            
            return REPLExecutionResult(
                success=False,
                output="\n".join(self.output_buffer),
                error=error_msg,
                retry_hint=retry_hint,
                execution_time_ms=execution_time_ms,
                new_entities_discovered=[],
                new_relationships_discovered=[]
            )
    
    def get_variable(self, name: str) -> Any:
        """Get a variable from the sandbox namespace."""
        if name in self.locals_namespace:
            return self.locals_namespace[name]
        if name in self.globals_namespace:
            return self.globals_namespace[name]
        return None
    
    def set_variable(self, name: str, value: Any):
        """Set a variable in the sandbox namespace."""
        self.globals_namespace[name] = value
    
    def reset(self):
        """Reset the sandbox to initial state."""
        self.output_buffer = []
        self.locals_namespace = {}
        self._discovered_entities = []
        self._discovered_relationships = []
        
        if 'semantic' in self.memory_apis and self.memory_apis['semantic']:
            api = self.memory_apis['semantic']
            if hasattr(api, 'clear_access_tracking'):
                api.clear_access_tracking()
        
        if 'episodic' in self.memory_apis and self.memory_apis['episodic']:
            api = self.memory_apis['episodic']
            if hasattr(api, 'clear_access_tracking'):
                api.clear_access_tracking()
        
        if 'symbolic' in self.memory_apis and self.memory_apis['symbolic']:
            api = self.memory_apis['symbolic']
            if hasattr(api, 'clear_access_tracking'):
                api.clear_access_tracking()
        
        self.globals_namespace = self._create_safe_globals()


def generate_retry_hint(error: Exception, code: str) -> Optional[str]:
    """
    Generate helpful retry hints based on error type.
    
    Args:
        error: The exception that occurred
        code: The code that caused the error
    
    Returns:
        Actionable hint string, or None if no hint available
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    if error_type == "AttributeError":
        if "EntitySummary" in error_msg or "entity" in code.lower():
            return "EntitySummary has: id, name, entity_type, confidence, lifecycle_state, created_at, updated_at, primary_property, property_count, relationship_count"
        if "EntityDetail" in error_msg:
            return "EntityDetail has: id, name, entity_type, confidence, lifecycle_state, properties, aliases, source_document_ids, extraction_method, corroboration_count"
        if "ChunkDetail" in error_msg or "chunk" in code.lower():
            return "ChunkDetail has: id, document_id, chunk_index, content, token_count, document_name, document_type, upload_date, page_numbers"
        if "Relationship" in error_msg:
            return "Relationship has: id, source_entity_id, source_entity_name, target_entity_id, target_entity_name, relationship_type, confidence, lifecycle_state, properties"
        match = re.search(r"has no attribute '(\w+)'", error_msg)
        if match:
            return f"Object has no attribute '{match.group(1)}'. Check the schema documentation for available attributes."
    
    if error_type == "KeyError":
        return f"Key {error.args[0] if error.args else 'unknown'} not found. Use .get() for safe access or check available keys first."
    
    if error_type == "TypeError":
        if "argument" in error_msg:
            return "Wrong number or type of arguments. Check the method signature in the API documentation."
        if "subscriptable" in error_msg:
            return "Cannot use [] on this type. It may be None or a non-subscriptable object."
    
    if error_type == "IndexError":
        return "List index out of range. Check the length of the list before accessing by index."
    
    if error_type == "StaleEntityError":
        return "Entity was archived by Gardener during execution. Search for it again or use a different entity."
    
    if error_type == "BudgetExhaustedError":
        return "Sub-query budget exhausted. Call finalize() with your current findings."
    
    if "division by zero" in error_msg:
        return "Division by zero. Check that the denominator is not zero."
    
    if "NoneType" in error_msg:
        return "Tried to access attribute or method on None. Check if the previous operation returned a result."
    
    return None
