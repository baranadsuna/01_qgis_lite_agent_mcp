# Architectural Reverse-Engineering Synthesis: `qgis_lite_agent`

## 1. Executive Summary

`qgis_lite_agent` (**QGIS Lite Agent & MCP Bridge**) is a clean-room engineered QGIS plugin designed for **ultra-low token consumption**, **strict AST and loopback security**, **QGIS 3.x & 4.x (Qt5/Qt6) dual compatibility**, and **minimalist human-in-the-loop ergonomics**.

Rather than duplicating code from existing plugins, we conducted an architectural analysis of four leading AI/Workflow QGIS plugins on the official QGIS Plugin Repository to identify their strongest architectural patterns as well as their structural weaknesses (such as context bloat, unguarded `exec()`, or overcrowded visual node canvases).

---

## 2. Comparative Matrix of Reference Plugins vs. `qgis_lite_agent`

| Dimension | `qgis_mcp_plugin` (N. Karasiak) | `qgis_agent_mcp` (Aaa2122) | `qgis_ai_copilot` (A. Nazhmiden) | `zero2smartmodeler` (Geophilo) | `qgis_lite_agent` (Ours - Clean-Room) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Paradigm** | Local TCP Bridge + MCP Server | Adaptive Local Agent Bridge | Dockable Multi-LLM Chat Copilot | Visual Node Canvas + `.model3` Export | **Hybrid Loopback MCP Bridge + Minimalist Copilot Dock + `.model3` Export** |
| **Tool Surface & Token Overhead** | High (~118 granular tools exposed in prompt context; heavy schema token cost) | Low/Adaptive (compact tool definitions, bounded output pagination) | Medium (full system prompt + layer metadata JSON per message) | N/A (GUI-driven) | **Ultra-Low (< 150 tokens/turn via 6 multiplexed tools + SHA-256 Delta Digest)** |
| **Layer Privacy Control** | Full project exposed by default | Guarded project inspection | Explicit per-layer checkbox selector | N/A | **Per-Layer Opt-In Privacy Selector + Zero Raw Geometry Dumping** |
| **Code Execution Safety** | Direct execution on loopback | Guarded tool calls | Human-in-the-loop "Run Code" approval | Dry-run workflow validation | **3-Tier AST Static Sandbox (`READ_ONLY`, `WORKSPACE_MUTATION`, `BLOCKED`) + Ephemeral Token + Human Approval** |
| **Reproducibility / Export** | Ephemeral session actions | Ephemeral tool calls | Chat history + code snippets | Native `.model3` & Python script export | **1-Click Export of Agent Action Chains to Native `.model3` or Standalone `.py`** |
| **UI Complexity** | Minimal toggle + health check | Minimal bridge controller | Clean dockable chat + provider tabs | Heavy visual canvas + 21 showcase templates | **Streamlined 3-Section English Dock (No Canvas Bloat)** |
| **CRS Governance** | Generic CRS handling | Generic CRS handling | Generic CRS handling | Generic CRS handling | **First-Class `EPSG:5253` (TUREF / TM30) Audit & 1-Click Reprojection** |
| **Qt5 / Qt6 Compatibility** | Qt5/Qt6 | Qt5/Qt6 | Qt5/Qt6 | Qt5/Qt6 | **Strict `compat.py` Scoped Enum Shim (`qgisMinimumVersion=3.22`, `qgisMaximumVersion=4.99`, `supportsQt6=True`)** |

---

## 3. Clean-Room Synthesis: What We Adopted vs. What We Rejected

### 3.1 From `qgis_mcp_plugin` (Author: Nicolas Karasiak)
* **Conceptual Strengths Adopted (Clean-Room)**:
  * **Length-Prefixed Non-Blocking Loopback Framing**: Using a lightweight `127.0.0.1` loopback socket integrated with `QTimer` / Qt event loop polling so the QGIS main GUI thread never freezes while waiting for external MCP clients (Antigravity, Claude Code, Cursor, Codex).
  * **Stack Health & Expression Pre-Validation**: Verifying `QgsExpression` syntax and `qgis.processing` availability before attempting execution.
* **Weaknesses Avoided**:
  * Exposing 100+ individual tool schemas in the initial MCP handshake consumes thousands of prompt tokens before the user even asks a question. Instead, `qgis_lite_agent` consolidates all operations into **6 multiplexed, strongly-typed core tools**.

### 3.2 From `qgis_agent_mcp` (Author: Aaa2122)
* **Conceptual Strengths Adopted (Clean-Room)**:
  * **Compact & Bounded Tool Responses**: Returning paginated field summaries and bounded feature samples (max 3 rows, truncated strings) instead of raw GeoJSON feature collections.
  * **Incremental State Synchronization**: Only transmitting workspace changes (deltas) rather than repeating unchanged layer schemas on every turn.
  * **Universal Agent Compatibility**: Designing the bridge protocol so any local coding agent or LLM CLI (Antigravity, OpenCode, Codex, Claude Code, Cursor, Gemini, DeepSeek, Grok) can interact via standard JSON-RPC 2.0.

### 3.3 From `qgis_ai_copilot` (Author: Aidos Nazhmiden)
* **Conceptual Strengths Adopted (Clean-Room)**:
  * **Layer-Level Privacy Selector**: Giving the GIS analyst explicit checkboxes to control which layers are visible to the AI context. Unchecked layers are completely invisible to the compact context builder.
  * **Human-in-the-Loop Action Review**: Presenting any mutating PyQGIS script or processing chain in an inspectable review pane where the user must click **Approve & Run** (while allowing safe, read-only metadata checks to run seamlessly).
  * **Zero-Dependency HTTP Client**: Supporting direct API calls (Gemini, Claude, OpenAI, DeepSeek, Grok, Ollama) using Python's standard library (`urllib.request`) or `QgsNetworkAccessManager` with zero brittle binary pip dependencies (`pydantic-core`, `grpcio`, etc.).

### 3.4 From `zero2smartmodeler` / `02SmartModeler` (Author: Geophilo)
* **Conceptual Strengths Adopted (Clean-Room)**:
  * **Agent-to-`.model3` Compiler**: Translating an AI-proposed sequence of `qgis.processing` steps directly into a native QGIS Graphic Modeler file (`.model3`) or a clean, reproducible standalone Python script.
  * **Pre-Execution Dry-Run Check**: Verifying algorithm IDs (`QgsApplication.processingRegistry().algorithmById(...)`) and parameter keys before running the chain.
* **Weaknesses Strictly Avoided**:
  * **Zero Visual Canvas Bloat**: Per strict product requirements, `qgis_lite_agent` completely rejects the heavy custom node-graph editor and 21 pre-bundled showcase templates of `02SmartModeler`. QGIS already ships with the native Processing Modeler; duplicating a complex canvas inside an AI plugin adds thousands of lines of UI maintenance debt and slows down the user workflow.

---

## 4. Clean-Room Engineering Guarantee

All source files inside `src/qgis_lite_agent/` were written from scratch based strictly on public QGIS C++/Python API documentation (`QgsProject`, `QgsVectorLayer`, `QgsRasterLayer`, `QgsProcessingAlgorithm`, `QgsCoordinateReferenceSystem`) and Python standard library modules (`ast`, `hashlib`, `secrets`, `socket`, `json`, `xml.etree.ElementTree`). No source code blocks, UI `.ui` files, or prompt templates were copied from any third-party repository.
