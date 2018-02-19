# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ProtezioneCivile
                                 A QGIS plugin
 ProtezioneCivile
                             -------------------
        begin                : 2016-10-17
        copyright            : (C) 2016 by ar_gaeta@yahoo.it
        email                : ar_gaeta@yahoo.it
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ProtezioneCivile class from file ProtezioneCivile.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .ProtezioneCivile import ProtezioneCivile
    return ProtezioneCivile(iface)
