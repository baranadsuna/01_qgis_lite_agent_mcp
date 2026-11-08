# CLAUDE.md — `03_yeni_eklenti_fikirleri_ve_arge/01_qgis_lite_agent_mcp/` (Anthropic Claude Directives)

> **Plugin Scope**: `c:\Users\lilba\OneDrive\Masaüstü\qgis_plugin\03_yeni_eklenti_fikirleri_ve_arge\01_qgis_lite_agent_mcp\`

---

## 1. Claude Code Rules for `qgis_lite_agent`

- **Architecture**:
  - Ultra-low-token `QgsProject` context serializer.
  - `ASTSecurityGuard` static AST validator blocking unsafe system/network calls.
  - Localhost (`127.0.0.1`) MCP/JSON socket bridge.
  - `.model3` (`qgismodel3`) workflow exporter enforcing `EPSG:5253` (Rule 4) and No Orphan Analysis (Rule 3).
- **IP Hygiene**: Zero code duplication from external plugins; maintain `THIRD_PARTY_NOTICES.md` and `ACKNOWLEDGMENTS.md`.
- **Runtime**: Test via `& "C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat"`.
