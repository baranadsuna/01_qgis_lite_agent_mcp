# -*- coding: utf-8 -*-
"""
AST Static Security Sandbox & Localhost Loopback Authenticator (`security_guard.py`).

Inspects AI-proposed PyQGIS snippets and tool parameters before execution:
- Classifies operations into `READ_ONLY`, `WORKSPACE_MUTATION`, or `BLOCKED`.
- Blocks dangerous modules (`subprocess`, `socket`, `shutil`, `ctypes`, etc.),
  dangerous built-ins (`eval`, `exec`, `compile`, `__import__`, `open`),
  OS command execution (`os.system`, `os.popen`, `os.remove`), and dunder escapes.
- Generates and validates ephemeral `127.0.0.1` session tokens using `secrets.token_hex(16)`.
"""

import ast
import hmac
import io
import os
import secrets
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class RiskLevel( str, Enum ):
    """Three-tier security classification for agent operations."""

    READ_ONLY = "READ_ONLY"
    WORKSPACE_MUTATION = "WORKSPACE_MUTATION"
    BLOCKED = "BLOCKED"


FORBIDDEN_ROOT_MODULES: Set[str] = {
    "subprocess",
    "shutil",
    "socket",
    "ssl",
    "http",
    "urllib",
    "requests",
    "ftplib",
    "telnetlib",
    "smtplib",
    "xmlrpc",
    "ctypes",
    "multiprocessing",
    "threading",
    "concurrent",
    "asyncio",
    "pickle",
    "cPickle",
    "marshal",
    "shelve",
    "importlib",
    "builtins",
    "__builtin__",
    "sys",
    "pty",
    "tty",
    "winreg",
    "msvcrt",
    "webbrowser",
    " tempfile",
}

FORBIDDEN_BUILTINS: Set[str] = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "input",
    "breakpoint",
    "globals",
    "locals",
    "vars",
    "delattr",
    "setattr",
}

FORBIDDEN_OS_ATTRIBUTES: Set[str] = {
    "system",
    "popen",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "execl",
    "execle",
    "execlp",
    "execlpe",
    "execv",
    "execve",
    "execvp",
    "execvpe",
    "remove",
    "unlink",
    "rmdir",
    "removedirs",
    "rename",
    "replace",
    "chmod",
    "chown",
    "kill",
    "fork",
    "putenv",
    "environ",
}

FORBIDDEN_DUNDERS: Set[str] = {
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__code__",
    "__closure__",
    "__bases__",
    "__mro__",
    "__dict__",
    "__import__",
    "__loader__",
    "__spec__",
}

MUTATING_CALL_NAMES: Set[str] = {
    "run",
    "runAndLoadResults",
    "addMapLayer",
    "removeMapLayer",
    "removeAllMapLayers",
    "clear",
    "setCrs",
    "startEditing",
    "commitChanges",
    "rollBack",
    "addFeature",
    "addFeatures",
    "deleteFeature",
    "deleteFeatures",
    "changeAttributeValue",
    "changeGeometry",
    "addAttribute",
    "deleteAttribute",
    "updateFeature",
    "updateFields",
    "writeAsVectorFormat",
    "writeAsVectorFormatV2",
    "writeAsVectorFormatV3",
    "setSubsetString",
    "triggerRepaint",
}


@dataclass
class SecurityAuditResult:
    """Structured result returned by `SecurityGuard.inspect_code()`."""

    risk_level: RiskLevel
    allowed_auto: bool
    requires_approval: bool
    reasons: List[str] = field(default_factory=list)
    detected_mutations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "allowed_auto": self.allowed_auto,
            "requires_approval": self.requires_approval,
            "reasons": list(self.reasons),
            "detected_mutations": list(self.detected_mutations),
        }


