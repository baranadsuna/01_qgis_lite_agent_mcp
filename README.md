# QGIS Lite Agent & MCP Bridge (`qgis_lite_agent`)

**Production & Research Repository**: `02_gelistirilen_eklentiler/qgis_lite_agent`  
**Developer**: Baran Adsuna (`https://github.com/baranadsuna`) — Dokuz Eylül University, Department of Urban and Regional Planning  
**Mandatory CRS Standard**: `EPSG:5253` (TUREF / TM30)  
**QGIS Compatibility**: QGIS 3.22+ to QGIS 4.99 (`supportsQt6=True`, Qt5 & Qt6 compatible)  
**License**: GNU General Public License v2.0 or later (`GPL-2.0-or-later`)

---

## 1. What Is This Plugin? (Overview)

`qgis_lite_agent` is an ultra-lightweight, token-conscious, and strictly secured AI agent assistant and Model Context Protocol (MCP) localhost bridge for QGIS.

It enables modern AI agents (Google Antigravity, Claude Code, Cursor, Codex, OpenCode, Gemini, DeepSeek, Grok, Ollama) to interact with a live QGIS session safely and with minimal token usage, allowing spatial queries, geoprocessing execution, CRS compliance auditing, and 1-click export of agent actions into native QGIS Graphic Modeler (`.model3`) workflow files.

---

## 2. Key Architecture & Engineering Features

1. **Ultra-Low Token Footprint (< 150 Tokens/Turn)**:
   - Serializes opted-in layer schemas into a compact micro-DSL (`compact_context.py`).
   - Uses deterministic **SHA-256 state hashing** (`"delta": "UNCHANGED"`, ~18 tokens) on subsequent turns when layer schemas have not changed, eliminating the 98% prompt token waste common in legacy plugins.
2. **Per-Layer Privacy Selector**:
   - Explicit user opt-in checkboxes for each layer. Unchecked layers are completely invisible to both external MCP agents and LLM providers.
   - Never dumps raw GeoJSON coordinates or geometries into prompt contexts.
3. **3-Tier Python AST Security Sandbox (`security_guard.py`)**:
   - Inspects all PyQGIS snippets via `ast.NodeVisitor` before execution.
   - Classifies code into:
     - `READ_ONLY`: Safe introspection runs automatically on main thread.
     - `WORKSPACE_MUTATION`: Processing or editing steps requiring explicit human approval.
     - `BLOCKED`: Immediately halts dangerous calls (`subprocess`, `os.system`, `shutil.rmtree`, `eval`, `exec`, `socket`, and dunder escapes).
   - Secures loopback JSON-RPC traffic with an ephemeral 128-bit session token (`secrets.token_hex(16)`).
4. **First-Class `EPSG:5253` Governance**:
   - Continuously audits project and layer coordinate systems against `EPSG:5253` (TUREF / TM30).
   - Generates automated reprojection workflows so Euclidean metric calculations (buffers, accessibility) are never run on unprojected degrees.
5. **1-Click Native `.model3` Export (`model3_exporter.py`)**:
   - Compiles agent action chains directly into native QGIS Graphic Modeler files (`.model3`) and standalone Python scripts.
   - **Zero Canvas Bloat**: Rejects bulky custom node canvases (like 02SmartModeler) and relies entirely on QGIS's built-in Processing Modeler.

---

## 3. Directory Layout

```
02_gelistirilen_eklentiler/qgis_lite_agent/
|-- docs_github_io/                       # GitHub Pages methodology & documentation portal
|   |-- assets/                           # Real PyQGIS GUI screenshots
|   |-- index.html                        # Portal web page with KaTeX math
|   `-- METHODOLOGY.md                    # Academic methodology with Crossref DOIs
|-- releases/                             # Packaged .zip releases (max 3 versions)
|   `-- qgis_lite_agent_v1.0.0.zip
|-- src/
|   `-- qgis_lite_agent/                  # Plugin Python package source tree
|       |-- __init__.py
|       |-- metadata.txt                  # QGIS metadata (supportsQt6=True)
|       |-- compat.py                     # Qt5 / Qt6 scoped enum compatibility layer
|       |-- compact_context.py            # Micro-DSL & SHA-256 delta context builder
|       |-- security_guard.py             # AST static analysis sandbox & session token auth
|       |-- mcp_bridge.py                 # Localhost 127.0.0.1 MCP loopback server & 6 tools
|       |-- model3_exporter.py            # QGIS .model3 XML & standalone .py generator
|       |-- lite_agent_dock.py            # Streamlined 3-section English DockWidget
|       |-- lite_agent_plugin.py          # QGIS plugin lifecycle manager
|       `-- icon.svg                      # Vector UI icon
|-- tests/
|   `-- test_lite_agent.py                # Headless PyQGIS automated test suite
|-- ACKNOWLEDGMENTS.md                    # Attribution of conceptual inspirations
|-- THIRD_PARTY_NOTICES.md                # Clean-room synthesis & license notices
|-- REVERSE_ENGINEERING_SYNTHESIS.md      # Deep comparative study of reference plugins
|-- LOW_TOKEN_AND_SECURITY_SPEC.md        # Technical token and security specifications
|-- LICENSE                               # GPL-2.0-or-later
`-- README.md                             # This file
```

---

## 4. Verification & Testing

Run all unit and headless smoke tests using the primary QGIS LTR Python interpreter:

```powershell
& "C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat" 02_gelistirilen_eklentiler/qgis_lite_agent/tests/test_lite_agent.py
```
