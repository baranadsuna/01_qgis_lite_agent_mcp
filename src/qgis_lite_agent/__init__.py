# -*- coding: utf-8 -*-
"""
QGIS Lite Agent & MCP Bridge
Clean-room engineered, ultra-low-token AI agent & MCP loopback plugin for QGIS 3.x and 4.x.

License: GPL-2.0-or-later
"""


def classFactory(iface):
    """Load QgisLiteAgentPlugin class from file lite_agent_plugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .lite_agent_plugin import QgisLiteAgentPlugin

    return QgisLiteAgentPlugin(iface)
