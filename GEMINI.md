# GEMINI.md — `03_yeni_eklenti_fikirleri_ve_arge/01_qgis_lite_agent_mcp/` (Google Gemini Directives)

> **Plugin Scope**: `c:\Users\lilba\OneDrive\Masaüstü\qgis_plugin\03_yeni_eklenti_fikirleri_ve_arge\01_qgis_lite_agent_mcp\`

---

## 1. Gemini Engineering Directives for `qgis_lite_agent`

1. **Preserve AST Security Guard**: Never bypass `ASTSecurityGuard` when executing PyQGIS snippets received over the localhost MCP/socket bridge.
2. **Ultra-Low Token Budget**: Keep `get_compact_context()` output concise (`< 150` tokens per layer) and deterministic.
3. **`.model3` Export Integrity**: Ensure exported `.model3` files validate cleanly in `QgsProcessingModelAlgorithm` and enforce `EPSG:5253`.
4. **Qt5/Qt6 & English UI**: Use `qgis.PyQt` imports, Qt6-compatible scoped enums, and 100% English UI labels.
5. **Clean-Room Compliance**: Keep `THIRD_PARTY_NOTICES.md` and `ACKNOWLEDGMENTS.md` intact and never copy code from external MCP repositories.
