# -*- coding: utf-8 -*-
"""
Lightweight Localhost (`127.0.0.1`) Non-Blocking MCP / Agent Bridge (`mcp_bridge.py`).

Exposes exactly 6 ultra-compact multiplexed tools to keep initial context token
footprint minimal (<150 tokens) while supporting:
- Antigravity / MCP Loopback clients
- Claude Code / Cursor / Codex / OpenCode
- Direct REST providers (Gemini, Claude, OpenAI/Codex, DeepSeek, Grok, Ollama)
"""

import json
import socket
import struct
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal

from .compact_context import CompactContextBuilder
from .model3_exporter import Model3Exporter
from .security_guard import RiskLevel, SecurityGuard

SUPPORTED_PROVIDERS: List[str] = [
    "Antigravity / MCP Loopback (127.0.0.1)",
    "Gemini (Google AI)",
    "Claude (Anthropic)",
    "OpenAI / Codex",
    "DeepSeek",
    "Grok (xAI)",
    "OpenCode",
    "Ollama (Local 127.0.0.1:11434)",
]

COMPACT_TOOL_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "get_compact_context",
        "description": "Get <150-token layer digest or SHA-256 delta for opted-in layers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "previous_hash": {"type": "string"},
                "include_samples": {"type": "boolean"},
            },
        },
    },
    {
        "name": "inspect_layer_stats",
        "description": "Get bounded real field stats & up to 3 sample rows for an opted-in layer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer": {"type": "string"},
                "field": {"type": "string"},
                "max_samples": {"type": "integer"},
            },
            "required": ["layer"],
        },
    },
    {
        "name": "validate_crs_epsg5253",
        "description": "Audit project & layers for EPSG:5253 (TUREF/TM30) compliance; optionally enforce project CRS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enforce_project_crs": {"type": "boolean"},
            },
        },
    },
    {
        "name": "run_processing_alg",
        "description": "Validate and queue/run a qgis.processing algorithm (requires human approval unless approved=true).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "alg_id": {"type": "string"},
                "params": {"type": "object"},
                "human_approved": {"type": "boolean"},
            },
            "required": ["alg_id", "params"],
        },
    },
    {
        "name": "export_model3",
        "description": "Export a chain of processing steps to native QGIS .model3 XML or standalone .py file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {"type": "array"},
                "output_path": {"type": "string"},
                "model_name": {"type": "string"},
            },
            "required": ["steps"],
        },
    },
    {
        "name": "execute_guarded_pyqgis",
        "description": "Run AST-validated PyQGIS snippet (READ_ONLY runs directly; WORKSPACE_MUTATION requires approval).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "human_approved": {"type": "boolean"},
            },
            "required": ["code"],
        },
    },
]


