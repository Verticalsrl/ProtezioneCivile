#Alcuni comandi da lanciare direttamente da console python di QGis per la gestione del Composer e dell'Atlas
#Caso "copertina": la soluzione potrebbe essere invertire l'ordine delle pagine e al secondo giro dire myComposition.setNumPages(1): ma come invertire l'ordine?
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
composerlist = iface.activeComposers()
myComposition = composerlist[0].composition()
printer = QPrinter()
painter = QPainter()
myComposition.shouldExportPage( 1 )
filename_path = "C:/Users/riccardo/Desktop/render"
pagine = myComposition.pages()
copertina = pagine[0]
seconda = pagine[1]
oggetti = myComposition.composerMapItems()
#solo oggetti mappa
for oo in oggetti:
  print oo.displayName() #'Mappa 0'
  print oo.pagePos() #PyQt4.QtCore.QPointF(2.0, 156.969)
  #print oo.PageNumber #8
  print oo.page() #ok!
  if oo.page()==1:
    oo.hide()
#tutti gli oggetti:
all_items = myComposition.items()
for item in all_items:
  print item
  #print item.type()
  if (item.type()==3 or item.type()==65642):
    continue
  elif (item.type()==65639): #QgsComposerLabel
    print item.text()
  else:
    print item.page()
    if item.page()==1:
      item.hide()
#65642 QgsPaperItem
#3 QGraphicsRectItem
#tutti gli altri valori sembrano essere validi
myAtlas.beginRender()
myComposition.setAtlasMode(QgsComposition.ExportAtlas)
for i in range(0, myAtlas.numFeatures()):
  copertina.setExcludeFromExports(True)
  copertina.setVisibility(False)
  copertina.removeItems()
  copertina.update()
  copertina.updateItem()
  myComposition.update()
  myComposition.updateSettings()
  myComposition.renderPage(painter, 1)
  myAtlas.prepareForFeature( i )
  myComposition.beginPrintAsPDF(printer, filename_path)
  myComposition.beginPrint(printer)
  printReady = painter.begin(printer)
  myComposition.doPrint(printer, painter)
myAtlas.endRender()
painter.end()
