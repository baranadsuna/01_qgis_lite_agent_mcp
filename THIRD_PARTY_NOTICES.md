# Third-Party Notices & License Compliance

`qgis_lite_agent` (**QGIS Lite Agent & MCP Bridge**) is an original, clean-room engineered QGIS plugin distributed under the **GNU General Public License v2.0 or later (`GPL-2.0-or-later`)**, in full compliance with the official QGIS Plugin Repository requirements and the licensing terms of the QGIS Python API (`PyQGIS`) and `PyQt5`/`PyQt6`.

---

## 1. Statement of Clean-Room Implementation

No source code, classes, functions, or prompt strings from any third-party QGIS plugin were copied or redistributed in `qgis_lite_agent`. All modules (`compat.py`, `compact_context.py`, `security_guard.py`, `mcp_bridge.py`, `model3_exporter.py`, `lite_agent_dock.py`, `lite_agent_plugin.py`) are original implementations written against the official QGIS and Python standard library APIs.

---

## 2. Conceptual Reference Projects & Licenses

During the architectural research phase, the following open-source QGIS plugins were studied for high-level conceptual inspiration and workflow ergonomics:

1. **QGIS MCP Plugin (`qgis_mcp_plugin`)**
   * **Author**: Nicolas Karasiak
   * **Repository**: `https://github.com/nkarasiak/qgis-mcp`
   * **Plugin Page**: `https://plugins.qgis.org/plugins/qgis_mcp_plugin/`
   * **License**: MIT / GPL-2.0-or-later (QGIS Plugin compatibility)
   * **Conceptual Attribution**: Inspired the concept of a non-blocking localhost loopback command socket and runtime expression/health diagnostics.

2. **QGIS Agent MCP (`qgis_agent_mcp`)**
   * **Author**: Aaa2122
   * **Repository**: `https://github.com/Aaa2122/QGIS-MCP`
   * **Plugin Page**: `https://plugins.qgis.org/plugins/qgis_agent_mcp/`
   * **License**: GPL-2.0-or-later
   * **Conceptual Attribution**: Inspired the concept of an adaptive, low-token tool surface, bounded result pagination, and multi-agent local bridge compatibility.

3. **QGIS AI Copilot (`qgis_ai_copilot`)**
   * **Author**: Aidos Nazhmiden
   * **Plugin Page**: `https://plugins.qgis.org/plugins/qgis_ai_copilot/`
   * **License**: GPL-2.0-or-later
   * **Conceptual Attribution**: Inspired the user-controlled per-layer privacy selector, human-in-the-loop code approval workflow, and dependency-free multi-provider LLM adapter pattern.

4. **02SmartModeler - Visual Workflow Builder (`zero2smartmodeler`)**
   * **Author**: Geophilo
   * **Plugin Page**: `https://plugins.qgis.org/plugins/zero2smartmodeler/`
   * **License**: GPL-2.0-or-later
   * **Conceptual Attribution**: Inspired the concept of exporting validated processing chains into native QGIS `.model3` XML/JSON definitions and standalone Python scripts with dry-run algorithm verification.

---

## 3. Runtime Dependencies

`qgis_lite_agent` relies exclusively on components bundled with standard QGIS installations (3.22 LTS through 4.x):
* **QGIS Core / GUI / Processing APIs** (`qgis.core`, `qgis.gui`, `qgis.processing`) — Licensed under `GPL-2.0-or-later`.
* **PyQt5 / PyQt6 Wrapper** (`qgis.PyQt`) — Licensed under `GPL-3.0` / Riverbank Commercial License (bundled via QGIS).
* **Python Standard Library** (`ast`, `hashlib`, `hmac`, `json`, `secrets`, `socket`, ` urllib.request`, `xml.etree.ElementTree`) — Python Software Foundation License (PSFL).
