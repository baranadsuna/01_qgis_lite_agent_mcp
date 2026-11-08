# -*- coding: utf-8 -*-
"""
Unit & Headless QGIS Smoke Tests for `qgis_lite_agent` (`tests/test_lite_agent.py`).

Tests:
1. `compact_context.py`: <150-token budget, per-layer privacy selector, SHA-256 delta snapshots,
   `EPSG:5253` compliance auditing, and bounded layer statistics.
2. `security_guard.py`: AST static blocking (`subprocess`, `os.system`, `shutil.rmtree`, `eval`,
   `exec`, `socket`, dunder escapes), `READ_ONLY` vs `WORKSPACE_MUTATION` classification,
   and `127.0.0.1` session token authentication.
3. `model3_exporter.py`: `.model3` XML generation, standalone `.py` script generation, and dry-run
   step validation.
4. `mcp_bridge.py`: 6-tool catalog verification, JSON-RPC 2.0 dispatch, token enforcement,
   and non-blocking `127.0.0.1` loopback TCP socket roundtrip.
5. `lite_agent_dock.py` & `lite_agent_plugin.py`: Headless Qt5/Qt6 GUI instantiation, layer
   privacy refresh, AST dry-run button, and `.model3` file export.
"""

import json
import os
import socket
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PLUGIN_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(PLUGIN_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC_DIR))

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from qgis_lite_agent import classFactory
from qgis_lite_agent.compact_context import CompactContextBuilder, STANDARD_CRS_AUTHID
from qgis_lite_agent.compat import (
    check_state_checked,
    check_state_unchecked,
    is_qt6,
    right_dock_area,
)
from qgis_lite_agent.lite_agent_dock import LiteAgentDockWidget
from qgis_lite_agent.mcp_bridge import COMPACT_TOOL_CATALOG, McpLoopbackBridge
from qgis_lite_agent.model3_exporter import Model3Exporter
from qgis_lite_agent.security_guard import RiskLevel, SecurityGuard

_QGS_APP = None


def setUpModule() -> None:
    global _QGS_APP
    if QgsApplication.instance() is None:
        _QGS_APP = QgsApplication([], True)
        _QGS_APP.initQgis()


def tearDownModule() -> None:
    global _QGS_APP
    if _QGS_APP is not None:
        _QGS_APP.exitQgis()
        _QGS_APP = None


