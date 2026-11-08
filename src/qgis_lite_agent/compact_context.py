# -*- coding: utf-8 -*-
"""
Ultra-Low Token Compact Context Protocol & EPSG:5253 Governance (`compact_context.py`).

Builds a deterministic, privacy-filtered project digest under 150 tokens for
typical QGIS projects, supports SHA-256 delta state synchronization, and enforces
EPSG:5253 (TUREF / TM30) CRS auditing without hallucinating data.
"""

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional, Set

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeatureRequest,
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)

from .compat import layer_type_code

STANDARD_CRS_AUTHID = "EPSG:5253"

FIELD_TYPE_SHORT_MAP = {
    "Integer": "int",
    "Integer64": "int64",
    "Real": "real",
    "Double": "real",
    "String": "str",
    "Date": "date",
    "DateTime": "dt",
    "Boolean": "bool",
}


def estimate_tokens(payload: Any) -> int:
    """Estimate LLM token count conservatively (~4 characters per token for compact JSON)."""
    if isinstance(payload, str):
        raw = payload
    else:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return max(1, (len(raw) + 3) // 4)


def _short_field_type(type_name: str) -> str:
    """Convert verbose QVariant/QgsField type names to 2-5 char tokens."""
    if not type_name:
        return "any"
    for key, short_val in FIELD_TYPE_SHORT_MAP.items():
        if key.lower() in type_name.lower():
            return short_val
    return type_name[:6].lower()


class CompactContextBuilder:
    """Builds privacy-filtered, ultra-compact workspace snapshots and SHA-256 deltas."""

    def __init__(self, target_crs: str = STANDARD_CRS_AUTHID) -> None:
        self.target_crs: str = target_crs
        self._opted_in_layer_ids: Optional[Set[str]] = None
        self._last_state_hash: str = ""

    @property
    def last_state_hash(self) -> str:
        """Return the SHA-256 prefix hash of the most recently built full context."""
        return self._last_state_hash

    def set_opted_in_layers(self, layer_ids: Optional[Iterable[str]]) -> None:
        """Set explicit layer IDs allowed for agent inspection.

        Pass None to allow all currently loaded project layers, or an empty
        iterable to block all layers (strict privacy mode).
        """
        if layer_ids is None:
            self._opted_in_layer_ids = None
        else:
            self._opted_in_layer_ids = set(layer_ids)

    def get_opted_in_layers(self) -> Optional[Set[str]]:
        """Return the set of opted-in layer IDs, or None if all layers are allowed."""
        return self._opted_in_layer_ids

    def _iter_approved_layers(
        self,
        project: Optional[QgsProject] = None,
        explicit_layer_ids: Optional[Iterable[str]] = None,
    ) -> List[QgsMapLayer]:
        """Return valid QgsMapLayer instances that pass the privacy selector."""
        proj = project or QgsProject.instance()
        all_layers = proj.mapLayers()
        allowed_ids: Optional[Set[str]]
        if explicit_layer_ids is not None:
            allowed_ids = set(explicit_layer_ids)
        else:
            allowed_ids = self._opted_in_layer_ids

        result: List[QgsMapLayer] = []
        for lid in sorted(all_layers.keys()):
            if allowed_ids is not None and lid not in allowed_ids:
                continue
            layer = all_layers[lid]
            if layer is not None:
                result.append(layer)
        return result

    def summarize_layer(
        self,
        layer: QgsMapLayer,
        max_fields: int = 12,
        include_samples: bool = False,
        max_samples: int = 3,
    ) -> Dict[str, Any]:
        """Serialize a single QgsMapLayer into a compact dictionary."""
        if layer is None or not layer.isValid():
            return {
                "id": getattr(layer, "id", lambda: "invalid")(),
                "n": getattr(layer, "name", lambda: "Invalid Layer")(),
                "valid": False,
            }

        crs_authid = layer.crs().authid() if layer.crs().isValid() else "NONE"
        is_5253 = crs_authid.upper() == self.target_crs.upper()
        ltype = layer_type_code(layer)

        ext = layer.extent()
        if ext and not ext.isEmpty():
            extent_arr = [
                round(ext.xMinimum(), 2),
                round(ext.yMinimum(), 2),
                round(ext.xMaximum(), 2),
                round(ext.yMaximum(), 2),
            ]
        else:
            extent_arr = []

        entry: Dict[str, Any] = {
            "id": layer.id(),
            "n": layer.name(),
            "t": ltype,
            "crs": crs_authid,
            "ok5253": is_5253,
        }
        if extent_arr:
            entry["ext"] = extent_arr

        if isinstance(layer, QgsVectorLayer):
            entry["fc"] = int(layer.featureCount())
            entry["sel"] = int(layer.selectedFeatureCount())
            fields = layer.fields()
            field_tokens: List[str] = []
            for idx in range(min(len(fields), max_fields)):
                fld = fields.at(idx)
                field_tokens.append(f"{fld.name()}:{_short_field_type(fld.typeName())}")
            if len(fields) > max_fields:
                field_tokens.append(f"+{len(fields) - max_fields}_more")
            entry["f"] = field_tokens

            if include_samples and entry["fc"] > 0:
                samples: List[Dict[str, Any]] = []
                req = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry).setLimit(max_samples)
                for feat in layer.getFeatures(req):
                    row: Dict[str, Any] = {}
                    for idx in range(min(len(fields), 6)):
                        fname = fields.at(idx).name()
                        val = feat[fname]
                        if val is not None:
                            sval = str(val)
                            row[fname] = sval[:32] if len(sval) > 32 else sval
                    samples.append(row)
                entry["smp"] = samples
        elif isinstance(layer, QgsRasterLayer):
            entry["dim"] = [int(layer.width()), int(layer.height())]
            entry["bands"] = int(layer.bandCount())

        return entry

    def compute_state_hash(self, layers_digest: List[Dict[str, Any]], project_crs: str) -> str:
        """Compute a deterministic 16-hex-character SHA-256 digest of the workspace state."""
        canonical = json.dumps(
            {"p_crs": project_crs, "layers": layers_digest},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def build_compact_context(
        self,
        project: Optional[QgsProject] = None,
        explicit_layer_ids: Optional[Iterable[str]] = None,
        max_fields: int = 12,
        include_samples: bool = False,
    ) -> Dict[str, Any]:
        """Build a full compact workspace context dictionary (<150 tokens for typical projects)."""
        proj = project or QgsProject.instance()
        proj_crs = proj.crs().authid() if proj.crs().isValid() else "NONE"
        approved_layers = self._iter_approved_layers(proj, explicit_layer_ids)

        layers_digest = [
            self.summarize_layer(
                lyr,
                max_fields=max_fields,
                include_samples=include_samples,
            )
            for lyr in approved_layers
        ]

        all_5253 = (proj_crs.upper() == self.target_crs.upper()) and all(
            item.get("ok5253", False) for item in layers_digest if item.get("valid", True)
        )
        state_hash = self.compute_state_hash(layers_digest, proj_crs)
        self._last_state_hash = state_hash

        payload: Dict[str, Any] = {
            "v": 1,
            "p_crs": proj_crs,
            "std_crs": self.target_crs,
            "crs_ok": all_5253,
            "hash": state_hash,
            "layers": layers_digest,
        }
        payload["est_tokens"] = estimate_tokens(payload)
        return payload

    def build_delta_context(
        self,
        previous_hash: Optional[str] = None,
        project: Optional[QgsProject] = None,
        explicit_layer_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Return an ultra-compact UNCHANGED delta (~18 tokens) if state matches previous_hash."""
        full_ctx = self.build_compact_context(
            project=project,
            explicit_layer_ids=explicit_layer_ids,
            include_samples=False,
        )
        current_hash = full_ctx["hash"]
        if previous_hash and previous_hash == current_hash:
            delta_payload: Dict[str, Any] = {
                "v": 1,
                "delta": "UNCHANGED",
                "hash": current_hash,
                "p_crs": full_ctx["p_crs"],
                "crs_ok": full_ctx["crs_ok"],
            }
            delta_payload["est_tokens"] = estimate_tokens(delta_payload)
            return delta_payload

        full_ctx["delta"] = "UPDATED"
        return full_ctx

    def validate_crs_epsg5253(
        self,
        project: Optional[QgsProject] = None,
        explicit_layer_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Audit project and opted-in layers for strict EPSG:5253 (TUREF / TM30) compliance."""
        proj = project or QgsProject.instance()
        proj_crs = proj.crs().authid() if proj.crs().isValid() else "NONE"
        approved_layers = self._iter_approved_layers(proj, explicit_layer_ids)

        non_compliant: List[Dict[str, str]] = []
        compliant_ids: List[str] = []

        for lyr in approved_layers:
            if not lyr.isValid():
                continue
            authid = lyr.crs().authid() if lyr.crs().isValid() else "NONE"
            if authid.upper() == self.target_crs.upper():
                compliant_ids.append(lyr.id())
            else:
                ltype = layer_type_code(lyr)
                recommended_alg = (
                    "native:reprojectlayer" if ltype.startswith("V:") else "gdal:warpreproject"
                )
                non_compliant.append(
                    {
                        "layer_id": lyr.id(),
                        "layer_name": lyr.name(),
                        "current_crs": authid,
                        "target_crs": self.target_crs,
                        "recommended_alg": recommended_alg,
                    }
                )

        project_ok = proj_crs.upper() == self.target_crs.upper()
        return {
            "standard_crs": self.target_crs,
            "project_crs": proj_crs,
            "project_crs_compliant": project_ok,
            "all_layers_compliant": len(non_compliant) == 0,
            "fully_compliant": project_ok and len(non_compliant) == 0,
            "compliant_layer_count": len(compliant_ids),
            "non_compliant_layers": non_compliant,
        }

    def enforce_project_crs_epsg5253(self, project: Optional[QgsProject] = None) -> bool:
        """Set the QgsProject CRS to EPSG:5253 (TUREF / TM30)."""
        proj = project or QgsProject.instance()
        crs = QgsCoordinateReferenceSystem(self.target_crs)
        if not crs.isValid():
            return False
        proj.setCrs(crs)
        return proj.crs().authid().upper() == self.target_crs.upper()

    def inspect_layer_stats(
        self,
        layer_id_or_name: str,
        field_name: Optional[str] = None,
        max_samples: int = 3,
        project: Optional[QgsProject] = None,
    ) -> Dict[str, Any]:
        """Return bounded, real statistics for a single opted-in layer without hallucination."""
        proj = project or QgsProject.instance()
        approved = self._iter_approved_layers(proj)
        target_layer: Optional[QgsMapLayer] = None

        for lyr in approved:
            if lyr.id() == layer_id_or_name or lyr.name() == layer_id_or_name:
                target_layer = lyr
                break

        if target_layer is None:
            return {
                "ok": False,
                "error": f"Layer '{layer_id_or_name}' not found or not opted-in via Privacy Selector.",
            }

        summary = self.summarize_layer(
            target_layer,
            max_fields=25,
            include_samples=True,
            max_samples=min(max(1, max_samples), 5),
        )

        if field_name and isinstance(target_layer, QgsVectorLayer):
            idx = target_layer.fields().indexFromName(field_name)
            if idx < 0:
                summary["field_error"] = f"Field '{field_name}' does not exist in layer '{target_layer.name()}'."
            else:
                non_null = 0
                numeric_vals: List[float] = []
                distinct_preview: Set[str] = set()
                req = (
                    QgsFeatureRequest()
                    .setFlags(QgsFeatureRequest.NoGeometry)
                    .setSubsetOfAttributes([idx])
                    .setLimit(500)
                )
                for feat in target_layer.getFeatures(req):
                    val = feat[idx]
                    if val is not None and str(val) != "NULL":
                        non_null += 1
                        if len(distinct_preview) < 8:
                            distinct_preview.add(str(val)[:24])
                        try:
                            numeric_vals.append(float(val))
                        except (TypeError, ValueError):
                            pass

                fstats: Dict[str, Any] = {
                    "field": field_name,
                    "sampled_non_null": non_null,
                    "distinct_sample": sorted(distinct_preview),
                }
                if numeric_vals:
                    fstats["min"] = round(min(numeric_vals), 4)
                    fstats["max"] = round(max(numeric_vals), 4)
                    fstats["mean"] = round(sum(numeric_vals) / len(numeric_vals), 4)
                summary["field_stats"] = fstats

        summary["ok"] = True
        return summary