class McpLoopbackBridge(QObject):
    """Non-blocking `127.0.0.1` loopback JSON-RPC 2.0 / MCP bridge with 6 compact tools."""

    request_received = pyqtSignal(str, dict)
    pending_action_queued = pyqtSignal(dict)
    status_changed = pyqtSignal(bool, str)

    def __init__(
        self,
        context_builder: Optional[CompactContextBuilder] = None,
        security_guard: Optional[SecurityGuard] = None,
        model3_exporter: Optional[Model3Exporter] = None,
        iface: Any = None,
        host: str = "127.0.0.1",
        port: int = 9876,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.context_builder = context_builder or CompactContextBuilder()
        self.security_guard = security_guard or SecurityGuard()
        self.model3_exporter = model3_exporter or Model3Exporter()
        self.iface = iface
        self.host = host
        self.port = port

        self._server_socket: Optional[socket.socket] = None
        self._client_sockets: List[socket.socket] = []
        self._client_buffers: Dict[int, bytes] = {}
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)
        self._poll_timer.timeout.connect(self._poll_socket_events)
        self._pending_review_action: Optional[Dict[str, Any]] = None

    @property
    def is_running(self) -> bool:
        """Return True if the localhost loopback server socket is active."""
        return self._server_socket is not None

    @property
    def pending_review_action(self) -> Optional[Dict[str, Any]]:
        """Return the most recent action awaiting human-in-the-loop approval."""
        return self._pending_review_action

    def get_tool_catalog(self) -> List[Dict[str, Any]]:
        """Return the 6 ultra-compact multiplexed tool definitions."""
        return list(COMPACT_TOOL_CATALOG)

    def start_server(self, host: Optional[str] = None, port: Optional[int] = None) -> Dict[str, Any]:
        """Bind non-blocking TCP server strictly to 127.0.0.1 loopback."""
        bind_host = (host or self.host).strip()
        bind_port = self.port if port is None else int(port)

        if not self.security_guard.is_loopback_host(bind_host):
            msg = f"Security violation: Bridge must bind to 127.0.0.1 loopback, rejected '{bind_host}'."
            self.status_changed.emit(False, msg)
            return {"ok": False, "error": msg}

        if self._server_socket is not None:
            self.stop_server()

        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.setblocking(False)
            srv.bind((bind_host, bind_port))
            srv.listen(4)
            self._server_socket = srv
            self.host, self.port = srv.getsockname()[:2]
            self._poll_timer.start()
            status_msg = f"Listening on {self.host}:{self.port}"
            self.status_changed.emit(True, status_msg)
            return {
                "ok": True,
                "host": self.host,
                "port": self.port,
                "auth_token": self.security_guard.session_token,
            }
        except Exception as exc:
            self._server_socket = None
            err_msg = f"Failed to bind {bind_host}:{bind_port}: {exc}"
            self.status_changed.emit(False, err_msg)
            return {"ok": False, "error": err_msg}

    def stop_server(self) -> None:
        """Stop polling and close all loopback sockets cleanly."""
        self._poll_timer.stop()
        for cli in list(self._client_sockets):
            try:
                cli.close()
            except Exception:
                pass
        self._client_sockets.clear()
        self._client_buffers.clear()

        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None
        self.status_changed.emit(False, "Stopped")

    def dispatch_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        human_approved: bool = False,
    ) -> Dict[str, Any]:
        """Execute one of the 6 core tools with full security and CRS governance."""
        args = dict(arguments or {})
        effective_approved = bool(human_approved or args.get("human_approved", False))
        self.request_received.emit(tool_name, args)

        if tool_name == "get_compact_context":
            prev_hash = args.get("previous_hash")
            inc_samples = bool(args.get("include_samples", False))
            if prev_hash:
                return {
                    "ok": True,
                    "tool": tool_name,
                    "data": self.context_builder.build_delta_context(previous_hash= str(prev_hash)),
                }
            return {
                "ok": True,
                "tool": tool_name,
                "data": self.context_builder.build_compact_context(include_samples=inc_samples),
            }

        if tool_name == "inspect_layer_stats":
            layer_id = str(args.get("layer", "")).strip()
            field_name = args.get("field")
            max_samples = int(args.get("max_samples", 3))
            stats = self.context_builder.inspect_layer_stats(
                layer_id_or_name=layer_id,
                field_name=str(field_name) if field_name else None,
                max_samples=max_samples,
            )
            return {"ok": stats.get("ok", False), "tool": tool_name, "data": stats}

        if tool_name == "validate_crs_epsg5253":
            if args.get("enforce_project_crs"):
                self.context_builder.enforce_project_crs_epsg5253()
            report = self.context_builder.validate_crs_epsg5253()
            return {"ok": True, "tool": tool_name, "data": report}

        if tool_name == "run_processing_alg":
            alg_id = str(args.get("alg_id", "")).strip()
            params = args.get("params") or {}
            audit = self.security_guard.inspect_processing_call(alg_id, params)
            if audit.risk_level == RiskLevel.BLOCKED:
                return {
                    "ok": False,
                    "tool": tool_name,
                    "status": "BLOCKED",
                    "audit": audit.to_dict(),
                    "error": "; ".join(audit.reasons),
                }

            if not effective_approved:
                pending = {
                    "type": "processing",
                    "tool": tool_name,
                    "alg_id": alg_id,
                    "params": params,
                    "audit": audit.to_dict(),
                }
                self._pending_review_action = pending
                self.pending_action_queued.emit(pending)
                return {
                    "ok": False,
                    "tool": tool_name,
                    "status": "AWAITING_HUMAN_APPROVAL",
                    "audit": audit.to_dict(),
                    "message": f"Algorithm '{alg_id}' queued in Human-in-the-Loop Review Box.",
                }

            try:
                import processing

                res = processing.run(alg_id, params)
                return {
                    "ok": True,
                    "tool": tool_name,
                    "status": "EXECUTED",
                    "result": {k: str(v) for k, v in (res or {}).items()},
                }
            except Exception as exc:
                return {
                    "ok": False,
                    "tool": tool_name,
                    "status": "RUNTIME_ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                }

        if tool_name == "export_model3":
            steps = args.get("steps") or []
            output_path = args.get("output_path")
            model_name = str(args.get("model_name") or "LiteAgent_EPSG5253_Workflow")

            if output_path:
                if not self.security_guard.is_path_within_workspace(str(output_path)):
                    return {
                        "ok": False,
                        "tool": tool_name,
                        "status": "BLOCKED",
                        "error": f"Output path '{output_path}' is outside the permitted workspace.",
                    }
                export_res = self.model3_exporter.export_to_file(
                    steps=steps,
                    output_path=str(output_path),
                    model_name=model_name,
                )
                return {"ok": export_res.get("ok", False), "tool": tool_name, "data": export_res}

            validation = self.model3_exporter.dry_run_validate_steps(steps)
            if not validation["ok"]:
                return {"ok": False, "tool": tool_name, "data": validation}
            xml_str = self.model3_exporter.build_model3_xml(steps=steps, model_name=model_name)
            py_str = self.model3_exporter.build_python_script(steps=steps, model_name=model_name)
            return {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "model3_xml": xml_str,
                    "python_script": py_str,
                    "steps_count": len(steps),
                },
            }

        if tool_name == "execute_guarded_pyqgis":
            code = str(args.get("code", ""))
            audit = self.security_guard.inspect_code(code)
            if audit.risk_level == RiskLevel.WORKSPACE_MUTATION and not effective_approved:
                pending = {
                    "type": "pyqgis",
                    "tool": tool_name,
                    "code": code,
                    "audit": audit.to_dict(),
                }
                self._pending_review_action = pending
                self.pending_action_queued.emit(pending)
                return {
                    "ok": False,
                    "tool": tool_name,
                    "status": "AWAITING_HUMAN_APPROVAL",
                    "audit": audit.to_dict(),
                    "message": "Mutating PyQGIS snippet queued in Human-in-the-Loop Review Box.",
                }

            exec_res = self.security_guard.execute_guarded_pyqgis(
                code=code,
                iface=self.iface,
                human_approved=effective_approved,
            )
            exec_res["tool"] = tool_name
            return exec_res

        return {
            "ok": False,
            "error": f"Unknown tool '{tool_name}'. Supported tools: {[t['name'] for t in COMPACT_TOOL_CATALOG]}",
        }

    def handle_jsonrpc_Payload(
        self, payload: Dict[str, Any], require_token: bool = True
    ) -> Dict[str, Any]:
        """Process a JSON-RPC 2.0 / MCP request dictionary and return a JSON-RPC 2.0 response."""
        req_id = payload.get("id", 1)
        method = str(payload.get("method", "")).strip()
        params = payload.get("params") or {}

        if require_token:
            token = payload.get("auth_token") or (
                params.get("auth_token") if isinstance(params, dict) else None
            )
            if not self.security_guard.verify_session_token(token):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized: Invalid or missing localhost session auth_token.",
                    },
                }

        if method in ("ping", "health"):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "status": "ok",
                    "bridge": "qgis_lite_agent",
                    "tools_count": len(COMPACT_TOOL_CATALOG),
                    "standard_crs": self.context_builder.target_crs,
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.get_tool_catalog()},
            }

        if method == "tools/call":
            t_name = str(params.get("name", ""))
            t_args = params.get("arguments") or {}
            res = self.dispatch_tool(t_name, t_args, human_approved=False)
            return {"jsonrpc": "2.0", "id": req_id, "result": res}

        # Direct tool invocation shorthand (method == tool_name)
        if any(t["name"] == method for t in COMPACT_TOOL_CATALOG):
            res = self.dispatch_tool(method, params if isinstance(params, dict) else {}, human_approved=False)
            return {"jsonrpc": "2.0", "id": req_id, "result": res}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found."},
        }

    def _poll_socket_events(self) -> None:
        """Non-blocking poll of server socket and connected loopback clients."""
        if self._server_socket is None:
            return

        while True:
            try:
                client_sock, addr = self._server_socket.accept()
                peer_ip = str(addr[0])
                if not self.security_guard.is_loopback_host(peer_ip):
                    client_sock.close()
                    continue
                client_sock.setblocking(False)
                self._client_sockets.append(client_sock)
                self._client_buffers[client_sock.fileno()] = b""
            except (BlockingIOError, InterruptedError):
                break
            except Exception:
                break

        for cli in list(self._client_sockets):
            fd = cli.fileno()
            try:
                chunk = cli.recv(65536)
                if not chunk:
                    self._close_client(cli)
                    continue
                buf = self._client_buffers.get(fd, b"") + chunk
                self._client_buffers[fd] = buf
                self._process_client_buffer(cli)
            except (BlockingIOError, InterruptedError):
                continue
            except Exception:
                self._close_client(cli)

    def _process_client_buffer(self, cli: socket.socket) -> None:
        """Support both newline-delimited JSON-RPC and 4-byte big-endian length-prefixed framing."""
        fd = cli.fileno()
        buf = self._client_buffers.get(fd, b"")
        if not buf:
            return

        # Case 1: JSON object starting with '{' (newline-delimited or complete JSON)
        stripped = buf.lstrip()
        if stripped.startswith(b"{"):
            if b"\n" in buf:
                line, rest = buf.split(b"\n", 1)
                self._client_buffers[fd] = rest
                self._reply_json_bytes(cli, line.strip(), length_prefixed=False)
                return
            try:
                decoded = stripped.decode("utf-8")
                json.loads(decoded)
                self._client_buffers[fd] = b""
                self._reply_json_bytes(cli, stripped, length_prefixed=False)
            except Exception:
                pass
            return

        # Case 2: 4-byte big-endian length-prefixed framing
        if len(buf) >= 4:
            msg_len = struct.unpack(">I", buf[:4])[0]
            if msg_len > 5_000_000:
                self._close_client(cli)
                return
            if len(buf) >= 4 + msg_len:
                body = buf[4 : 4 + msg_len]
                self._client_buffers[fd] = buf[4 + msg_len :]
                self._reply_json_bytes(cli, body, length_prefixed=True)

    def _reply_json_bytes(
        self, cli: socket.socket, raw_bytes: bytes, length_prefixed: bool = False
    ) -> None:
        """Parse incoming JSON request, execute handler, and send framed response."""
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
            response = self.handle_jsonrpc_Payload(payload, require_token=True)
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }

        out_bytes = json.dumps(response, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            if length_prefixed:
                cli.sendall(struct.pack(">I", len(out_bytes)) + out_bytes)
            else:
                cli.sendall(out_bytes + b"\n")
        except Exception:
            self._close_client(cli)

    def _close_client(self, cli: socket.socket) -> None:
        fd = cli.fileno()
        self._client_buffers.pop(fd, None)
        if cli in self._client_sockets:
            self._client_sockets.remove(cli)
        try:
            cli.close()
        except Exception:
            pass

    def synthesize_local_action_proposal(self, user_prompt: str) -> Dict[str, Any]:
        """Deterministic, zero-hallucination local action planner when offline or using MCP Loopback.

        Generates a compact, inspectable PyQGIS snippet or processing step chain
        grounded strictly in the currently opted-in layers and EPSG:5253 standard.
        """
        ctx = self.context_builder.build_compact_context()
        layers = ctx.get("layers", [])
        prompt_lower = (user_prompt or "").lower()

        if "5253" in prompt_lower or "crs" in prompt_lower or "reproject" in prompt_lower:
            steps: List[Dict[str, Any]] = []
            for lyr in layers:
                if not lyr.get("ok5253", False):
                    alg = (
                        "native:reprojectlayer"
                        if str(lyr.get("t", "")).startswith("V:")
                        else "gdal:warpreproject"
                    )
                    steps.append(
                        {
                            "id": f"reproject_{lyr['id']}",
                            "alg_id": alg,
                            "description": f"Reproject {lyr['n']} from {lyr['crs']} to EPSG:5253",
                            "params": {
                                "INPUT": lyr["id"],
                                "TARGET_CRS": "EPSG:5253",
                                "OUTPUT": "TEMPORARY_OUTPUT",
                            },
                        }
                    )
            if not steps and layers:
                first_lyr = layers[0]
                steps.append(
                    {
                        "id": "reproject_step_1",
                        "alg_id": "native:reprojectlayer",
                        "description": f"Ensure {first_lyr['n']} is in EPSG:5253",
                        "params": {
                            "INPUT": first_lyr["id"],
                            "TARGET_CRS": "EPSG:5253",
                            "OUTPUT": "TEMPORARY_OUTPUT",
                        },
                    }
                )
            code = self.model3_exporter.build_python_script(
                steps or [{"alg_id": "native:reprojectlayer", "params": {"INPUT": "active_layer", "TARGET_CRS": "EPSG:5253", "OUTPUT": "TEMPORARY_OUTPUT"}}],
                model_name="EPSG5253_Standardization",
            )
            return {"code": code, "steps": steps, "context": ctx}

        if "buffer" in prompt_lower:
            target_id = layers[0]["id"] if layers else "INPUT_LAYER"
            target_name = layers[0]["n"] if layers else "Active Layer"
            steps = [
                {
                    "id": "buffer_step_1",
                    "alg_id": "native:buffer",
                    "description": f"50m Buffer on {target_name} (EPSG:5253)",
                    "params": {
                        "INPUT": target_id,
                        "DISTANCE": 50.0,
                        "SEGMENTS": 8,
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                }
            ]
            code = self.model3_exporter.build_python_script(steps, model_name="LiteAgent_Buffer_Workflow")
            return {"code": code, "steps": steps, "context": ctx}

        # Default read-only inspection snippet
        code_lines = [
            "# Read-Only Workspace Inspection (Safe Auto-Inspect)",
            "proj = QgsProject.instance()",
            "summary = []",
            "for lid, lyr in proj.mapLayers().items():",
            "    summary.append(f\"{lyr.name()} [{lyr.crs().authid()}]\")",
            "result = {'project_crs': proj.crs().authid(), 'layers': summary}",
            "print('Inspected layers:', len(summary))",
        ]
        return {"code": "\n".join(code_lines), "steps": [], "context": ctx}