class TestQgisLiteAgentSuite(unittest.TestCase):
    """Comprehensive unit and headless QGIS smoke test suite."""

    def setUp(self) -> None:
        self.project = QgsProject.instance()
        self.project.clear()
        self.project.setCrs(QgsCoordinateReferenceSystem(STANDARD_CRS_AUTHID))

        # Layer 1: Compliant EPSG:5253 Polygon memory layer
        self.lyr_5253 = QgsVectorLayer(
            "Polygon?crs=EPSG:5253&field=parcel_no:integer&field=area_m2:double&field=owner:string(40)",
            "Parcels_5253",
            "memory",
        )
        pr1 = self.lyr_5253.dataProvider()
        feat1 = QgsFeature(self.lyr_5253.fields())
        feat1.setGeometry(
            QgsGeometry.fromPolygonXY(
                [
                    [
                        QgsPointXY(500000, 4420000),
                        QgsPointXY(500100, 4420000),
                        QgsPointXY(500100, 4420100),
                        QgsPointXY(500000, 4420100),
                        QgsPointXY(500000, 4420000),
                    ]
                ]
            )
        )
        feat1.setAttributes([101, 10000.0, "Public_Domain"])
        pr1.addFeatures([feat1])
        self.lyr_5253.updateExtents()

        # Layer 2: Non-compliant EPSG:4326 Point memory layer
        self.lyr_4326 = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=station_id:integer&field=name:string(30)",
            "Stations_4326",
            "memory",
        )
        pr2 = self.lyr_4326.dataProvider()
        feat2 = QgsFeature(self.lyr_4326.fields())
        feat2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(32.85, 39.92)))
        feat2.setAttributes([1, "Ankara_Ref"])
        pr2.addFeatures([feat2])
        self.lyr_4326.updateExtents()

        self.project.addMapLayer(self.lyr_5253)
        self.project.addMapLayer(self.lyr_4326)

    def tearDown(self) -> None:
        self.project.clear()

    # =========================================================================
    # 1. Compact Context, Privacy Filter, Delta Hash & EPSG:5253 Tests
    # =========================================================================
    def test_compact_context_token_budget_and_delta_hash(self) -> None:
        builder = CompactContextBuilder(target_crs="EPSG:5253")
        ctx = builder.build_compact_context(project=self.project)

        self.assertEqual(ctx["p_crs"], "EPSG:5253")
        self.assertEqual(ctx["std_crs"], "EPSG:5253")
        self.assertFalse(ctx["crs_ok"])  # Because Stations_4326 is in EPSG:4326
        self.assertEqual(len(ctx["layers"]), 2)
        self.assertLess(ctx["est_tokens"], 150, "Compact context must stay under 150 tokens!")

        # Verify Delta Snapshot returns UNCHANGED (~18 tokens) when state hash matches
        prev_hash = ctx["hash"]
        delta_ctx = builder.build_delta_context(previous_hash=prev_hash, project=self.project)
        self.assertEqual(delta_ctx["delta"], "UNCHANGED")
        self.assertEqual(delta_ctx["hash"], prev_hash)
        self.assertLess(delta_ctx["est_tokens"], 30)

    def test_layer_privacy_selector_and_epsg5253_audit(self) -> None:
        builder = CompactContextBuilder(target_crs="EPSG:5253")
        # Opt-in ONLY the EPSG:5253 layer; hide the EPSG:4326 layer
        builder.set_opted_in_layers([self.lyr_5253.id()])

        ctx = builder.build_compact_context(project=self.project)
        self.assertEqual(len(ctx["layers"]), 1)
        self.assertEqual(ctx["layers"][0]["n"], "Parcels_5253")
        self.assertTrue(ctx["crs_ok"])

        # Inspect layer stats on opted-in layer vs private layer
        stats_ok = builder.inspect_layer_stats(
            self.lyr_5253.id(), field_name="area_m2", project=self.project
        )
        self.assertTrue(stats_ok["ok"])
        self.assertEqual(stats_ok["field_stats"]["min"], 10000.0)

        stats_blocked = builder.inspect_layer_stats(
            self.lyr_4326.id(), project=self.project
        )
        self.assertFalse(stats_blocked["ok"])

        # Audit all layers for EPSG:5253 compliance
        builder.set_opted_in_layers(None)
        crs_report = builder.validate_crs_epsg5253(project=self.project)
        self.assertTrue(crs_report["project_crs_compliant"])
        self.assertFalse(crs_report["all_layers_compliant"])
        self.assertEqual(len(crs_report["non_compliant_layers"]), 1)
        self.assertEqual(
            crs_report["non_compliant_layers"][0]["recommended_alg"],
            "native:reprojectlayer",
        )

    # =========================================================================
    # 2. Security Guard AST Static Analyzer & Token Tests
    # =========================================================================
    def test_security_guard_ast_blocking_and_classification(self) -> None:
        guard = SecurityGuard(workspace_dir=tempfile.gettempdir())

        # Dangerous snippets that MUST be BLOCKED
        dangerous_snippets = [
            "import subprocess\nsubprocess.Popen(['calc.exe'])",
            "import os\nos.system('whoami')",
            "import shutil\nshutil.rmtree('/')",
            "eval('2 + 2')",
            "exec('import sys')",
            "import socket\ns = socket.socket()",
            "x = ().__class__.__bases__[0].__subclasses__()",
            "f = open('C:/Windows/win.ini', 'r')",
        ]
        for snippet in dangerous_snippets:
            audit = guard.inspect_code(snippet)
            self.assertEqual(
                audit.risk_level,
                RiskLevel.BLOCKED,
                f"Snippet should have been BLOCKED: {snippet}",
            )
            self.assertFalse(audit.allowed_auto)

        # Mutating snippet that MUST be classified as WORKSPACE_MUTATION
        mutating_code = (
            "import processing\n"
            "processing.run('native:buffer', {'INPUT': 'lyr', 'DISTANCE': 10, 'OUTPUT': 'TEMPORARY_OUTPUT'})"
        )
        mut_audit = guard.inspect_code(mutating_code)
        self.assertEqual(mut_audit.risk_level, RiskLevel.WORKSPACE_MUTATION)
        self.assertTrue(mut_audit.requires_approval)
        self.assertFalse(mut_audit.allowed_auto)

        # Calling execute_guarded_pyqgis on mutating code without human_approved=True must halt
        unapproved_res = guard.execute_guarded_pyqgis(mutating_code, human_approved=False)
        self.assertFalse(unapproved_res["ok"])
        self.assertEqual(unapproved_res["status"], "AWAITING_HUMAN_APPROVAL")

        # Read-only snippet that MUST be classified as READ_ONLY and execute safely
        readonly_code = (
            "proj = QgsProject.instance()\n"
            "result = proj.crs().authid()\n"
        )
        ro_audit = guard.inspect_code(readonly_code)
        self.assertEqual(ro_audit.risk_level, RiskLevel.READ_ONLY)
        self.assertTrue(ro_audit.allowed_auto)

        exec_res = guard.execute_guarded_pyqgis(readonly_code, human_approved=False)
        self.assertTrue(exec_res["ok"])
        self.assertEqual(exec_res["result"], "EPSG:5253")

        # Session token verification
        tok = guard.session_token
        self.assertEqual(len(tok), 32)
        self.assertTrue(guard.verify_session_token(tok))
        self.assertFalse(guard.verify_session_token("invalid_token"))

    # =========================================================================
    # 3. Model3 & Standalone Python Exporter Tests
    # =========================================================================
    def test_model3_and_python_exporter(self) -> None:
        exporter = Model3Exporter(default_crs="EPSG:5253")
        steps = [
            {
                "id": "reproject_1",
                "alg_id": "native:reprojectlayer",
                "description": "Reproject input to EPSG:5253",
                "params": {
                    "INPUT": self.lyr_4326.id(),
                    "TARGET_CRS": "EPSG:5253",
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
            },
            {
                "id": "buffer_2",
                "alg_id": "native:buffer",
                "description": "Buffer by 50 meters",
                "params": {
                    "INPUT": "TEMPORARY_OUTPUT",
                    "DISTANCE": 50.0,
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
            },
        ]

        dry_run = exporter.dry_run_validate_steps(steps)
        self.assertTrue(dry_run["ok"])
        self.assertEqual(dry_run["validated_steps"], 2)

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = str(Path(tmpdir) / "test_workflow.model3")
            res_m3 = exporter.export_to_file(steps, model_path, model_name="Test_5253_Chain")
            self.assertTrue(res_m3["ok"])
            self.assertEqual(res_m3["format"], "model3")
            xml_text = Path(res_m3["path"]).read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE model>", xml_text)
            self.assertIn("native:reprojectlayer", xml_text)
            self.assertIn("EPSG:5253", xml_text)

            # Ensure XML body is well-formed
            xml_body = xml_text.split("<!DOCTYPE model>", 1)[1].strip()
            root = ET.fromstring(xml_body)
            self.assertEqual(root.tag, "Option")

            py_path = str(Path(tmpdir) / "test_workflow.py")
            res_py = exporter.export_to_file(steps, py_path, model_name="Test_5253_Chain")
            self.assertTrue(res_py["ok"])
            self.assertEqual(res_py["format"], "py")
            py_text = Path(res_py["path"]).read_text(encoding="utf-8")
            self.assertIn('QgsCoordinateReferenceSystem("EPSG:5253")', py_text)
            self.assertIn("processing.run('native:buffer'", py_text)

    # =========================================================================
    # 4. MCP Bridge 6-Tool Catalog & Localhost Socket Framing Tests
    # =========================================================================
    def test_mcp_bridge_tools_and_socket_loopback(self) -> None:
        self.assertEqual(len(COMPACT_TOOL_CATALOG), 6)
        bridge = McpLoopbackBridge()

        # Reject non-loopback bind attempt
        bad_bind = bridge.start_server(host="0.0.0.0", port=0)
        self.assertFalse(bad_bind["ok"])

        # Start on ephemeral port on 127.0.0.1
        start_info = bridge.start_server(host="127.0.0.1", port=0)
        self.assertTrue(start_info["ok"])
        port = start_info["port"]
        token = start_info["auth_token"]

        try:
            # 1. Unauthorized socket call without token must return -32001 error
            with socket.create_connection(("127.0.0.1", port), timeout=2.0) as cli:
                req_unauth = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
                cli.sendall(req_unauth.encode("utf-8"))
                for _ in range(10):
                    QCoreApplication.processEvents()
                    bridge._poll_socket_events()
                raw_resp = cli.recv(4096).decode("utf-8")
                resp_unauth = json.loads(raw_resp.strip())
                self.assertIn("error", resp_unauth)
                self.assertEqual(resp_unauth["error"]["code"], -32001)

            # 2. Authorized socket call to `get_compact_context`
            with socket.create_connection(("127.0.0.1", port), timeout=2.0) as cli:
                req_ctx = (
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "auth_token": token,
                            "method": "tools/call",
                            "params": {"name": "get_compact_context", "arguments": {}},
                        }
                    )
                    + "\n"
                )
                cli.sendall(req_ctx.encode("utf-8"))
                for _ in range(10):
                    QCoreApplication.processEvents()
                    bridge._poll_socket_events()
                raw_resp2 = cli.recv(16384).decode("utf-8")
                resp_ctx = json.loads(raw_resp2.strip())
                self.assertTrue(resp_ctx["result"]["ok"])
                self.assertEqual(resp_ctx["result"]["data"]["std_crs"], "EPSG:5253")
        finally:
            bridge.stop_server()
            self.assertFalse(bridge.is_running)

    # =========================================================================
    # 5. GUI DockWidget & Plugin Lifecycle Headless Tests
    # =========================================================================
    def test_dock_widget_and_plugin_lifecycle(self) -> None:
        mock_iface = MagicMock()
        mock_iface.mainWindow.return_value = None

        plugin = classFactory(mock_iface)
        plugin.initGui()
        self.assertIsNotNone(plugin.action_toggle_dock)
        plugin.toggle_dock_widget(True)
        self.assertIsNotNone(plugin.dock_widget)

        dock: LiteAgentDockWidget = plugin.dock_widget
        self.assertEqual(dock.layer_list.count(), 2)
        self.assertIn("EPSG:5253", dock.lbl_crs_status.text())

        # Propose a buffer action and verify AST classification in the UI
        dock.txt_prompt.setText("Buffer parcels by 50m in EPSG:5253")
        dock.on_propose_action_clicked()
        audit_dict = dock.on_dry_run_ast_clicked()
        self.assertEqual(audit_dict["risk_level"], RiskLevel.WORKSPACE_MUTATION.value)
        self.assertIn("WORKSPACE_MUTATION", dock.lbl_ast_badge.text())

        # Export proposed steps to .model3 directly
        with tempfile.TemporaryDirectory() as tmpdir:
            out_model = str(Path(tmpdir) / "ui_exported.model3")
            exp_res = dock.on_export_model3_clicked(target_path=out_model)
            self.assertTrue(exp_res["ok"])
            self.assertTrue(Path(out_model).exists())

        plugin.unload()
        self.assertIsNone(plugin.dock_widget)


if __name__ == "__main__":
    unittest.main(verbosity=2)
