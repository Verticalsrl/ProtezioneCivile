# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ProtezioneCivile
                                 A QGIS plugin
 ProtezioneCivile
                              -------------------
        begin                : 2016-10-17
        git sha              : $Format:%H$
        copyright            : (C) 2016 by ar_gaeta@yahoo.it
        email                : ar_gaeta@yahoo.it
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

'''

#Ottimizzazioni:
- prelevare la lista dei layer "destinazione" da un file? Quali complicazioni potrebbe avere? Primo: il percorso del file quale sarebbe? All'interno dello stesso file andrebbero anche salvate le info da estrarre dai vari layer, se lo si vuole rendere veramente flessibile. Vedi funzione "fai_intersezione" e "ecco_la_intersezione"
- il layer temporaneo crearlo con lo SRID del progetto!
- creare un resoconto su html: forse segui http://stackoverflow.com/questions/30735665/displaying-a-temporary-html-file-with-webbrowser-in-python
e questo: https://pymotw.com/2/tempfile/
- restituire meglio il risultato a video sui cittadini intercettati
- forse la finestra di dialogo che dice che l'esportazione e'/non e' avvenuta dovrebbe apparire quando tutto il ciclo e' finito...
- ATTENZIONE perche' in alcuni casi congelo lo SRID a 23032!!!

-->vedi mail Andrea 9 marzo:
- controlla tasto INFO crasha? Mi pare di no...

'''


#from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
#from PyQt4.QtGui import QAction, QIcon
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
#from qgis.utils import *
import qgis.utils as qgis_utils

import plugin_utils as Utils

import webbrowser

# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from ProtezioneCivile_dialog import ProtezioneCivileDialog
import os.path

#importo DockWidget
from ProtezioneCivileDock_dockwidget import ProtezioneCivileDockDockWidget
from ProtezioneCivile_help_dockwidget import ProtezioneCivileHelpDockWidget