class _AstSecurityVisitor(ast.NodeVisitor):
    """AST visitor that detects forbidden constructs and workspace mutations."""

    def __init__(self) -> None:
        self.violations: List[str] = []
        self.mutations: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_mod = alias.name.split(".")[0].strip()
            if root_mod in FORBIDDEN_ROOT_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Importing forbidden module '{alias.name}' is blocked."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_name = (node.module or "").strip()
        root_mod = module_name.split(".")[0] if module_name else ""
        if root_mod in FORBIDDEN_ROOT_MODULES:
            self.violations.append(
                f"Line {node.lineno}: Importing from forbidden module '{module_name}' is blocked."
            )
        for alias in node.names:
            if alias.name in FORBIDDEN_ROOT_MODULES or alias.name in FORBIDDEN_BUILTINS:
                self.violations.append(
                    f"Line {node.lineno}: Importing forbidden symbol '{alias.name}' is blocked."
                )
            if root_mod == "os" and alias.name in FORBIDDEN_OS_ATTRIBUTES:
                self.violations.append(
                    f"Line {node.lineno}: Importing dangerous OS function 'os.{alias.name}' is blocked."
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        attr = node.attr
        if attr in FORBIDDEN_DUNDERS or (attr.startswith("__") and attr.endswith("__")):
            self.violations.append(
                f"Line {node.lineno}: Accessing dunder attribute '{attr}' is blocked by sandbox policy."
            )
        if isinstance(node.value, ast.Name) and node.value.id == "os":
            if attr in FORBIDDEN_OS_ATTRIBUTES:
                self.violations.append(
                    f"Line {node.lineno}: Accessing 'os.{attr}' is blocked by sandbox policy."
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_DUNDERS:
            self.violations.append(
                f"Line {node.lineno}: Referencing restricted identifier '{node.id}' is blocked."
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        qualified_name = ""

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            qualified_name = func_name
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                qualified_name = f"{node.func.value.id}.{func_name}"
            else:
                qualified_name = func_name

        if func_name in FORBIDDEN_BUILTINS:
            self.violations.append(
                f"Line {node.lineno}: Calling built-in '{func_name}()' is blocked by sandbox policy."
            )

        if qualified_name.startswith("os.") and func_name in FORBIDDEN_OS_ATTRIBUTES:
            self.violations.append(
                f"Line {node.lineno}: Calling '{qualified_name}()' is blocked by sandbox policy."
            )

        if qualified_name.startswith("shutil.") or qualified_name.startswith("subprocess."):
            self.violations.append(
                f"Line {node.lineno}: Calling '{qualified_name}()' is blocked by sandbox policy."
            )

        if func_name in MUTATING_CALL_NAMES or qualified_name in (
            "processing.run",
            "processing.runAndLoadResults",
        ):
            self.mutations.append(f"Line {node.lineno}: {qualified_name}()")

        self.generic_visit(node)


class SecurityGuard:
    """Central security gatekeeper for AST code inspection, path validation, and loopback auth."""

    LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

    def __init__(self, workspace_dir: Optional[str] = None) -> None:
        self._session_token: str = secrets.token_hex(16)
        self._workspace_dir: Optional[Path] = (
            Path(workspace_dir).resolve() if workspace_dir else None
        )

    @property
    def session_token(self) -> str:
        """Return the ephemeral 32-hex-char session token for localhost loopback calls."""
        return self._session_token

    def rotate_session_token(self) -> str:
        """Generate a fresh 128-bit session token."""
        self._session_token = secrets.token_hex(16)
        return self._session_token

    def verify_session_token(self, candidate_token: Optional[str]) -> bool:
        """Verify a candidate session token in constant time."""
        if not candidate_token or not isinstance(candidate_token, str):
            return False
        return hmac.compare_digest(self._session_token, candidate_token.strip())

    def is_loopback_host(self, host: str) -> bool:
        """Ensure socket host is strictly bound to local loopback."""
        return host.strip().lower() in self.LOOPBACK_HOSTS

    def is_path_within_workspace(self, candidate_path: str) -> bool:
        """Verify that a file path does not escape the permitted workspace directory."""
        if not candidate_path:
            return False
        if candidate_path.startswith("memory:") or candidate_path == "TEMPORARY_OUTPUT":
            return True
        if self._workspace_dir is None:
            return True
        try:
            resolved = Path(candidate_path).resolve()
            resolved.relative_to(self._workspace_dir)
            return True
        except Exception:
            return False

    def inspect_code(self, code: str) -> SecurityAuditResult:
        """Statically analyze Python/PyQGIS source code via AST before execution."""
        if not code or not code.strip():
            return SecurityAuditResult(
                risk_level=RiskLevel.BLOCKED,
                allowed_auto=False,
                requires_approval=False,
                reasons=["Empty code snippet provided."],
            )

        if len(code) > 25000:
            return SecurityAuditResult(
                risk_level=RiskLevel.BLOCKED,
                allowed_auto=False,
                requires_approval=False,
                reasons=["Code snippet exceeds maximum safe length (25,000 chars)."],
            )

        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            return SecurityAuditResult(
                risk_level=RiskLevel.BLOCKED,
                allowed_auto=False,
                requires_approval=False,
                reasons=[f"Python SyntaxError at line {exc.lineno}: {exc.msg}"],
            )

        visitor = _AstSecurityVisitor()
        visitor.visit(tree)

        if visitor.violations:
            return SecurityAuditResult(
                risk_level=RiskLevel.BLOCKED,
                allowed_auto=False,
                requires_approval=False,
                reasons=visitor.violations,
                detected_mutations=visitor.mutations,
            )

        if visitor.mutations:
            return SecurityAuditResult(
                risk_level=RiskLevel.WORKSPACE_MUTATION,
                allowed_auto=False,
                requires_approval=True,
                reasons=[
                    "Code performs workspace or layer mutations and requires explicit user approval."
                ],
                detected_mutations=visitor.mutations,
            )

        return SecurityAuditResult(
            risk_level=RiskLevel.READ_ONLY,
            allowed_auto=True,
            requires_approval=False,
            reasons=["AST static check passed: Read-only PyQGIS inspection."],
            detected_mutations=[],
        )

    def inspect_processing_call(
        self, alg_id: str, params: Dict[str, Any]
    ) -> SecurityAuditResult:
        """Inspect a `qgis.processing` algorithm request and validate output paths."""
        if not alg_id or ":" not in alg_id:
            return SecurityAuditResult(
                risk_level=RiskLevel.BLOCKED,
                allowed_auto=False,
                requires_approval=False,
                reasons=[f"Invalid processing algorithm identifier: '{alg_id}'."],
            )

        provider = alg_id.split(":", 1)[0].lower()
        allowed_providers = {"native", "qgis", "gdal", "grass", "grass7", "saga", "model"}
        if provider not in allowed_providers:
            return SecurityAuditResult(
                risk_level=RiskLevel.BLOCKED,
                allowed_auto=False,
                requires_approval=False,
                reasons=[f"Provider '{provider}' is not in the approved processing provider list."],
            )

        for key, val in (params or {}).items():
            if isinstance(val, str) and ("OUTPUT" in key.upper() or os.path.sep in val or "/" in val):
                if val not in ("TEMPORARY_OUTPUT", "memory:") and not val.startswith("memory:"):
                    if self._workspace_dir is not None and not self.is_path_within_workspace(val):
                        return SecurityAuditResult(
                            risk_level=RiskLevel.BLOCKED,
                            allowed_auto=False,
                            requires_approval=False,
                            reasons=[
                                f"Parameter '{key}' references path '{val}' outside approved workspace."
                            ],
                        )

        return SecurityAuditResult(
            risk_level=RiskLevel.WORKSPACE_MUTATION,
            allowed_auto=False,
            requires_approval=True,
            reasons=[f"Processing algorithm '{alg_id}' requires user approval before execution."],
            detected_mutations=[f"processing.run('{alg_id}')"],
        )

    def execute_guarded_pyqgis(
        self,
        code: str,
        iface: Any = None,
        human_approved: bool = False,
    ) -> Dict[str, Any]:
        """Execute PyQGIS code only after AST validation and (if mutating) human approval."""
        audit = self.inspect_code(code)
        if audit.risk_level == RiskLevel.BLOCKED:
            return {
                "ok": False,
                "status": "BLOCKED",
                "audit": audit.to_dict(),
                "error": "; ".join(audit.reasons),
            }

        if audit.risk_level == RiskLevel.WORKSPACE_MUTATION and not human_approved:
            return {
                "ok": False,
                "status": "AWAITING_HUMAN_APPROVAL",
                "audit": audit.to_dict(),
                "error": "Mutating operation requires explicit user approval (human_approved=True).",
            }

        import qgis.core as qgis_core
        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsExpression,
            QgsFeature,
            QgsFeatureRequest,
            QgsField,
            QgsGeometry,
            QgsPointXY,
            QgsProject,
            QgsRasterLayer,
            QgsRectangle,
            QgsVectorLayer,
            QgsWkbTypes,
        )

        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "int": int,
            "isinstance": isinstance,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "print": print,
            "range": range,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
        }

        sandbox_globals: Dict[str, Any] = {
            "__builtins__": safe_builtins,
            "qgis": qgis_core,
            "QgsProject": QgsProject,
            "QgsVectorLayer": QgsVectorLayer,
            "QgsRasterLayer": QgsRasterLayer,
            "QgsCoordinateReferenceSystem": QgsCoordinateReferenceSystem,
            "QgsFeature": QgsFeature,
            "QgsFeatureRequest": QgsFeatureRequest,
            "QgsField": QgsField,
            "QgsGeometry": QgsGeometry,
            "QgsPointXY": QgsPointXY,
            "QgsRectangle": QgsRectangle,
            "QgsWkbTypes": QgsWkbTypes,
            "QgsExpression": QgsExpression,
            "iface": iface,
            "result": None,
        }

        if human_approved:
            try:
                import processing

                sandbox_globals["processing"] = processing
            except ImportError:
                pass

        stdout_buf = io.StringIO()
        try:
            compiled = compile(ast.parse(code, mode="exec"), "<qgis_lite_agent_sandbox>", "exec")
            with redirect_stdout(stdout_buf):
                exec(compiled, sandbox_globals, sandbox_globals)  # noqa: S102 - guarded by AST + restricted builtins
        except Exception as exc:
            return {
                "ok": False,
                "status": "RUNTIME_ERROR",
                "audit": audit.to_dict(),
                "stdout": stdout_buf.getvalue()[:2000],
                "error": f"{type(exc).__name__}: {exc}",
            }

        return {
            "ok": True,
            "status": "EXECUTED",
            "audit": audit.to_dict(),
            "stdout": stdout_buf.getvalue()[:2000].strip(),
            "result": sandbox_globals.get("result"),
        }
