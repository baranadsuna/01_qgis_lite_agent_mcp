# Acknowledgments

We gratefully acknowledge the open-source geospatial and AI developer community whose pioneering work on integrating Large Language Models (LLMs), the Model Context Protocol (MCP), and automated workflow generation with QGIS inspired the architectural direction of `qgis_lite_agent`:

* **Nicolas Karasiak** (`qgis_mcp_plugin` — [GitHub](https://github.com/nkarasiak/qgis-mcp) / [QGIS Plugins](https://plugins.qgis.org/plugins/qgis_mcp_plugin/)): For demonstrating the effectiveness of a local loopback socket bridge connecting external MCP clients directly to a live QGIS session, as well as built-in stack health diagnostics.
* **Aaa2122** (`qgis_agent_mcp` — [GitHub](https://github.com/Aaa2122/QGIS-MCP) / [QGIS Plugins](https://plugins.qgis.org/plugins/qgis_agent_mcp/)): For pioneering token-conscious, bounded tool output strategies and broad interoperability with modern coding agents (Antigravity, OpenCode, Codex, Claude Code, Cursor, Gemini, DeepSeek, Grok).
* **Aidos Nazhmiden** (`qgis_ai_copilot` — [QGIS Plugins](https://plugins.qgis.org/plugins/qgis_ai_copilot/)): For emphasizing user data sovereignty via explicit per-layer privacy filtering and human-in-the-loop code review before executing PyQGIS mutations.
* **Geophilo** (`zero2smartmodeler` / `02SmartModeler` — [QGIS Plugins](https://plugins.qgis.org/plugins/zero2smartmodeler/)): For highlighting the value of bridging automated workflow steps into native QGIS `.model3` Graphic Modeler files and reproducible Python scripts.
* **The QGIS Core Development Team & OSGeo Community**: For maintaining `PyQGIS`, the `QgsProcessing` framework, and the seamless `qgis.PyQt` compatibility layer supporting the transition from QGIS 3 (Qt5) to QGIS 4 (Qt6).
