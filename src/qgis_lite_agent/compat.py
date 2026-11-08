# -*- coding: utf-8 -*-
"""
Qt5 / Qt6 and QGIS 3.x / 4.x Compatibility Layer (`compat.py`).

Provides unified enum resolvers and execution helpers so `qgis_lite_agent`
runs identically under QGIS 3.22+ (PyQt5) and QGIS 4.x (PyQt6).
"""

from typing import Any
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal, QObject, QT_VERSION_STR
from qgis.core import Qgis, QgsMapLayer, QgsWkbTypes


def is_qt6() -> bool:
    """Return True when running under Qt6 / PyQt6."""
    return QT_VERSION_STR.startswith("6.")


def resolve_qt_enum(scoped_namespace: str, enum_name: str, fallback_attr: str = "") -> Any:
    """Resolve a Qt enum safely across both Qt6 scoped enums and Qt5 flat enums.

    Example:
        resolve_qt_enum("DockWidgetArea", "RightDockWidgetArea")
    """
    namespace_obj = getattr(Qt, scoped_namespace, None)
    if namespace_obj is not None and hasattr(namespace_obj, enum_name):
        return getattr(namespace_obj, enum_name)
    flat_name = fallback_attr or enum_name
    return getattr(Qt, flat_name)


def right_dock_area() -> Any:
    """Return Qt RightDockWidgetArea compatible with Qt5 and Qt6."""
    return resolve_qt_enum("DockWidgetArea", "RightDockWidgetArea")


def left_dock_area() -> Any:
    """Return Qt LeftDockWidgetArea compatible with Qt5 and Qt6."""
    return resolve_qt_enum("DockWidgetArea", "LeftDockWidgetArea")


def check_state_checked() -> Any:
    """Return Qt Checked state compatible with Qt5 and Qt6."""
    return resolve_qt_enum("CheckState", "Checked")


def check_state_unchecked() -> Any:
    """Return Qt Unchecked state compatible with Qt5 and Qt6."""
    return resolve_qt_enum("CheckState", "Unchecked")


def user_role() -> Any:
    """Return Qt UserRole compatible with Qt5 and Qt6."""
    return resolve_qt_enum("ItemDataRole", "UserRole")


def item_flags_checkable_enabled() -> Any:
    """Return combined ItemFlags for an enabled, user-checkable, selectable list item."""
    enabled = resolve_qt_enum("ItemFlag", "ItemIsEnabled")
    checkable = resolve_qt_enum("ItemFlag", "ItemIsUserCheckable")
    selectable = resolve_qt_enum("ItemFlag", "ItemIsSelectable")
    return enabled | checkable | selectable


def orientation_horizontal() -> Any:
    """Return Qt Horizontal orientation compatible with Qt5 and Qt6."""
    return resolve_qt_enum("Orientation", "Horizontal")


def orientation_vertical() -> Any:
    """Return Qt Vertical orientation compatible with Qt5 and Qt6."""
    return resolve_qt_enum("Orientation", "Vertical")


def exec_dialog(widget: Any) -> int:
    """Execute a QDialog or QMenu using `.exec()` (Qt6 / modern Qt5) or `.exec_()` fallback."""
    if hasattr(widget, "exec"):
        return widget.exec()
    return widget.exec_()


def message_level_info() -> Any:
    """Return Qgis.MessageLevel.Info across QGIS 3 and QGIS 4."""
    if hasattr(Qgis, "MessageLevel") and hasattr(Qgis.MessageLevel, "Info"):
        return Qgis.MessageLevel.Info
    return getattr(Qgis, "Info", 0)


def message_level_warning() -> Any:
    """Return Qgis.MessageLevel.Warning across QGIS 3 and QGIS 4."""
    if hasattr(Qgis, "MessageLevel") and hasattr(Qgis.MessageLevel, "Warning"):
        return Qgis.MessageLevel.Warning
    return getattr(Qgis, "Warning", 1)


def message_level_critical() -> Any:
    """Return Qgis.MessageLevel.Critical across QGIS 3 and QGIS 4."""
    if hasattr(Qgis, "MessageLevel") and hasattr(Qgis.MessageLevel, "Critical"):
        return Qgis.MessageLevel.Critical
    return getattr(Qgis, "Critical", 2)


def message_level_success() -> Any:
    """Return Qgis.MessageLevel.Success across QGIS 3 and QGIS 4."""
    if hasattr(Qgis, "MessageLevel") and hasattr(Qgis.MessageLevel, "Success"):
        return Qgis.MessageLevel.Success
    return getattr(Qgis, "Success", 3)


def layer_type_code(layer: QgsMapLayer) -> str:
    """Return a compact, deterministic layer type code ('V:<Geom>' or 'R' or 'O')."""
    if layer is None:
        return "UNKNOWN"

    ltype = layer.type()
    vector_type = getattr(QgsMapLayer, "VectorLayer", None)
    if hasattr(Qgis, "LayerType") and hasattr(Qgis.LayerType, "Vector"):
        is_vector = ltype == Qgis.LayerType.Vector or ltype == vector_type
    else:
        is_vector = ltype == vector_type

    raster_type = getattr(QgsMapLayer, "RasterLayer", None)
    if hasattr(Qgis, "LayerType") and hasattr(Qgis.LayerType, "Raster"):
        is_raster = ltype == Qgis.LayerType.Raster or ltype == raster_type
    else:
        is_raster = ltype == raster_type

    if is_vector and hasattr(layer, "wkbType"):
        try:
            geom_display = QgsWkbTypes.displayString(layer.wkbType())
            if not geom_display:
                geom_display = "Geometry"
        except Exception:
            geom_display = "Vector"
        return f"V:{geom_display}"
    if is_raster:
        return "R:Raster"
    return "O:Other"


__all__ = [
    "Qt",
    "QTimer",
    "pyqtSignal",
    "QObject",
    "QT_VERSION_STR",
    "is_qt6",
    "resolve_qt_enum",
    "right_dock_area",
    "left_dock_area",
    "check_state_checked",
    "check_state_unchecked",
    "user_role",
    "item_flags_checkable_enabled",
    "orientation_horizontal",
    "orientation_vertical",
    "exec_dialog",
    "message_level_info",
    "message_level_warning",
    "message_level_critical",
    "message_level_success",
    "layer_type_code",
]
