# -*- coding: utf-8 -*-
"""
Minimalist 3-Section English UI DockWidget (`lite_agent_dock.py`).

Designed for clarity, speed, and zero visual bloat:
1. Layer Privacy Selector & EPSG:5253 Governance Bar with Live Token Budget Meter.
2. MCP Loopback Bridge Controller & Multi-Agent Provider Selector.
3. Human-in-the-Loop Action / Code Review Box with `[Dry-Run AST Check]`,
   `[Approve & Run]`, and `[Export .model3]`.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QClipboard
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsProject

from .compact_context import CompactContextBuilder, STANDARD_CRS_AUTHID
from .compat import (
    check_state_checked,
    check_state_unchecked,
    item_flags_checkable_enabled,
    layer_type_code,
    user_role,
)
from .mcp_bridge import McpLoopbackBridge, SUPPORTED_PROVIDERS
from .model3_exporter import Model3Exporter
from .security_guard import RiskLevel, SecurityGuard


class LiteAgentDockWidget(QDockWidget):
    """Streamlined 3-section dock widget for QGIS Lite Agent & MCP Bridge."""

    def __init__(
        self,
        iface: Any = None,
        parent: Optional[QWidget] = None,
        context_builder: Optional[CompactContextBuilder] = None,
        security_guard: Optional[SecurityGuard] = None,
        model3_exporter: Optional[Model3Exporter] = None,
        mcp_bridge: Optional[McpLoopbackBridge] = None,
    ) -> None:
        super().__init__("QGIS Lite Agent & MCP Bridge", parent)
        self.setObjectName("QgisLiteAgentDockWidget")

        self.iface = iface
        self.context_builder = context_builder or CompactContextBuilder(
            target_crs=STANDARD_CRS_AUTHID
        )
        self.security_guard = security_guard or SecurityGuard()
        self.model3_exporter = model3_exporter or Model3Exporter(
            default_crs=STANDARD_CRS_AUTHID
        )
        self.mcp_bridge = mcp_bridge or McpLoopbackBridge(
            context_builder=self.context_builder,
            security_guard=self.security_guard,
            model3_exporter=self.model3_exporter,
            iface=self.iface,
            parent=self,
        )

        self._current_steps: List[Dict[str, Any]] = []
        self._build_ui()
        self._connect_signals()
        self.refresh_layer_privacy_list()

    def _build_ui(self) -> None:
        container = QWidget(self)
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # =====================================================================
        # SECTION 1: Layer Privacy Selector, EPSG:5253 Status & Token Meter
        # =====================================================================
        sec1_group = QGroupBox("1. Layer Privacy & EPSG:5253 Context Governance", container)
        sec1_layout = QVBoxLayout(sec1_group)
        sec1_layout.setContentsMargins(6, 6, 6, 6)
        sec1_layout.setSpacing(4)

        status_row = QHBoxLayout()
        self.lbl_crs_status = QLabel("CRS: Checking EPSG:5253...", sec1_group)
        self.lbl_crs_status.setToolTip(
            "Displays whether the project and opted-in layers comply with EPSG:5253 (TUREF / TM30)."
        )
        self.lbl_token_meter = QLabel("Context Budget: 0 / 150 tokens", sec1_group)
        self.lbl_token_meter.setToolTip(
            "Estimated prompt token footprint of the compact layer digest."
        )
        status_row.addWidget(self.lbl_crs_status, 1)
        status_row.addWidget(self.lbl_token_meter, 0)
        sec1_layout.addLayout(status_row)

        self.layer_list = QListWidget(sec1_group)
        self.layer_list.setMaximumHeight(95)
        self.layer_list.setToolTip(
            "Tick only the layers you allow the AI agent to inspect (Privacy Selector)."
        )
        sec1_layout.addWidget(self.layer_list)

        sec1_btn_row = QHBoxLayout()
        self.btn_refresh_layers = QPushButton("Refresh Layers", sec1_group)
        self.btn_enforce_5253 = QPushButton("Enforce EPSG:5253", sec1_group)
        self.btn_enforce_5253.setToolTip(
            "Set project CRS to EPSG:5253 (TUREF / TM30) and generate reprojection steps for non-compliant layers."
        )
        sec1_btn_row.addWidget(self.btn_refresh_layers)
        sec1_btn_row.addWidget(self.btn_enforce_5253)
        sec1_layout.addLayout(sec1_btn_row)

        root_layout.addWidget(sec1_group)

        # =====================================================================
        # SECTION 2: MCP Loopback Bridge Control & Provider Selector
        # =====================================================================
        sec2_group = QGroupBox("2. Agent Provider & Localhost MCP Bridge", container)
        sec2_layout = QVBoxLayout(sec2_group)
        sec2_layout.setContentsMargins(6, 6, 6, 6)
        sec2_layout.setSpacing(4)

        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Provider:", sec2_group))
        self.cmb_provider = QComboBox(sec2_group)
        for prov in SUPPORTED_PROVIDERS:
            self.cmb_provider.addItem(prov)
        prov_row.addWidget(self.cmb_provider, 1)
        sec2_layout.addLayout(prov_row)

        bridge_row = QHBoxLayout()
        bridge_row.addWidget(QLabel("127.0.0.1 Port:", sec2_group))
        self.spin_port = QSpinBox(sec2_group)
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(9876)
        self.btn_toggle_bridge = QPushButton("Start MCP Bridge", sec2_group)
        self.btn_copy_token = QPushButton("Copy Token", sec2_group)
        self.btn_copy_token.setToolTip(
            "Copy the ephemeral 128-bit localhost session token to clipboard."
        )
        bridge_row.addWidget(self.spin_port)
        bridge_row.addWidget(self.btn_toggle_bridge)
        bridge_row.addWidget(self.btn_copy_token)
        sec2_layout.addLayout(bridge_row)

        prompt_row = QHBoxLayout()
        self.txt_prompt = QLineEdit(sec2_group)
        self.txt_prompt.setPlaceholderText(
            "Ask agent (e.g., 'Audit EPSG:5253 and buffer parcels by 50m')..."
        )
        self.btn_propose = QPushButton("Propose Action", sec2_group)
        prompt_row.addWidget(self.txt_prompt, 1)
        prompt_row.addWidget(self.btn_propose)
        sec2_layout.addLayout(prompt_row)

        root_layout.addWidget(sec2_group)

        # =====================================================================
        # SECTION 3: Human-in-the-Loop Action / Code Review Box
        # =====================================================================
        sec3_group = QGroupBox("3. Human-in-the-Loop Action & Code Review", container)
        sec3_layout = QVBoxLayout(sec3_group)
        sec3_layout.setContentsMargins(6, 6, 6, 6)
        sec3_layout.setSpacing(4)

        self.lbl_ast_badge = QLabel("AST Security Status: Ready (Awaiting Action)", sec3_group)
        sec3_layout.addWidget(self.lbl_ast_badge)

        self.txt_code_review = QPlainTextEdit(sec3_group)
        self.txt_code_review.setPlaceholderText(
            "# Proposed PyQGIS snippet or processing workflow will appear here for review before execution..."
        )
        self.txt_code_review.setMinimumHeight(110)
        sec3_layout.addWidget(self.txt_code_review)

        action_row = QHBoxLayout()
        self.btn_dry_run_ast = QPushButton("Dry-Run AST Check", sec3_group)
        self.btn_approve_run = QPushButton("Approve & Run", sec3_group)
        self.btn_export_model3 = QPushButton("Export .model3", sec3_group)
        action_row.addWidget(self.btn_dry_run_ast)
        action_row.addWidget(self.btn_approve_run)
        action_row.addWidget(self.btn_export_model3)
        sec3_layout.addLayout(action_row)

        self.lbl_output_status = QLabel("Status: Idle.", sec3_group)
        self.lbl_output_status.setWordWrap(True)
        sec3_layout.addWidget(self.lbl_output_status)

        root_layout.addWidget(sec3_group)
        self.setWidget(container)

    def _connect_signals(self) -> None:
        self.btn_refresh_layers.clicked.connect(self.refresh_layer_privacy_list)
        self.btn_enforce_5253.clicked.connect(self.on_enforce_epsg5253_clicked)
        self.layer_list.itemChanged.connect(self._on_layer_check_changed)

        self.btn_toggle_bridge.clicked.connect(self.on_toggle_bridge_clicked)
        self.btn_copy_token.clicked.connect(self.on_copy_token_clicked)
        self.btn_propose.clicked.connect(self.on_propose_action_clicked)
        self.txt_prompt.returnPressed.connect(self.on_propose_action_clicked)

        self.btn_dry_run_ast.clicked.connect(self.on_dry_run_ast_clicked)
        self.btn_approve_run.clicked.connect(self.on_approve_and_run_clicked)
        self.btn_export_model3.clicked.connect(self.on_export_model3_clicked)

        self.mcp_bridge.pending_action_queued.connect(self._on_pending_bridge_action)
        self.mcp_bridge.status_changed.connect(self._on_bridge_status_changed)

    def refresh_layer_privacy_list(self) -> None:
        """Populate the per-layer privacy selector from QgsProject.instance()."""
        existing_opted = self.context_builder.get_opted_in_layers()
        self.layer_list.blockSignals(True)
        self.layer_list.clear()

        proj = QgsProject.instance()
        for lid, lyr in sorted(proj.mapLayers().items()):
            if lyr is None:
                continue
            crs_str = lyr.crs().authid() if lyr.crs().isValid() else "NO_CRS"
            ltype = layer_type_code(lyr)
            item = QListWidgetItem(f"{lyr.name()} [{ltype} | {crs_str}]")
            item.setFlags(item_flags_checkable_enabled())
            item.setData(user_role(), lid)
            is_checked = True if existing_opted is None else (lid in existing_opted)
            item.setCheckState(
                check_state_checked() if is_checked else check_state_unchecked()
            )
            self.layer_list.addItem(item)

        self.layer_list.blockSignals(False)
        self._sync_privacy_selection_and_metrics()

    def _on_layer_check_changed(self, _item: QListWidgetItem) -> None:
        self._sync_privacy_selection_and_metrics()

    def _sync_privacy_selection_and_metrics(self) -> None:
        """Update CompactContextBuilder with checked layer IDs and refresh token & CRS badges."""
        selected_ids: List[str] = []
        checked_enum = check_state_checked()
        role = user_role()
        for idx in range(self.layer_list.count()):
            item = self.layer_list.item(idx)
            if item is not None and item.checkState() == checked_enum:
                lid = item.data(role)
                if lid:
                    selected_ids.append(str(lid))

        self.context_builder.set_opted_in_layers(selected_ids)
        ctx = self.context_builder.build_compact_context()
        est_tokens = ctx.get("est_tokens", 0)
        crs_ok = ctx.get("crs_ok", False)
        p_crs = ctx.get("p_crs", "NONE")

        if crs_ok:
            self.lbl_crs_status.setText(f"CRS: {p_crs} (EPSG:5253 Compliant)")
        else:
            self.lbl_crs_status.setText(f"CRS Warning: Project={p_crs} (Target: EPSG:5253)")

        self.lbl_token_meter.setText(
            f"Context Budget: ~{est_tokens} / 150 tokens [#{ctx.get('hash', '')[:6]}]"
        )

    def on_enforce_epsg5253_clicked(self) -> None:
        """Enforce EPSG:5253 on the project and queue reprojection steps for any non-5253 layers."""
        ok = self.context_builder.enforce_project_crs_epsg5253()
        proposal = self.mcp_bridge.synthesize_local_action_proposal("reproject to EPSG:5253")
        self._current_steps = proposal.get("steps", [])
        self.txt_code_review.setPlainText(proposal.get("code", ""))
        self.refresh_layer_privacy_list()
        self.on_dry_run_ast_clicked()
        if ok:
            self.lbl_output_status.setText(
                "Status: Project CRS set to EPSG:5253. Review reprojection script above."
            )
        else:
            self.lbl_output_status.setText("Status: Could not set EPSG:5253 on project.")

    def on_toggle_bridge_clicked(self) -> None:
        """Start or stop the 127.0.0.1 loopback MCP server."""
        if self.mcp_bridge.is_running:
            self.mcp_bridge.stop_server()
        else:
            port = int(self.spin_port.value())
            res = self.mcp_bridge.start_server(host="127.0.0.1", port=port)
            if not res.get("ok"):
                self.lbl_output_status.setText(f"Bridge Error: {res.get('error')}")

    def _on_bridge_status_changed(self, running: bool, message: str) -> None:
        if running:
            self.btn_toggle_bridge.setText("Stop MCP Bridge")
            self.lbl_output_status.setText(f"Bridge Active: {message}")
        else:
            self.btn_toggle_bridge.setText("Start MCP Bridge")
            self.lbl_output_status.setText(f"Bridge: {message}")

    def on_copy_token_clicked(self) -> None:
        """Copy the ephemeral localhost session token to the system clipboard."""
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(self.security_guard.session_token, QClipboard.Clipboard)
        self.lbl_output_status.setText(
            f"Status: Session token ({self.security_guard.session_token[:8]}...) copied to clipboard."
        )

    def on_propose_action_clicked(self) -> None:
        """Synthesize an inspectable PyQGIS snippet & workflow steps from the prompt."""
        prompt = self.txt_prompt.text().strip()
        proposal = self.mcp_bridge.synthesize_local_action_proposal(prompt)
        self._current_steps = proposal.get("steps", [])
        self.txt_code_review.setPlainText(proposal.get("code", ""))
        self.on_dry_run_ast_clicked()
        self.lbl_output_status.setText(
            "Status: Action proposed. Inspect code and click 'Approve & Run' or 'Export .model3'."
        )

    def _on_pending_bridge_action(self, pending: Dict[str, Any]) -> None:
        """Populate the review box when an external MCP client queues a mutating action."""
        if pending.get("type") == "processing":
            step = {
                "alg_id": pending.get("alg_id", "native:buffer"),
                "params": pending.get("params", {}),
            }
            self._current_steps = [step]
            code = self.model3_exporter.build_python_script(self._current_steps)
            self.txt_code_review.setPlainText(code)
        else:
            self._current_steps = []
            self.txt_code_review.setPlainText(str(pending.get("code", "")))
        self.on_dry_run_ast_clicked()
        self.lbl_output_status.setText(
            "Status: External MCP client queued an action awaiting your approval."
        )

    def on_dry_run_ast_clicked(self) -> Dict[str, Any]:
        """Run the AST static analyzer on the code currently in the Review Box."""
        code = self.txt_code_review.toPlainText()
        audit = self.security_guard.inspect_code(code)
        reason_str = "; ".join(audit.reasons) if audit.reasons else "OK"

        if audit.risk_level == RiskLevel.BLOCKED:
            self.lbl_ast_badge.setText(f"AST Security Status: BLOCKED ({reason_str})")
            self.btn_approve_run.setEnabled(False)
        elif audit.risk_level == RiskLevel.WORKSPACE_MUTATION:
            self.lbl_ast_badge.setText(
                f"AST Security Status: WORKSPACE_MUTATION (Requires Approval — {len(audit.detected_mutations)} call(s))"
            )
            self.btn_approve_run.setEnabled(True)
        else:
            self.lbl_ast_badge.setText("AST Security Status: READ_ONLY (Safe Inspection)")
            self.btn_approve_run.setEnabled(True)

        return audit.to_dict()

    def on_approve_and_run_clicked(self) -> Dict[str, Any]:
        """Execute the reviewed PyQGIS code with explicit Human-in-the-Loop approval."""
        code = self.txt_code_review.toPlainText()
        res = self.security_guard.execute_guarded_pyqgis(
            code=code,
            iface=self.iface,
            human_approved=True,
        )
        if res.get("ok"):
            out_preview = res.get("stdout") or str(res.get("result") or "Completed")
            self.lbl_output_status.setText(f"Execution Succeeded: {out_preview[:140]}")
            self.refresh_layer_privacy_list()
        else:
            self.lbl_output_status.setText(
                f"Execution Halted [{res.get('status')}]: {res.get('error')}"
            )
        return res

    def on_export_model3_clicked(self, target_path: Optional[str] = None) -> Dict[str, Any]:
        """Export the current processing steps to a `.model3` or `.py` file."""
        steps = list(self._current_steps)
        if not steps:
            steps = [
                {
                    "id": "reproject_epsg5253",
                    "alg_id": "native:reprojectlayer",
                    "description": "Standardize Layer CRS to EPSG:5253 (TUREF / TM30)",
                    "params": {
                        "INPUT": "active_layer",
                        "TARGET_CRS": STANDARD_CRS_AUTHID,
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                }
            ]

        if not target_path:
            default_file = str(Path(tempfile.gettempdir()) / "lite_agent_workflow.model3")
            chosen, _ = QFileDialog.getSaveFileName(
                self,
                "Export QGIS Workflow (.model3 or .py)",
                default_file,
                "QGIS Processing Model (*.model3);;Standalone PyQGIS Script (*.py)",
            )
            if not chosen:
                return {"ok": False, "cancelled": True}
            target_path = chosen

        export_res = self.model3_exporter.export_to_file(
            steps=steps,
            output_path=target_path,
            model_name="LiteAgent_EPSG5253_Workflow",
        )
        if export_res.get("ok"):
            self.lbl_output_status.setText(
                f"Exported {export_res.get('format')} workflow to: {export_res.get('path')}"
            )
        else:
            self.lbl_output_status.setText(
                f"Export Error: {'; '.join(export_res.get('errors', []))}"
            )
        return export_res
