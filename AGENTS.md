# AGENTS.md — `03_yeni_eklenti_fikirleri_ve_arge/01_qgis_lite_agent_mcp/` (QGIS Lite Agent & MCP Bridge)

> **Plugin Scope**: `c:\Users\lilba\OneDrive\Masaüstü\qgis_plugin\03_yeni_eklenti_fikirleri_ve_arge\01_qgis_lite_agent_mcp\`
> **Plugin Package**: `qgis_lite_agent` (QGIS 3.22–4.99, Qt5 & Qt6 Compatible, 100% English UI)

---

## 1. Domain Architecture & Security Invariants

`qgis_lite_agent` is a clean-room, ultra-low-token AI & Model Context Protocol (MCP) assistant and `.model3` workflow generator for QGIS:

1. **Ultra-Low Token Context Serializer**:
   - Compresses active `QgsProject` state into a minimal JSON digest (`crs`, `layer_count`, and per-layer `id`, `name`, `type`, `crs`, `feature_count`, `fields` up to a compact cap) consuming `< 150` tokens per layer.
   - Strictly forbids serializing raw vertex coordinates or full attribute tables into LLM prompts.
2. **AST Security Guard (`ASTSecurityGuard`)**:
   - Every Python snippet or expression submitted through the localhost bridge or interactive console is parsed with Python's `ast.parse()` before execution.
   - Blocks dangerous imports (`subprocess`, `shutil`, `socket`, `ctypes`, `winreg`, `requests`, `urllib`) and destructive builtins/calls (`eval`, `exec`, `compile`, `__import__`, `open` in write/delete modes, `os.system`, `os.popen`, `os.remove`, `os.unlink`, `os.rmdir`).
3. **Localhost-Only Non-Blocking Socket / MCP Bridge**:
   - Binds exclusively to `127.0.0.1` (localhost) on a configurable port (default `9876`) using `QTcpServer` or non-blocking loopback sockets integrated with the Qt event loop so the QGIS GUI never freezes.
   - Exposes structured JSON-RPC / MCP-compatible actions: `ping`, `get_compact_context`, `validate_crs_epsg5253`, `run_processing_step`, `export_model3`, and `execute_safe_pyqgis`.
4. **Native `.model3` (`QgsProcessingModelAlgorithm`) Export**:
   - Converts multi-step spatial analysis chains directly into valid QGIS Graphical Modeler `.model3` XML/JSON files (`qgismodel3`) so researchers can inspect, modify, and re-run workflows deterministically without an AI connection (Rule 5: Individual Responsibility).
5. **Zero Code Duplication & Clean-Room Attribution**:
   - 100% original clean-room implementation. Maintains `THIRD_PARTY_NOTICES.md` and `ACKNOWLEDGMENTS.md` inside the folder.

---

## 2. Immutable Academic & Ethical Rules ("Değişmez Akademik ve Etik Kurallar")

1. **Sıfır Halüsinasyon (Zero Hallucination)**: Yapay zekâya uydurma veri, hayali istatistik veya sentetik katman ürettirilemez.
2. **Gerçek DOI Zorunluluğu (Real DOI Requirement)**: Every academic reference in generated reports or model metadata must be verified with `05_araclar_ve_rehberler/doi_dogrula.py --doi <DOI>`.
3. **Öksüz Analiz Yok (No Orphan Analysis)**: Every `.model3` processing node must connect to a synthesis output or document its exclusion reason.
4. **Koordinat Sistemi (CRS Standard)**: Enforces **EPSG:5253** (TUREF / TM30) across all project layers and `.model3` outputs.
5. **Bireysel Sorumluluk (Individual Responsibility)**: Researchers review and approve every processing parameter and `.model3` graph.

---

## 3. Workstation & Verification Commands

- **Developer**: Baran Adsuna (`https://github.com/baranadsuna`, Dokuz Eylül University, Urban & Regional Planning)
- **Workstation**: Windows 11 Pro, Intel Core i7-13620H, RTX 4050 (`6141 MiB`), `16 GB` RAM.
- **Verification**:
  ```powershell
  & "C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat" 04_test_ve_dogrulama_laboratuvari/run_all_tests.py
  ```
