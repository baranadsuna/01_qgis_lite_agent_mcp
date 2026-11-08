# -*- coding: utf-8 -*-
"""
Native QGIS `.model3` Workflow & Standalone Python Exporter (`model3_exporter.py`).

Clean-room exporter that converts an agent-proposed sequence of `qgis.processing`
steps into:
1. A valid QGIS Graphic Modeler `.model3` XML file (`<Option type="Map">`), or
2. A clean, reproducible standalone PyQGIS script enforcing `EPSG:5253`.

Includes dry-run algorithm verification against `QgsApplication.processingRegistry()`
without any bloated visual node canvas.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from qgis.core import QgsApplication

from .compact_context import STANDARD_CRS_AUTHID


class Model3Exporter:
    """Validates and exports processing chains to `.model3` XML or standalone `.py` scripts."""

    def __init__(self, default_crs: str = STANDARD_CRS_AUTHID) -> None:
        self.default_crs = default_crs

    def dry_run_validate_steps(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify that every step has a valid structure and (when registry is loaded) a known alg_id."""
        if not isinstance(steps, list) or len(steps) == 0:
            return {
                "ok": False,
                "errors": ["Workflow steps list must be a non-empty list of step dictionaries."],
                "validated_steps": 0,
            }

        registry = QgsApplication.processingRegistry() if QgsApplication.instance() else None
        has_providers = bool(registry and len(registry.providers()) > 0)

        errors: List[str] = []
        warnings: List[str] = []

        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {idx + 1}: Must be a dictionary.")
                continue

            alg_id = str(step.get("alg_id", "")).strip()
            if not alg_id or ":" not in alg_id:
                errors.append(
                    f"Step {idx + 1}: Missing or invalid 'alg_id' (expected 'provider:algorithm', e.g. 'native:buffer')."
                )
                continue

            params = step.get("params", {})
            if not isinstance(params, dict):
                errors.append(f"Step {idx + 1} ('{alg_id}'): 'params' must be a dictionary.")
                continue

            if has_providers and registry is not None:
                alg = registry.algorithmById(alg_id)
                if alg is None:
                    warnings.append(
                        f"Step {idx + 1}: Algorithm '{alg_id}' not found in active Processing Registry."
                    )

        return {
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "validated_steps": len(steps) if len(errors) == 0 else 0,
        }

    def _append_option_scalar(
        self, parent: ET.Element, name: Optional[str], value: Any
    ) -> ET.Element:
        """Append a typed QGIS `<Option>` scalar element to an XML parent."""
        attrib: Dict[str, str] = {}
        if name is not None:
            attrib["name"] = str(name)

        if value is None:
            attrib["type"] = "invalid"
        elif isinstance(value, bool):
            attrib["type"] = "bool"
            attrib["value"] = "true" if value else "false"
        elif isinstance(value, int):
            attrib["type"] = "int"
            attrib["value"] = str(value)
        elif isinstance(value, float):
            attrib["type"] = "double"
            attrib["value"] = str(value)
        else:
            attrib["type"] = "QString"
            attrib["value"] = str(value)

        return ET.SubElement(parent, "Option", attrib)

    def _append_option_value(
        self, parent: ET.Element, name: Optional[str], value: Any
    ) -> ET.Element:
        """Recursively serialize Python dicts/lists/scalars into QGIS `.model3` `<Option>` XML."""
        if isinstance(value, dict):
            attrib = {"type": "Map"}
            if name is not None:
                attrib["name"] = str(name)
            map_el = ET.SubElement(parent, "Option", attrib)
            for k, v in value.items():
                self._append_option_value(map_el, str(k), v)
            return map_el

        if isinstance(value, (list, tuple)):
            attrib = {"type": "List"}
            if name is not None:
                attrib["name"] = str(name)
            list_el = ET.SubElement(parent, "Option", attrib)
            for item in value:
                self._append_option_value(list_el, None, item)
            return list_el

        return self._append_option_scalar(parent, name, value)

    def build_model3_xml(
        self,
        steps: List[Dict[str, Any]],
        model_name: str = "LiteAgent_EPSG5253_Workflow",
        model_group: str = "QGIS Lite Agent",
    ) -> str:
        """Build a native QGIS `.model3` XML string from a sequence of processing steps."""
        root = ET.Element("Option", {"type": "Map"})

        self._append_option_scalar(root, "model_name", model_name)
        self._append_option_scalar(root, "model_group", model_group)
        self._append_option_value(
            root,
            "help",
            {
                "SHORT_DESCRIPTION": f"Generated by QGIS Lite Agent (Standard CRS: {self.default_crs}).",
                "CRS_STANDARD": self.default_crs,
            },
        )
        self._append_option_value(root, "parameterDefinitions", {})
        self._append_option_value(root, "parameters", {})

        children_map: Dict[str, Any] = {}
        for idx, step in enumerate(steps):
            alg_id = str(step.get("alg_id", "native:buffer")).strip()
            step_id = str(step.get("id") or f"{alg_id.replace(':', '_')}_{idx + 1}")
            desc = str(step.get("description") or f"Step {idx + 1}: {alg_id}")
            raw_params = step.get("params", {})

            formatted_params: Dict[str, Any] = {}
            for p_key, p_val in raw_params.items():
                formatted_params[p_key] = [
                    {
                        "source": 2,  # Static value in QgsProcessingModelChildParameterSource
                        "static_value": p_val,
                    }
                ]

            children_map[step_id] = {
                "active": True,
                "alg_id": alg_id,
                "color": "",
                "comment": {"color": "", "component_description": "", "component_height": 60.0, "component_pos_x": 0.0, "component_pos_y": 0.0, "component_width": 100.0, "outputs_collapsed": True, "parameters_collapsed": True},
                "component_description": desc,
                "component_height": 30.0,
                "component_pos_x": float(140 + (idx * 220)),
                "component_pos_y": float(120 + (idx * 90)),
                "component_width": 200.0,
                "dependencies": [steps[idx - 1].get("id", f"{steps[idx - 1].get('alg_id', 'step').replace(':', '_')}_{idx}")] if idx > 0 else [],
                "id": step_id,
                "outputs": {},
                "outputs_collapsed": True,
                "parameters_collapsed": True,
                "params": formatted_params,
            }

        self._append_option_value(root, "children", children_map)

        try:
            ET.indent(root, space="  ")
        except AttributeError:
            pass

        xml_body = ET.tostring(root, encoding="unicode")
        return f'<!DOCTYPE model>\n{xml_body}\n'

    def build_python_script(
        self,
        steps: List[Dict[str, Any]],
        model_name: str = "LiteAgent_EPSG5253_Workflow",
    ) -> str:
        """Build a clean, reproducible standalone PyQGIS Processing script from steps."""
        lines: List[str] = [
            "# -*- coding: utf-8 -*-",
            '"""',
            f"Reproducible PyQGIS Workflow: {model_name}",
            f"Generated by QGIS Lite Agent & MCP Bridge (Target CRS: {self.default_crs})",
            '"""',
            "",
            "from qgis.core import QgsCoordinateReferenceSystem, QgsProject",
            "import processing",
            "",
            "",
            "def run_workflow():",
            f'    target_crs = QgsCoordinateReferenceSystem("{self.default_crs}")',
            "    if target_crs.isValid():",
            "        QgsProject.instance().setCrs(target_crs)",
            "    results = {}",
        ]

        for idx, step in enumerate(steps):
            alg_id = str(step.get("alg_id", "native:buffer")).strip()
            step_key = str(step.get("id") or f"step_{idx + 1}")
            desc = str(step.get("description") or f"Step {idx + 1}: {alg_id}")
            params = step.get("params", {})

            lines.append(f"    # {desc}")
            lines.append(
                f"    results[{step_key!r}] = processing.run({alg_id!r}, {params!r})"
            )

        lines.extend(
            [
                "    return results",
                "",
                "",
                'if __name__ == "__main__":',
                "    run_workflow()",
                "",
            ]
        )
        return "\n".join(lines)

    def export_to_file(
        self,
        steps: List[Dict[str, Any]],
        output_path: str,
        model_name: str = "LiteAgent_EPSG5253_Workflow",
    ) -> Dict[str, Any]:
        """Validate steps and write either a `.model3` or `.py` file to disk."""
        validation = self.dry_run_validate_steps(steps)
        if not validation["ok"]:
            return {
                "ok": False,
                "errors": validation["errors"],
            }

        path_obj = Path(output_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        suffix = path_obj.suffix.lower()

        if suffix == ".py":
            content = self.build_python_script(steps, model_name=model_name)
            fmt = "py"
        else:
            if suffix != ".model3":
                path_obj = path_obj.with_suffix(".model3")
            content = self.build_model3_xml(steps, model_name=model_name)
            fmt = "model3"

        path_obj.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "format": fmt,
            "path": str(path_obj),
            "steps_count": len(steps),
            "warnings": validation.get("warnings", []),
        }
