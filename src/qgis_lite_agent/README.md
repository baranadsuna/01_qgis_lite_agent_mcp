# QGIS Lite Agent & MCP Bridge (`qgis_lite_agent`)

**QGIS Lite Agent & MCP Bridge** is a clean-room engineered, lightweight AI agent assistant and Model Context Protocol (MCP) localhost bridge for **QGIS 3.22+ (Qt5)** and **QGIS 4.x (Qt6)**.

---

## Key Highlights

1. **Ultra-Low Token Context (`< 150 Tokens`)**:
   * Serializes only user-approved layers into a compact micro-DSL digest (`compact_context.py`).
   * Uses deterministic **SHA-256 Delta Snapshots** (`"delta": "UNCHANGED"`, ~18 tokens) on subsequent turns when workspace state has not changed.
2. **Per-Layer Privacy Selector**:
   * Explicit opt-in checkboxes per layer. Unchecked layers are invisible to both local MCP clients and LLM providers.
   * Never dumps raw GeoJSON geometries into prompts.
3. **3-Tier AST Security Sandbox & Ephemeral Loopback Auth (`security_guard.py`)**:
   * Inspects all PyQGIS snippets via `ast.NodeVisitor` before execution.
   * Classifies actions into `READ_ONLY` (safe auto-inspect), `WORKSPACE_MUTATION` (requires Human-in-the-Loop approval), or `BLOCKED` (`subprocess`, `os.system`, `shutil`, `socket`, `eval`, `exec`, dunder escapes).
   * Binds strictly to `127.0.0.1` with a 128-bit cryptographic session token (`secrets.token_hex(16)`).
4. **First-Class `EPSG:5253` (TUREF / TM30) Governance**:
   * Continuously audits project and layer CRS against `EPSG:5253` and provides 1-click standardization and reprojection workflow generation.
5. **1-Click Native `.model3` & Reproducible Python Export (`model3_exporter.py`)**:
   * Exports agent-proposed processing chains directly into native QGIS Graphic Modeler `.model3` XML files or standalone `.py` scripts—without any bloated custom node canvas.
6. **Multi-Agent & Multi-Provider Compatibility**:
   * Exposes 6 multiplexed JSON-RPC 2.0 / MCP tools over `127.0.0.1` for **Antigravity**, **Claude Code**, **Cursor**, **Codex**, **OpenCode**, **Gemini**, **DeepSeek**, **Grok**, and **Ollama**.

---

## The 6 Multiplexed MCP Tools

| Tool Name | Risk Class | Description |
| :--- | :--- | :--- |
| `get_compact_context` | `READ_ONLY` | Returns `<150`-token layer digest or SHA-256 `UNCHANGED` delta. |
| `inspect_layer_stats` | `READ_ONLY` | Returns bounded real attribute statistics and up to 3 truncated sample rows. |
| `validate_crs_epsg5253` | `READ_ONLY` / `MUTATION` | Audits project and layers against `EPSG:5253` (TUREF / TM30). |
| `run_processing_alg` | `WORKSPACE_MUTATION` | Validates and runs/queues a `qgis.processing` algorithm. |
| `export_model3` | `READ_ONLY` / `EXPORT` | Compiles processing steps into a native `.model3` XML or `.py` script. |
| `execute_guarded_pyqgis` | `AST_CLASSIFIED` | Runs AST-checked PyQGIS code (`READ_ONLY` or human-approved `WORKSPACE_MUTATION`). |

---

## Installation

1. Copy or symlink the `src/qgis_lite_agent` folder into your QGIS Python plugins directory:
   * **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\qgis_lite_agent`
2. Enable **QGIS Lite Agent & MCP Bridge** in **Plugins -> Manage and Install Plugins**.

---

## License

Distributed under the **GNU General Public License v2.0 or later (`GPL-2.0-or-later`)**. See [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md), and [ACKNOWLEDGMENTS.md](../../ACKNOWLEDGMENTS.md).