class ProtezioneCivile:
    """QGIS Plugin Implementation."""

    #Modificare SOLO la SECONDA voce e non la PRIMA che rappresenta l'indice di questo dictionary:
    LAYER_NAME = {
        'CIVICI': 'civici',
        'FERROVIA': 'ferrovia',
        'STRADE': 'strade',
        'FABBRICATI': 'Fabbricati',
        'V_LAC': 'v_lac_anagrafe'
    }
    
    PLUGIN_PATH = os.path.dirname(os.path.abspath(__file__))
    CSV_PATH = os.getenv("HOME") + '/residenti_intercettati.csv'
    
    def __init__(self, iface):
        """Constructor.
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ProtezioneCivile_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = ProtezioneCivileDialog()
        self.dlg_help = ProtezioneCivileHelpDockWidget()
        
        #Apro un link esterno per l'help:
        help_button = QDialogButtonBox.Help #16777216
        Utils.logMessage('help'+str(help_button))
        self.dlg_help.help_btn.clicked.connect(self.help_open)
                
        #Definisco alcune variabili globali:
        global filename
        filename = None
        
        #Aggiungo DockWidget
        self.pluginIsActive = False
        self.dockwidget = None
        
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ProtezioneCivile')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'ProtezioneCivile')
        self.toolbar.setObjectName(u'ProtezioneCivile')
        
        
    #--------------------------------------------------------------------------
    
    def select_output_file(self):
        filename = QFileDialog.getSaveFileName(self.dockwidget, "Salva il risultato", self.CSV_PATH, '*.csv')
        self.dockwidget.fileBrowse_txt.setText(filename)
        #Ridefinisco la variabile CSV_PATH:
        global CSV_PATH
        if filename:
            self.CSV_PATH = filename
        else:
            self.CSV_PATH = os.getenv("HOME") + '/residenti_intercettati.csv'
            
    def select_output_file_dlg(self):
        filename = QFileDialog.getSaveFileName(self.dlg, "Salva il risultato", self.CSV_PATH, '*.csv')
        self.dlg.fileBrowse_txt.setText(filename)
        #Ridefinisco la variabile CSV_PATH:
        global CSV_PATH
        if filename:
            self.CSV_PATH = filename
        else:
            self.CSV_PATH = os.getenv("HOME") + '/residenti_intercettati.csv'
    
    def write_output_lac_file(self, uk_civici_intersected):
        #Seleziono i cittadini in base ai civici selezionati - in questo caso si sta agendo su una TABELLA che non ha FEATURES! Quindi bisogna inventarsi un altro modo per recuperare le righe che ci servono.
        #Cicliamo dentro TUTTI gli elementi e vediamo quali di questi ha l'fk_civico che ci serve:
        info_cittadino_dict = dict()
        header_list = ['codice_fiscale', 'cognome', 'nome', 'sesso', 'data_nascita', 'indirizzo', 'codice_famiglia']
        #Per coerenza seleziono comunque i record cosi' mi restano evidenti anche in tabella di QGis:
        uk_civici_intersected_str = '\',\''.join(uk_civici_intersected)
        cittadini_query_string = u'"fk_civico" IN (\'%s\')' % ( str(uk_civici_intersected_str.decode('utf-8')) )
        #Utils.logMessage("UK_civici totali: " + cittadini_query_string)
        select_expression = QgsExpression( cittadini_query_string )
        select_cittadini = VLACANAG_layer.getFeatures( QgsFeatureRequest( select_expression ) )
        #Build a list of feature Ids from the result obtained:
        ids_selected = [i.id() for i in select_cittadini]
        #Select features with the ids obtained in 3.:
        VLACANAG_layer.removeSelection() #ripulisco eventuali selezioni precedenti
        VLACANAG_layer.setSelectedFeatures( ids_selected )
        #Adesso ciclo dentro TUTTI gli elementi di VLACANAG_layer e recupero le info che mi servono.
        #Sembrerebbe anche buona la variabile select_cittadini, ma per qualche motivo non contiene le stesse info che ciclando direttamente dentro tutto il layer...
        for j_cit in VLACANAG_layer.getFeatures():
            fk=j_cit['fk_civico']
            if ( fk in uk_civici_intersected):
                codice_fiscale = j_cit['codice_fiscale']
                #Utils.logMessage("codice_fiscale: " + str(codice_fiscale))
                cognome = j_cit['cognome']
                nome = j_cit['nome']
                sesso = j_cit['sesso']
                data_nascita = j_cit['data_nascita']
                indirizzo = "%s %s %s" % (j_cit['strada_specie'], j_cit['strada'], j_cit['numero'] )
                codice_famiglia = j_cit['codice_famiglia']
                cit_list = [codice_fiscale, cognome, nome, sesso, data_nascita, indirizzo, codice_famiglia]
                info_cittadino_dict[j_cit['PK_UID']] = cit_list
        
        #Utils.logMessage("Cittadini: " + str(info_cittadino_dict))
        
        #Scrivo il risultato in un CSV:
        import csv
        righe_valori_dict = ''
        try:
            with open(self.CSV_PATH, 'wb') as csv_file:
                writer = csv.writer(csv_file, delimiter='\t')
                Utils.logMessage("1-Scrivo il CSV in " + self.CSV_PATH)
                writer.writerow(header_list)
                for key, value in info_cittadino_dict.items():
                    #writer.writerow([key, str(value).decode('utf-8')])
                    #writer.writerow(str(value).encode('utf-8')) #cosi' separa tutte le lettere..!
                    righe_valori_dict += str(value).decode('utf-8') + '\n'
                    writer.writerow(value)
        except NameError as err:
            msg = QMessageBox()
            msg.setText("Qualche problema nell'esportare il risultato in csv. Contattare l'amministratore.")
            msg.setDetailedText(err.args[0])
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Errore!")
            msg.setStandardButtons(QMessageBox.Ok)
            retval = msg.exec_()
            return 0
        else:
            msg = QMessageBox()
            if (str(righe_valori_dict)):
                msg.setText("Risultati esportati con successo in " + self.CSV_PATH)
                msg.setDetailedText(str(righe_valori_dict))
                msg.setWindowTitle("Esportazione riuscita!")
            else:
                msg.setText("Nessun cittadino intercettato, niente da esportare.")
                msg.setWindowTitle("Niente da esportare...")
            msg.setIcon(QMessageBox.Information)                
            msg.setStandardButtons(QMessageBox.Ok)
            retval = msg.exec_()
            return 1
    
    def help_open(self):
        url = "http://vertical-srl.it/"
        webbrowser.open(url, new=0, autoraise=True)
        
    def seleziona(self):
        #Recupero la stringa del filtro completa del campo:
        if not(layer_da_filtrare):
            return 0
        cod_com_da_filtrare = self.dlg.combo_layer.currentText()
        field_da_filtrare = self.dlg.combo_fields.currentText() #nome e tipo della via
        civico_da_filtrare = self.dlg.combo_civici.currentText()
        
        #Interrogo il layer secondo questi 4 dati: cod_comu, nome, tipo ed eventuale civico:
        if (civico_da_filtrare != default_civico and civico_da_filtrare != ''):
          query_string = u'"cod_comu" = \'%s\' AND "nome" || \' (\'  ||   "tipo"  || \')\' = \'%s\' AND "civico" = \'%s\'' % (str(cod_com_da_filtrare), str(field_da_filtrare.replace("'", r"\'")), str(civico_da_filtrare))
        else:
          query_string = u'"cod_comu" = \'%s\' AND "nome" || \' (\'  ||   "tipo"  || \')\' = \'%s\'' % (str(cod_com_da_filtrare), str(field_da_filtrare.replace("'", r"\'")))
        Utils.logMessage("Filtro completo: " + query_string)
        select_expression = QgsExpression( query_string )
        test_select = layer_da_filtrare.getFeatures( QgsFeatureRequest( select_expression ) )
        #Build a list of feature Ids from the result obtained:
        ids_selected = [i.id() for i in test_select]
        #Select features with the ids obtained in 3.:
        layer_da_filtrare.removeSelection() #ripulisco eventuali selezioni precedenti
        layer_da_filtrare.setSelectedFeatures( ids_selected )
        layer_ids_selezionate = layer_da_filtrare.selectedFeaturesIds()
        layer_feature_selezionate = layer_da_filtrare.selectedFeatures()
        uk_civici = set()
        for j_ids in layer_feature_selezionate:
            recupera_valore_campo = j_ids['uk_civici']
            uk_civici.add(recupera_valore_campo)
        #Preparo l'area su cui zoommare:
        box = layer_da_filtrare.boundingBoxOfSelected()
        MAP_CANVAS.setExtent(box)
        MAP_CANVAS.refresh()
        counted_selected = layer_da_filtrare.selectedFeatureCount()
        self.dlg.filter_txt.setText("Selezionati " + str(counted_selected) + " civici")
        #self.dlg.filter_txt.setPlainText(str(uk_civici))
        
        #layer_da_filtrare.removeSelection() #ripulisco la selezione - commento perche' la voglio
        
        #Proviamo a richiamare la funzione per aggiungere un elemento al layer:
        self.iface.setActiveLayer(CIVICI_layer)
        # Find the layer to edit
        layer = qgis_utils.iface.activeLayer()
        layer.startEditing()
        # Implement the Add Feature button
        qgis_utils.iface.actionAddFeature().trigger()
        #E poi qualcosa del tipo:
        layer.commitChanges() # Commit changes, ma devi lanciarlo da un pulsante...
        
    def inizializza_comuni(self):
        global CIVICI_layer
        global VLACANAG_layer
        try:
            CIVICI_layer = QgsMapLayerRegistry.instance().mapLayersByName(self.LAYER_NAME['CIVICI'])[0]
            Utils.logMessage("Layer Civici: " + CIVICI_layer.name())
            VLACANAG_layer = QgsMapLayerRegistry.instance().mapLayersByName(self.LAYER_NAME['V_LAC'])[0]
        except:
            msg = QMessageBox()
            msg.setText("Caricare sul progetto i layer CIVICI e LAC e nominarli '%s' e '%s' rispettivamente!" % (self.LAYER_NAME['CIVICI'], self.LAYER_NAME['V_LAC']))
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Layer mancanti")
            msg.setStandardButtons(QMessageBox.Ok)
            retval = msg.exec_()
            return 0
        
        global MAP_CANVAS
        MAP_CANVAS = self.iface.mapCanvas()
        
        #Recupero valori univoci del campo cod_comu:
        cod_comu = set()
        #for feature in CIVICI_layer.getFeatures():
        #    cod_comu.add(feature['cod_comu'])
        #Oppure:
        idx_cod_com = CIVICI_layer.fieldNameIndex('cod_comu')
        cod_comu = CIVICI_layer.uniqueValues( idx_cod_com )
    
        #Popolo la prima combo per la scelta del comune:
        global default_comune
        default_comune = '--Scegli un comune--'
        self.dlg.combo_layer.addItem(default_comune) #prima opzione non valida
        for comune in cod_comu:
            self.dlg.combo_layer.addItem(comune)
        #Seleziono la prima opzione:
        #idx_comune = self.dlg.combo_layer.findText(default_comune)
        #self.dlg.combo_layer.setCurrentIndex(idx_comune)
        idx_comune = self.dlg.combo_layer.findText(cod_comu[0])
        self.dlg.combo_layer.setCurrentIndex(idx_comune)
        self.updateFromSelection_comune()
        
    def inizializza_layer_origine(self, combo_da_popolare):
        global CIVICI_layer
        global VLACANAG_layer
        #global STRADE_layer
        #STRADE_layer = QgsMapLayerRegistry.instance().mapLayersByName(self.LAYER_NAME['STRADE'])[0]
        global FABBRICATI_layer
        try:
            CIVICI_layer = QgsMapLayerRegistry.instance().mapLayersByName(self.LAYER_NAME['CIVICI'])[0]
            VLACANAG_layer = QgsMapLayerRegistry.instance().mapLayersByName(self.LAYER_NAME['V_LAC'])[0]
            FABBRICATI_layer = QgsMapLayerRegistry.instance().mapLayersByName(self.LAYER_NAME['FABBRICATI'])[0]
        except:
            msg = QMessageBox()
            msg.setText("Caricare sul progetto i layer CIVICI, LAC e FABBRICATI e nominarli '%s', '%s' e '%s' rispettivamente!" % (self.LAYER_NAME['CIVICI'], self.LAYER_NAME['V_LAC'], self.LAYER_NAME['FABBRICATI']))
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Layer mancanti")
            msg.setStandardButtons(QMessageBox.Ok)
            retval = msg.exec_()
            return 0
            
        #global FERROVIA_layer
        #FERROVIA_layer = QgsMapLayerRegistry.instance().mapLayersByName(self.LAYER_NAME['FERROVIA'])[0]
        
        legend = self.iface.legendInterface()
        layers_caricati = legend.layers()
        Utils.logMessage("Primo layer: " + layers_caricati[0].name())
        
        #Dobbiamo ciclare dentro i layer per popolare il combobox.
        global default_text
        default_text = '--Scegli un layer--'
        combo_da_popolare.addItem(default_text) #prima opzione non valida
        for layer in layers_caricati:
            #Se raster pero lo esonero, non avendo campi su cui filtrare:
            if (layer.type() == 0): #non ho trovato la decodifica. Per ragionamento induttivo pare sia 0-vector; 1-raster;
                #Per escludere dei layer:
                #if not (layer.name() in [ self.LAYER_NAME['FERROVIA'], self.LAYER_NAME['CIVICI'], self.LAYER_NAME['V_LAC'], self.LAYER_NAME['STRADE'], self.LAYER_NAME['FABBRICATI'] ]):
                #oppure includo solo quelli con un certo nome:
                if (layer.name().find('int_')>=0):
                    combo_da_popolare.addItem(layer.name())
        #Seleziono la prima opzione:
        idx = combo_da_popolare.findText(default_text)
        combo_da_popolare.setCurrentIndex(idx)
    
    def inizializza_layer_destinazione(self, combo_da_popolare):
        #in realta questa combo la toglierei e farei la intersezione su tutti i layer destinazione ch servono..
        combo_da_popolare.addItem('civici')
        combo_da_popolare.setEnabled(False)
    
    def inizializza_layer(self, combo_da_popolare):
        legend = self.iface.legendInterface()
        layers_caricati = legend.layers()
        Utils.logMessage("Primo layer: " + layers_caricati[0].name())
        #Altro metodo:
        #registry = QgsMapLayerRegistry.instance()
        #layers_loaded = registry.mapLayers().values()
        #Utils.logMessage("First layer: " + layers_loaded[0].name())
        #O ancora:
        #layers_canvas = self.iface.mapCanvas().layers()
        #Utils.logMessage("First layer canvas: " + layers_canvas[0].name())
        #Per definire un layer specifico:
        #custom_layer = QgsMapLayerRegistry.instance().mapLayersByName('<nome_layer_in_legenda>')[0]
        
        #In ogni caso dobbiamo ciclare dentro i layer per popolare il combobox.
        global default_text
        default_text = '--Scegli un layer--'
        combo_da_popolare.addItem(default_text) #prima opzione non valida
        for layer in layers_caricati:
            #Se raster pero lo esonero, non avendo campi su cui filtrare:
            if (layer.type() == 0): #non ho trovato la decodifica. Per ragionamento induttivo pare sia 0-vector; 1-raster;
                combo_da_popolare.addItem(layer.name())
        #Seleziono la prima opzione:
        idx = combo_da_popolare.findText(default_text)
        combo_da_popolare.setCurrentIndex(idx)
            
        
    def updateFromSelection_comune(self):
        global layer_da_filtrare
        layer_da_filtrare = CIVICI_layer
        cod_com_da_filtrare = self.dlg.combo_layer.currentText()
        if (cod_com_da_filtrare != default_comune and cod_com_da_filtrare != ''):
            self.dlg.combo_fields.setEnabled(True)
            Utils.logMessage("COD_COM da filtrare: " + cod_com_da_filtrare)
            #Recupero valori univoci del campo nome con il cod_comu selezionato:
            nome_via = set()
            for feature in CIVICI_layer.getFeatures():
                if (feature['cod_comu'] == cod_com_da_filtrare):
                    nome_e_tipo = feature['nome'] + " (" + feature['tipo'] + ")"
                    nome_via.add(nome_e_tipo)
                    
            #Popolo il menu a tendina ma prima lo svuoto:
            self.dlg.combo_fields.clear()
            for field_name in sorted(nome_via):
                self.dlg.combo_fields.addItem(field_name)
            
            '''
            layer_da_filtrare = QgsMapLayerRegistry.instance().mapLayersByName(layername_da_filtrare)[0]
            #Recupero i campi del layer:
            #fields = layer_da_filtrare.pendingFields() #alias di fields()
            fields_only = layer_da_filtrare.fields()   
            field_names_only = [field.name() for field in fields_only]
            Utils.logMessage("Campi: " + str(field_names_only))
            #Popolo il menu a tendina ma prima lo svuoto:
            self.dlg.combo_fields.clear()
            self.dlg.atlas_ckbox.setChecked(False) #svuoto anche l'opzione per l'Atlas
            for field_name in field_names_only:
                self.dlg.combo_fields.addItem(field_name)
            '''
            #Attivo e popolo la combo dei civici nel caso:
            self.dlg.combo_civici.setEnabled(True)
            self.get_field_type()
            #Attivo il tasto finale:
            self.dlg.search_btn.setEnabled(True)
        else:
            self.dlg.combo_fields.setEnabled(False)
            self.dlg.combo_civici.setEnabled(False)
            self.dlg.search_btn.setEnabled(False)
    
    def updateFromSelection_layers(self):
        global layer_da_filtrare
        layer_da_filtrare = None
        layername_da_filtrare = self.dockwidget.combo_layer.currentText()
        if (layername_da_filtrare != default_text and layername_da_filtrare != ''):
            #self.dockwidget.combo_fields.setEnabled(True)
            Utils.logMessage("Layer da filtrare: " + layername_da_filtrare)
            layer_da_filtrare = QgsMapLayerRegistry.instance().mapLayersByName(layername_da_filtrare)[0]
            #Recupero i campi del layer:
            #fields = layer_da_filtrare.pendingFields() #alias di fields()
            fields_only = layer_da_filtrare.fields()   
            field_names_only = [field.name() for field in fields_only]
            Utils.logMessage("Campi: " + str(field_names_only))
            #Popolo il menu a tendina ma prima lo svuoto:
            #self.dockwidget.combo_fields.clear()
            #self.dockwidget.atlas_ckbox.setChecked(False) #svuoto anche l'opzione per l'Atlas
            #for field_name in field_names_only:
            #    self.dockwidget.combo_fields.addItem(field_name)
            #Attivo il tasto finale:
            self.dockwidget.select_btn.setEnabled(True)
            self.dockwidget.select_feature.setEnabled(True)
        else:
            #self.dockwidget.combo_fields.setEnabled(False)
            self.dockwidget.select_btn.setEnabled(False)
            self.dockwidget.select_feature.setEnabled(False)
            
    def select_layer_exist(self): #seleziono in mappa il layer scelto dall'utente
        layer_origine_str = self.dockwidget.combo_layer.currentText()
        if (layer_origine_str == default_text):
            msg = QMessageBox()
            msg.setText("Prima di effettuare o confermare una selezione occorre selezionare un layer di origine dal menu a tendina!")
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Scegli un layer di origine!")
            msg.setStandardButtons(QMessageBox.Ok)
            retval = msg.exec_()
            return 0
        self.iface.setActiveLayer(layer_da_filtrare)
        # Find the layer to edit
        layer_attivo = qgis_utils.iface.activeLayer()
        # Implement the Add Feature button
        qgis_utils.iface.actionSelect().trigger()
        #per i vari metodi vedere: https://qgis.org/api/classQgisInterface.html

    def check_layer_virtuale(self, nome_layer):
        try:
            check_layer_virtuale = QgsMapLayerRegistry.instance().mapLayersByName(nome_layer)[0]
        except:
            return 1 #il layer non esiste quindi va
        else: #il layer esiste gia'
            msg = QMessageBox()
            if (check_layer_virtuale): #cosi' dovrebbe esistere
                msg.setText("ATTENZIONE! Il layer esiste gia': si desidera sostituirlo creandone uno nuovo?")
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Layer gia' esistente! Sostituirlo?")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                retval = msg.exec_()
                if (retval != 16384): #l'utente NON ha cliccato yes: sceglie di fermarsi, esco
                    return 0
                elif (retval == 16384): #l'utente HA CLICCATO YES. Tolgo il vecchio layer per aggiungere quello nuovo
                    QgsMapLayerRegistry.instance().removeMapLayer(check_layer_virtuale.id())
                    return retval

    def create_point(self): #creo un layer virtuale puntuale
        #Prima verifico non esista gia' un layer con lo stesso nome
        retval = self.check_layer_virtuale("user_point_layer_int_")
        if (retval == 0): return
        #Get a reference of the layer tree
        root = QgsProject.instance().layerTreeRoot()
        global mem_layer
        mem_layer = QgsVectorLayer("point?crs=epsg:23032", "user_point_layer_int_", "memory")
        if not mem_layer.isValid(): raise Exception("Failed to create memory layer") #in realta' lo crea anche se da errore...
        mem_layer_provider = mem_layer.dataProvider()
        QgsMapLayerRegistry.instance().addMapLayer(mem_layer, False) #aggiungo il layer alla legenda
        #mem_layer.loadNamedStyle(os.getenv("HOME")+'/.qgis2/python/plugins/ProtezioneCivile/qml/temp_point_layer.qml')
        mem_layer.loadNamedStyle(self.PLUGIN_PATH + '/qml/temp_point_layer.qml')
        #Utils.logMessage(str(os.getcwd())) #C:\PROGRA~1\QGIS2~1.14\bin
        #Utils.logMessage(str( os.path.dirname(os.path.abspath(__file__)) )) #C:\Users\riccardo\.qgis2\python\plugins\ProtezioneCivile
        #Insert the layer at the top of the ToC (position 0)
        root.insertLayer(0, mem_layer)
        self.iface.setActiveLayer(mem_layer)
        # Find the layer to edit
        global layer_attivo
        layer_attivo = qgis_utils.iface.activeLayer()
        layer_attivo.startEditing()
        # Implement the Add Feature button
        qgis_utils.iface.actionAddFeature().trigger()
        
    def create_line(self): #creo un layer virtuale lineare
        #Prima verifico non esista gia' un layer con lo stesso nome
        retval = self.check_layer_virtuale("user_line_layer_int_")
        if (retval == 0): return
        #Get a reference of the layer tree
        root = QgsProject.instance().layerTreeRoot()
        global mem_layer
        mem_layer = QgsVectorLayer("linestring?crs=epsg:23032", "user_line_layer_int_", "memory")
        if not mem_layer.isValid(): raise Exception("Failed to create memory layer") #in realta' lo crea anche se da errore...
        mem_layer_provider = mem_layer.dataProvider()
        QgsMapLayerRegistry.instance().addMapLayer(mem_layer, False) #aggiungo il layer alla legenda
        mem_layer.loadNamedStyle(self.PLUGIN_PATH + '/qml/temp_line_layer.qml')
        #Insert the layer at the top of the ToC (position 0)
        root.insertLayer(0, mem_layer)
        self.iface.setActiveLayer(mem_layer)
        # Find the layer to edit
        global layer_attivo
        layer_attivo = qgis_utils.iface.activeLayer()
        layer_attivo.startEditing()
        # Implement the Add Feature button
        qgis_utils.iface.actionAddFeature().trigger()
        
    def create_poly(self): #creo un layer virtuale poligonale
        #Prima verifico non esista gia' un layer con lo stesso nome
        retval = self.check_layer_virtuale("user_poly_layer_int_")
        if (retval == 0): return
        #Get a reference of the layer tree
        root = QgsProject.instance().layerTreeRoot()
        global mem_layer
        mem_layer = QgsVectorLayer("polygon?crs=epsg:23032", "user_poly_layer_int_", "memory")
        if not mem_layer.isValid(): raise Exception("Failed to create memory layer") #in realta' lo crea anche se da errore...
        mem_layer_provider = mem_layer.dataProvider()
        QgsMapLayerRegistry.instance().addMapLayer(mem_layer, False) #aggiungo il layer alla legenda
        mem_layer.loadNamedStyle(self.PLUGIN_PATH + '/qml/temp_poly_layer.qml')
        #Insert the layer at the top of the ToC (position 0)
        root.insertLayer(0, mem_layer)
        self.iface.setActiveLayer(mem_layer)
        # Find the layer to edit
        global layer_attivo
        layer_attivo = qgis_utils.iface.activeLayer()
        layer_attivo.startEditing()
        # Implement the Add Feature button
        qgis_utils.iface.actionAddFeature().trigger()
        
    #Se si volessero aggiungere dei campi ai nuovi layer vedere:
    #http://gis.stackexchange.com/questions/30261/how-to-create-a-new-empty-vector-layer-programmatically
        
    def commit_new_feature(self): #committo il layer virtuale
        layer_attivo.commitChanges() # Commit changes
        Utils.logMessage("qui committo il layer virtuale")
    
    def ecco_la_intersezione(self, buffer_dist, featsOrigine, layer_target, layer_origine_str): #eseguo l'intersezione tra i layer indicati
        count_intersected = 0
        count_pop = 0
        result_string = ''
        #featsOrigine = layer_origine.getFeatures() #get all features from layer
        layer_target_str = layer_target.name()
        layer_target_geom = layer_target.wkbType()
        Utils.logMessage("layer target name " + layer_target_str + ' LAYER TYPE - ' + str(layer_target_geom))
        '''
        layer_target_geom==4: #QGis.WKBPoint
        layer_target_geom==3: #QGis.WKBPolygon
        layer_target_geom==2: #QGis.WKBLineString
        '''
        id_field = ''
        attribute_field = ''
        #Tengo traccia dei vari ID per poterli poi selezionare in mappa:
        ids_to_select = list()
        uk_civici_intersected = list()
        for featPoly in featsOrigine: #iterate poly features
            geomPoly = None #initialize geometry from layer
            #Creo BUFFER:
            if (buffer_dist and buffer_dist != '' and buffer_dist > 0):
                buffer_dist = int(buffer_dist)
                geomPoly = featPoly.geometry().buffer(buffer_dist, 5) #buffer from geometry
            else:
                geomPoly = featPoly.geometry() #get geometry from layer
            #performance boost: get point features by poly bounding box first
            featsPnt = layer_target.getFeatures(QgsFeatureRequest().setFilterRect(geomPoly.boundingBox()))
            for featPnt in featsPnt:
                #iterate preselected point features and perform exact check with current polygon
                #if featPnt.geometry().within(geomPoly):
                if featPnt.geometry().intersects(geomPoly):
                    count_intersected += 1
                    ids_to_select.append(featPnt.id())
                    if layer_target_str==self.LAYER_NAME['CIVICI']:
                        id_field = featPnt["uk_civici"]
                        uk_civici_intersected.append(id_field)
                        attribute_field = featPnt["tipo"] +' '+ featPnt["nome"] +' '+ featPnt["civico"]
                        v_lac_anagrafe_query_string = u'"fk_civico" = \'%s\'' % (str(id_field))
                        counted_selected = self.fai_selezione(v_lac_anagrafe_query_string, VLACANAG_layer)
                        #Utils.logMessage("Query:" + str(v_lac_anagrafe_query_string) +" counted_selected?: " + str(counted_selected))
                        count_pop += counted_selected
                        result_string += str(id_field) + " " + str(attribute_field) + "\n"
                    elif layer_target_str==self.LAYER_NAME['STRADE']:
                        id_field = featPnt["PKUID"]
                        attribute_field = featPnt["descr_s16"]
                        result_string += str(id_field) + " " + attribute_field.encode('utf-8') + "\n"
                    elif layer_target_str==self.LAYER_NAME['FABBRICATI']:
                        id_field = featPnt["PKUID"]
                        #attribute_field = featPnt["descr_s16"]
                        result_string += str(id_field) + "\n"
                    elif layer_target_str==self.LAYER_NAME['FERROVIA']:
                        id_field = featPnt["PKUID"]
                        #attribute_field = featPnt["descr_s16"]
                        result_string += str(id_field) + "\n"
                    
                    #self.dockwidget.result_txt.clear()
        prime_string = layer_origine_str + ' - ' + layer_target_str + '  ' + str(count_intersected) + ' intersezioni:\n'
        layer_target.setSelectedFeatures( ids_to_select ) #selezioni gli elementi intercettati in mappa
        if layer_target_str==self.LAYER_NAME['CIVICI']:
            #Richiamo una funzione che posso sfruttare in altri modi:
            write_result = self.write_output_lac_file(uk_civici_intersected)
            
            return prime_string, result_string.decode('utf-8'), count_intersected, count_pop
        elif layer_target_str==self.LAYER_NAME['STRADE']:
            return prime_string, result_string.decode('utf-8')
        elif layer_target_str==self.LAYER_NAME['FABBRICATI']:
            return prime_string, result_string.decode('utf-8')
        elif layer_target_str==self.LAYER_NAME['FERROVIA']:
            return prime_string, result_string.decode('utf-8')
    
    def recupera_residenti_da_ricerca(self):
        #Lancio la funzione di export csv e intercetta dei residenti dalla finestra di RICERCA:
        featsPnt = CIVICI_layer.selectedFeatures()
        counted_selected_CIVICI = CIVICI_layer.selectedFeatureCount()
        if (counted_selected_CIVICI<=0):
            msg = QMessageBox()
            msg.setText("Nessuna geometria selezionata! Selezionare almeno un elemento dal layer CIVICI")
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Errore!")
            msg.setStandardButtons(QMessageBox.Ok)
            retval = msg.exec_()
            return 0
        uk_civici_intersected = list()
        for featPnt in featsPnt:
            id_field = featPnt["uk_civici"]
            uk_civici_intersected.append(id_field)
        write_result = self.write_output_lac_file(uk_civici_intersected)
        return 1
    
    def fai_intersezione(self): #richiamo l'intersezione tra i layer indicati
        '''
        #Provare anche questo altro metodo:
        areas = []
        for line_feature in line_layer.getFeatures():
            cands = area_layer.getFeatures(QgsFeatureRequest().setFilterRect(line_feature.geometry().boundingBox()))
            for area_feature in cands:
                if line_feature.geometry().intersects(area_feature.geometry()):
                    areas.append(area_feature.id())
        area_layer.select(areas)
        '''
        #PRIMO BIVIO: se ho spuntato l'opzione di prendere i civici selezionati manualmente in mappa, allora richiamo subito la funzione che esporta il CSV.
        if (self.dockwidget.manual_civici.isChecked()):
            featsPnt = CIVICI_layer.selectedFeatures()
            counted_selected_CIVICI = CIVICI_layer.selectedFeatureCount()
            if (counted_selected_CIVICI<=0):
                msg = QMessageBox()
                msg.setText("Nessuna geometria selezionata! Selezionare almeno un elemento dal layer CIVICI, oppure deselezionare l'opzione 'Usa i civici selezionati manualmente'")
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Errore!")
                msg.setStandardButtons(QMessageBox.Ok)
                retval = msg.exec_()
                return 0
            uk_civici_intersected = list()
            for featPnt in featsPnt:
                id_field = featPnt["uk_civici"]
                uk_civici_intersected.append(id_field)
            write_result = self.write_output_lac_file(uk_civici_intersected)
            return 1
            
        #Altrimenti proseguo per la strada normale facendo l'intersect tra i layer scelti:
        layer_esistente = self.dockwidget.group_layer_esistente.isChecked()
        nuovo_layer = self.dockwidget.group_nuovo_layer.isChecked()
        get_feature_from_selection = self.dockwidget.atlas_ckbox.isChecked()
        buffer_dist = self.dockwidget.buffer_txt.text()
        featsOrigine = None
        if (layer_esistente==True):
            #self.dockwidget.chkDB.setChecked(False)
            Utils.logMessage("qui eseguo intersezione tra layer esistenti in mappa")
            layer_origine_str = self.dockwidget.combo_layer.currentText()
            layer_origine = QgsMapLayerRegistry.instance().mapLayersByName(layer_origine_str)[0]
            if (get_feature_from_selection==True):
                counted_selected_Origine = layer_origine.selectedFeatureCount()
                Utils.logMessage("elementi selezionati dall'origine:" + str(counted_selected_Origine))
                if (counted_selected_Origine<1):
                    msg = QMessageBox()
                    msg.setText("Nessuna geometria selezionata! Selezionare almeno un elemento dal layer di origine scelto, oppure deselezionare l'opzione 'Usa solo le geometrie selezionate'")
                    msg.setIcon(QMessageBox.Critical)
                    msg.setWindowTitle("Errore!")
                    msg.setStandardButtons(QMessageBox.Ok)
                    retval = msg.exec_()
                    return 0
                else:
                    featsOrigine = layer_origine.selectedFeatures() #for testing, use selected features only
                    #Per effettuare l'intersezione vera e propria richiamo una funzione esterna:
                    civici_intro, civici_risultato, count_intersected, count_pop = self.ecco_la_intersezione(buffer_dist, featsOrigine, CIVICI_layer, layer_origine_str) ###CIVICI
                    featsOrigine = layer_origine.selectedFeatures() #for testing, use selected features only
                    fabbricati_intro, fabbricati_risultato = self.ecco_la_intersezione(buffer_dist, featsOrigine, FABBRICATI_layer, layer_origine_str) ###FABBRICATI
            
            else:
                featsOrigine = layer_origine.getFeatures() #get all features from layer
                #Per effettuare l'intersezione vera e propria richiamo una funzione esterna:
                civici_intro, civici_risultato, count_intersected, count_pop = self.ecco_la_intersezione(buffer_dist, featsOrigine, CIVICI_layer, layer_origine_str) ###CIVICI
                #strade_intro, strade_risultato = self.ecco_la_intersezione(buffer_dist, featsOrigine, STRADE_layer, layer_origine_str) ###STRADE
                #ferrovia_intro, ferrovia_risultato = self.ecco_la_intersezione(buffer_dist, featsOrigine, FERROVIA_layer, layer_origine_str) ###FERROVIA
                featsOrigine = layer_origine.getFeatures() #get all features from layer - lo devo richiamare perche' in qualche modo si azzera al secondo giro!
                fabbricati_intro, fabbricati_risultato = self.ecco_la_intersezione(buffer_dist, featsOrigine, FABBRICATI_layer, layer_origine_str) ###FABBRICATI
            
            prime_string = 'Popolazione coinvolta:' + str(count_pop) + '\n\n'
            #self.dockwidget.result_txt.setText(prime_string+civici_intro+civici_risultato+'\n'+strade_intro+strade_risultato+'\n'+ferrovia_intro+ferrovia_risultato+'\n'+fabbricati_intro+fabbricati_risultato)
            self.dockwidget.result_txt.setText(prime_string+civici_intro+civici_risultato+'\n'+fabbricati_intro+fabbricati_risultato)
            
        elif (nuovo_layer==True):
            Utils.logMessage("qui eseguo intersezione tra layer temporaneo e layer in mappa")
            #L'ULTIMO LAYER CREATO DALL'UTENTE SI CHIAMA "MEM_LAYER"!! Se si vuole avere piu' controllo su questa variabile agire di conseguenza
            msg = QMessageBox()
            try:
                layer_origine = mem_layer
            except NameError as err:
                msg.setText("Anche se presente nel progetto occorre RIdefinire il layer temporaneo per l'intersezione, oppure scegliere l'opzione 'Interseca un layer esistente'")
                msg.setDetailedText(err.args[0])
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Errore!")
                msg.setStandardButtons(QMessageBox.Ok)
                retval = msg.exec_()
                Utils.logMessage(err.args[0])
                return 0
            layer_origine_str = mem_layer.name()
            #featsOrigine = layer_origine.selectedFeatures() #for testing, use selected features only
            featsOrigine = layer_origine.getFeatures() #get all features from layer
            #Per effettuare l'intersezione vera e propria richiamo una funzione esterna:
            civici_intro, civici_risultato, count_intersected, count_pop = self.ecco_la_intersezione(buffer_dist, featsOrigine, CIVICI_layer, layer_origine_str) ###CIVICI
            #strade_intro, strade_risultato = self.ecco_la_intersezione(buffer_dist, featsOrigine, STRADE_layer, layer_origine_str) ###STRADE
            #ferrovia_intro, ferrovia_risultato = self.ecco_la_intersezione(buffer_dist, featsOrigine, FERROVIA_layer, layer_origine_str) ###FERROVIA
            featsOrigine = layer_origine.getFeatures() #get all features from layer
            fabbricati_intro, fabbricati_risultato = self.ecco_la_intersezione(buffer_dist, featsOrigine, FABBRICATI_layer, layer_origine_str) ###FABBRICATI
            
            prime_string = 'Popolazione coinvolta:' + str(count_pop) + '\n\n'
            #self.dockwidget.result_txt.setText(prime_string+civici_intro+civici_risultato+'\n'+strade_intro+strade_risultato+'\n'+ferrovia_intro+ferrovia_risultato+'\n'+fabbricati_intro+fabbricati_risultato)
            self.dockwidget.result_txt.setText(prime_string+civici_intro+civici_risultato+'\n'+fabbricati_intro+fabbricati_risultato)
    
    def get_field_type(self): #in realta qui creo la combo con i civici
        if not(layer_da_filtrare):
            return 0
        cod_com_da_filtrare = self.dlg.combo_layer.currentText()
        field_da_filtrare_raw = self.dlg.combo_fields.currentText() #nome e tipo della via
        
        #Interrogo il layer secondo questi 3 dati: cod_comu, nome e tipo:
        query_string = u'"cod_comu" = \'%s\' AND "nome" || \' (\'  ||   "tipo"  || \')\' = \'%s\'' % (str(cod_com_da_filtrare), str(field_da_filtrare_raw.replace("'", r"\'")))
        Utils.logMessage("Filtro di che?: " + query_string)
        select_expression = QgsExpression( query_string )
        test_select = layer_da_filtrare.getFeatures( QgsFeatureRequest( select_expression ) )
        #Build a list of feature Ids from the result obtained:
        ids_selected = [i.id() for i in test_select]
        #Select features with the ids obtained in 3.:
        layer_da_filtrare.removeSelection() #ripulisco eventuali selezioni precedenti
        layer_da_filtrare.setSelectedFeatures( ids_selected )
        layer_ids_selezionate = layer_da_filtrare.selectedFeaturesIds()
        layer_feature_selezionate = layer_da_filtrare.selectedFeatures()
        civici = set()
        for j_ids in layer_feature_selezionate:
            recupera_valore_campo = j_ids['civico']
            civici.add(recupera_valore_campo)
        layer_da_filtrare.removeSelection() #ripulisco la selezione
        #Popolo il menu a tendina ma prima lo svuoto:
        self.dlg.combo_civici.clear()
        global default_civico
        default_civico = '--Civico--'
        self.dlg.combo_civici.addItem(default_civico) #prima opzione non valida
        for n_civico in sorted(civici):
            self.dlg.combo_civici.addItem(n_civico)
        idx_civico = self.dlg.combo_civici.findText(default_civico)
        self.dlg.combo_civici.setCurrentIndex(idx_civico)
        

    def fai_selezione(self, query_string, layer_da_filtrare):
        #Se invece di filtrare volessi attuare una selezione:
        select_expression = QgsExpression( query_string )
        #request = QgsFeatureRequest().setFilterExpression( query_string )
        #test_select = layer_da_filtrare.getFeatures( request )
        test_select = layer_da_filtrare.getFeatures( QgsFeatureRequest( select_expression ) )
        #Build a list of feature Ids from the result obtained:
        ids_selected = [i.id() for i in test_select]
        #Select features with the ids obtained in 3.:
        layer_da_filtrare.removeSelection() #ripulisco eventuali selezioni precedenti
        layer_da_filtrare.setSelectedFeatures( ids_selected )
        layer_ids_selezionate = layer_da_filtrare.selectedFeaturesIds()
        layer_feature_selezionate = layer_da_filtrare.selectedFeatures()
        #In questo caso voglio per il momento restituire indietro il numero delle feature selezionate, ovvero degli abitanti:
        counted_selected = layer_da_filtrare.selectedFeatureCount()
            
        return counted_selected
        #for j_ids in layer_ids_selezionate: #questo j_ids contiene solo gli ID delle features selezionate
        '''for j_ids in layer_feature_selezionate:
            recupera_valore_campo = j_ids[field_da_filtrare]
            Utils.logMessage("ID: " + str(recupera_valore_campo))
            #Se volessi modificare l'attributo delle feature selezionate:
            #layer_da_filtrare.startEditing()
            #idx_campo_da_modificare=layer_da_filtrare.fieldNameIndex('nome_campo')
            #nuovo_valore_da_assegnare=None
            #layer_da_filtrare.changeAttributeValue(j_ids, idx_campo_da_modificare, nuovo_valore_da_assegnare)
            #layer_da_filtrare.rollBack()
            #layer_da_filtrare.commitChanges()
        '''
        
        '''
        idx_field = layer_da_filtrare.fields().indexFromName(field_da_filtrare)
        if (idx_field == -1): #al cambio di combobox non riconosce subito l'indice del campo
            return 0
        type_field = layer_da_filtrare.fields().field(idx_field).typeName()
        Utils.logMessage("idx field: " + str(type_field))
        self.dlg.field_type.setText(str(type_field))
        '''        
        
        
    #--------------------------------------------------------------------------

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('ProtezioneCivile', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def disconnetto_pulsanti(self):
        #Avendo definito un dock e volendo sfruttare anche il dialog, devo disconnettere alcuni oggetti per poi riconnetterli onde evitare doppie azioni
        #In realta' anche questa disconnessione e' difficle da gestire...Usare o il Dock o il Dialog!!
        self.dlg.search_btn.clicked.disconnect(self.seleziona)
        #se modifico il drop down faccio partire un'azione:
        QObject.disconnect(self.dlg.combo_layer, SIGNAL("currentIndexChanged(const QString&)"), self.updateFromSelection_comune)
        QObject.disconnect(self.dlg.combo_fields, SIGNAL("currentIndexChanged(const QString&)"), self.get_field_type)
    
    #Normalmente le azioni sui pulsanti sono definite sotto initGui() ma le richiamo qui per maggior ordine.
    def connetto_pulsanti_dialog(self):
        #Pulsanti per il dialog:
        self.dlg.search_btn.clicked.connect(self.seleziona)   
        #se modifico il drop down faccio partire un'azione:
        QObject.connect(self.dlg.combo_layer, SIGNAL("currentIndexChanged(const QString&)"), self.updateFromSelection_comune)
        QObject.connect(self.dlg.combo_fields, SIGNAL("currentIndexChanged(const QString&)"), self.get_field_type)
        QObject.connect(self.dlg.fileBrowse_btn, SIGNAL("clicked()"), self.select_output_file_dlg)
        self.dlg.fileBrowse_txt.clear()
        QObject.connect(self.dlg.select_btn, SIGNAL("clicked()"), self.recupera_residenti_da_ricerca)

    def connetto_pulsanti_dock(self):
        #Pulsanti per il dock:
        QObject.connect(self.dockwidget.select_btn, SIGNAL("clicked()"), self.fai_intersezione)
        QObject.connect(self.dockwidget.select_feature, SIGNAL("clicked()"), self.select_layer_exist)
        QObject.connect(self.dockwidget.point_layer, SIGNAL("clicked()"), self.create_point)
        QObject.connect(self.dockwidget.linear_layer, SIGNAL("clicked()"), self.create_line)
        QObject.connect(self.dockwidget.poly_layer, SIGNAL("clicked()"), self.create_poly)
        QObject.connect(self.dockwidget.commit_layer, SIGNAL("clicked()"), self.commit_new_feature)
        #SALVA FILE con nome
        self.dockwidget.fileBrowse_txt.clear()
        QObject.connect(self.dockwidget.fileBrowse_btn, SIGNAL("clicked()"), self.select_output_file)
        #se modifico il drop down faccio partire un'azione:
        QObject.connect(self.dockwidget.combo_layer, SIGNAL("currentIndexChanged(const QString&)"), self.updateFromSelection_layers)
        #QObject.connect(self.dockwidget.combo_fields, SIGNAL("currentIndexChanged(const QString&)"), self.get_field_type)
        #Verifico il layer iniziale da intersecare (esistente o custom) escludendo la doppia scelta:
        self.dockwidget.group_nuovo_layer.clicked.connect(self.choose_layer_exist)
        self.dockwidget.group_layer_esistente.clicked.connect(self.choose_layer_new)
        self.dockwidget.manual_civici.clicked.connect(self.manual_lac)
        
    def manual_lac(self):
        manual = self.dockwidget.manual_civici.isChecked()
        if (manual==True):
            self.dockwidget.select_btn.setEnabled(True)
        else:
            self.dockwidget.select_btn.setEnabled(False)
    
    def choose_layer_exist(self):
        shp_value = self.dockwidget.group_nuovo_layer.isChecked()
        if (shp_value==True):
            self.dockwidget.group_layer_esistente.setChecked(False)
            #inoltre attivo il pulsante che avvia l'intersezione anche se il layer temporaneo per l'intersezione definito dall'utente non e' ancora stato creato:
            self.dockwidget.select_btn.setEnabled(True)
        else:
            self.dockwidget.select_btn.setEnabled(False)
    
    def choose_layer_new(self):
        db_value = self.dockwidget.group_layer_esistente.isChecked()
        if (db_value==True):
            self.dockwidget.group_nuovo_layer.setChecked(False)
        
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/ProtezioneCivile/search_address.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Cerca un indirizzo'),
            callback=self.run,
            parent=self.iface.mainWindow())
            
        #Aggiungo DockWidget:
        icon_path = ':/plugins/ProtezioneCivile/cross.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Intercetta i cittadini'),
            callback=self.run_dock,
            parent=self.iface.mainWindow())
        
        icon_path = ':/plugins/ProtezioneCivile/help.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Informazioni'),
            callback=self.run_help,
            parent=self.iface.mainWindow())
            
        #Implemento alcune azioni sui miei pulsanti
        #self.connetto_pulsanti()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            #self.iface.removePluginDatabaseMenu(
            self.iface.removePluginMenu(
                self.tr(u'&ProtezioneCivile'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar
        
    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""
        #print "** CLOSING Core"
        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        # remove this statement if dockwidget is to remain for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe when closing the docked window:
        # self.dockwidget = None
        self.pluginIsActive = False
        
    #All'apertura della finestra ripulisco eventuali tracce precedenti:
    def clean_elements_dialog(self):
        self.dlg.combo_layer.clear()
        self.dlg.combo_fields.clear()
        self.dlg.combo_civici.clear()
        self.dlg.filter_txt.clear()
        self.dlg.fileBrowse_txt.clear()
        self.dlg.fileBrowse_txt.setText(self.CSV_PATH)
        #self.dlg.pageBar.setValue(0)
        #self.dlg.field_type.setText('field type')
        #self.dlg.atlas_ckbox.setChecked(False)        
        #self.dlg.buttonGroup.setExclusive(False);
        #self.dlg.radio_png.setChecked(False)
        #self.dlg.radio_pdf.setChecked(False)
        #self.dlg.buttonGroup.setExclusive(True);
    def clean_elements_dock(self):
        self.dockwidget.combo_layer.clear()
        #self.dockwidget.combo_fields.clear()
        #self.dockwidget.filter_txt.clear()
        self.dockwidget.result_txt.clear()
        self.dockwidget.buffer_txt.clear()
        self.dockwidget.fileBrowse_txt.clear()
        self.dockwidget.fileBrowse_txt.setText(self.CSV_PATH)
        #self.dockwidget.pageBar.setValue(0)
        #self.dockwidget.field_type.setText('field type')
        self.dockwidget.atlas_ckbox.setChecked(False) #lo uso per scegleire se usare o meno le gemetrie selezionate dal layer di partenza
        self.dockwidget.manual_civici.setChecked(False) #lo uso per usare una eventuale selezione manuale dei civici
        #self.dockwidget.buttonGroup.setExclusive(False);
        #self.dockwidget.radio_png.setChecked(False)
        #self.dockwidget.radio_pdf.setChecked(False)
        #self.dockwidget.buttonGroup.setExclusive(True);
    
    def run_dock(self):
        """Run method that loads and starts the plugin"""
        if not self.pluginIsActive:
            self.pluginIsActive = True
            #print "** STARTING Core"
            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = ProtezioneCivileDockDockWidget()
            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)
            # show the dockwidget
            # TODO: fix to allow choice of dock location        
            self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dockwidget)

            #Per non riscrivere tutto il codice precedente, ridefinisco il QDialog per sostituirlo con questo DockWidget, equiparando le 2 variabili:
            #self.dlg = self.dockwidget

            #All'apertura della finestra ripulisco eventuali tracce precedenti:
            self.clean_elements_dock()
            
            #Inizializzo i layer presenti in mappa:
            #self.inizializza_layer(self.dockwidget.combo_layer)
            #self.inizializza_layer(self.dockwidget.combo_fields)
            #Avendo entrambe le combobox delle regole diverse li carico in maniera diversa:
            result_inizializza = self.inizializza_layer_origine(self.dockwidget.combo_layer)
            if (result_inizializza==0):
                self.dockwidget.close()
                return 0
            #self.inizializza_layer_destinazione(self.dockwidget.combo_fields)
            
            #Ridefinisco le azioni sui pulsanti. Per evitare comportamenti anomali dovuti alla copresenza di Dock e Dialog prima li disconnetto:
            #self.disconnetto_pulsanti() #genera anomalie
            self.connetto_pulsanti_dock()
        
            # show the dock
            self.dockwidget.show()
    
    def run_help(self):
        #Prelevo il numero di versione dal file metadata.txt:
        #nome_file = os.getenv("HOME")+'/.qgis2/python/plugins/ProtezioneCivile/metadata.txt'
        nome_file = self.PLUGIN_PATH + '/metadata.txt'
        searchfile = open(nome_file, "r")
        for line in searchfile:
            if "version=" in line:
                version = str(line[8:11])
                #Utils.logMessage(str(line[8:]))
            if "release_date=" in line:
                release_date = str(line[13:23])
        searchfile.close()
        self.dlg_help.label_version.clear()
        self.dlg_help.label_version.setText("Versione: " + version + " - " + release_date)
        # show the dialog
        self.dlg_help.show()
        # Run the dialog event loop
        result = self.dlg_help.exec_()
        
    def run(self):
        #Se ho aggiunto il Dock, riporto il self.dlg al Dialog:
        self.dlg = ProtezioneCivileDialog()
        
        #All'apertura della finestra ripulisco eventuali tracce precedenti:
        self.clean_elements_dialog()
        
        #Inizializzo i layer presenti in mappa:
        result_inizializza = self.inizializza_comuni()
        if (result_inizializza==0):
            return 0
        
        #Ridefinisco le azioni sui pulsanti. Per evitare comportamenti anomali dovuti alla copresenza di Dock e Dialog prima li disconnetto:
        #self.disconnetto_pulsanti() #genera anomalie
        self.connetto_pulsanti_dialog()
        
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        '''result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass'''
