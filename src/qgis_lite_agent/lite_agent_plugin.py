# -*- coding: utf-8 -*-
"""
Main Plugin Lifecycle Class (`lite_agent_plugin.py`).

Manages toolbar actions, menu registration, dock widget creation, and clean
teardown of the localhost MCP loopback bridge on unload.
"""

from pathlib import Path
from typing import Any, Optional

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .compat import right_dock_area
from .lite_agent_dock import LiteAgentDockWidget


class QgisLiteAgentPlugin:
    """QGIS Lite Agent & MCP Bridge main plugin controller."""

    PLUGIN_MENU_NAME = "&QGIS Lite Agent & MCP Bridge"

    def __init__(self, iface: Any) -> None:
        self.iface = iface
        self.plugin_dir = Path(__file__).resolve().parent
        self.action_toggle_dock: Optional[QAction] = None
        self.dock_widget: Optional[LiteAgentDockWidget] = None

    def initGui(self) -> None:
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = str(self.plugin_dir / "icon.svg")
        icon = QIcon(icon_path)

        parent_win = self.iface.mainWindow() if self.iface else None
        self.action_toggle_dock = QAction(
            icon,
            "QGIS Lite Agent & MCP Bridge",
            parent_win,
        )
        self.action_toggle_dock.setCheckable(True)
        self.action_toggle_dock.setStatusTip(
            "Open QGIS Lite Agent (<150-token context, AST Security Sandbox, EPSG:5253, .model3 export)"
        )
        self.action_toggle_dock.triggered.connect(self.toggle_dock_widget)

        if self.iface is not None:
            self.iface.addToolBarIcon(self.action_toggle_dock)
            self.iface.addPluginToMenu(self.PLUGIN_MENU_NAME, self.action_toggle_dock)

    def toggle_dock_widget(self, checked: bool = True) -> None:
        """Show or hide the LiteAgentDockWidget."""
        if self.dock_widget is None:
            parent_win = self.iface.mainWindow() if self.iface else None
            self.dock_widget = LiteAgentDockWidget(iface=self.iface, parent=parent_win)
            self.dock_widget.visibilityChanged.connect(self._on_dock_visibility_changed)
            if self.iface is not None and hasattr(self.iface, "addDockWidget"):
                self.iface.addDockWidget(right_dock_area(), self.dock_widget)

        if self.dock_widget.isVisible() and not checked:
            self.dock_widget.hide()
        else:
            self.dock_widget.show()
            self.dock_widget.raise_()
            self.dock_widget.refresh_layer_privacy_list()

    def _on_dock_visibility_changed(self, visible: bool) -> None:
        if self.action_toggle_dock is not None:
            self.action_toggle_dock.blockSignals(True)
            self.action_toggle_dock.setChecked(visible)
            self.action_toggle_dock.blockSignals(False)

    def unload(self) -> None:
        """Stop the loopback bridge and remove plugin UI elements cleanly."""
        if self.dock_widget is not None:
            try:
                self.dock_widget.mcp_bridge.stop_server()
            except Exception:
                pass
            if self.iface is not None and hasattr(self.iface, "removeDockWidget"):
                self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

        if self.action_toggle_dock is not None and self.iface is not None:
            self.iface.removePluginMenu(self.PLUGIN_MENU_NAME, self.action_toggle_dock)
            self.iface.removeToolBarIcon(self.action_toggle_dock)
            self.action_toggle_dock = None
