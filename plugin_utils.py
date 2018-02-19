from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *


def getSridAndGeomType(con, table, geometry):
    args = {}
    args['table'] = table
    args['geometry'] = geometry
    cur = con.cursor()
    cur.execute("""
        SELECT ST_SRID(%(geometry)s), ST_GeometryType(%(geometry)s)
            FROM %(table)s 
            LIMIT 1
    """ % args)
    row = cur.fetchone()
    return row[0], row[1]

def refreshMapCanvas(mapCanvas):
    if QGis.QGIS_VERSION_INT < 20400:
        return mapCanvas.clear()
    else:
        return mapCanvas.refresh()

def logMessage(message, level=QgsMessageLog.INFO):
    QgsMessageLog.logMessage(message, 'ProtezioneCivile', level)

