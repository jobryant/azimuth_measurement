# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AzimuthMeasurement
                                 A QGIS plugin
 Just measure Azimuth when you draw a line
                              -------------------
        begin                : 2015-12-18
        git sha              : $Format:%H$
        copyright            : (C) 2015 by WebGeoDataVore
        email                : contact@webgeodatavore.com
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
from __future__ import absolute_import
from builtins import str
from builtins import object
from qgis.PyQt.QtCore import QSettings, Qt, QTranslator, qVersion, QCoreApplication

from qgis.PyQt.QtWidgets import QAction, QWidgetAction
from qgis.PyQt.QtGui import QIcon
# Initialize Qt resources from file resources.py
# import resources
from .resources import *

from qgis.core import (QgsGeometry,
                       QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform,
                       QgsCoordinateTransformContext)

from .draw_mono_line_map_tool import DrawMonoLineMapTool

# Import the code for the widget
from .azimuth_measurement_widget import AzimuthMeasurementWidget
import os.path

from .gc_geo import *


class AzimuthMeasurement(object):
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.ratio = 1
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            '{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dock = AzimuthMeasurementWidget()
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.hide()

        # Declare instance attributes
        self.actions = []

        if not hasattr(self, 'draw_mono_line'):
            self.draw_mono_line = DrawMonoLineMapTool(self.canvas)
            self.draw_mono_line.deactivated.connect(self.desactivateTool)
            self.draw_mono_line.azimuth_calcul.connect(
                self.populate_dock_widget
            )
            self.dock.dist_units.currentIndexChanged.connect(self.set_units)

        self.dock.clear_button.clicked.connect(self.clear_all)

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
        return QCoreApplication.translate('AzimuthMeasurement', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/AzimuthMeasurement/icon.png'

        icon = QIcon(icon_path)
        action = QAction(
            icon, self.tr(u'Azimut Measurement'),
            self.iface.mainWindow()
        )
        action.triggered.connect(self.run)

        for act in self.iface.attributesToolBar().actions():
            if isinstance(act, QWidgetAction):
                first_action = act.defaultWidget().actions()[0]
                if first_action == self.iface.actionMeasure():
                    act.defaultWidget().addAction(
                        action
                    )
        self.actions.append(action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.clear_canvas()
        for act in self.iface.attributesToolBar().actions():
            if isinstance(act, QWidgetAction):
                first_action = act.defaultWidget().actions()[0]
                if first_action == self.iface.actionMeasure():
                    act.defaultWidget().removeAction(
                        self.actions[0]
                    )

    def run(self):
        """Run method that performs all the real work"""
        # show the widget
        self.dock.show()
        self.canvas.setMapTool(self.draw_mono_line)

    def desactivateTool(self):
        """Slot called when desactivate the tool.
        Reset values in the dock and hide the dock"""
        self.set_widget_content()
        # self.dock.hide()

    def populate_dock_widget(self, start_point, end_point):
        """Fill the fields in the dock"""
        result = self.calculate_azimuth(start_point, end_point)
        if ((result is not None and 'distance' in result and
             'azimuth' in result)):
            self.distance = result['distance']
            self.azimuth = result['azimuth']
            precision = "{0:.2f}"
            self.set_widget_content(
                precision.format(self.distance * self.ratio),
                precision.format(self.azimuth)
            )
        else:
            self.distance = ""
            self.azimuth = ""
            self.set_widget_content()

    def set_widget_content(self, distance="", azimuth=""):
        self.dock.geographic_distance.setText(distance)
        self.dock.azimuth.setText(azimuth)

    def clear_canvas(self):
        self.draw_mono_line.reset()

    def clear_all(self):
        self.clear_canvas()
        self.set_widget_content()

    def calculate_azimuth(self, start_point, end_point):
            sp = self.transform_to_epsg_4326(start_point)
            ep = self.transform_to_epsg_4326(end_point)
            print('sp', sp)
            print('ep', ep)
            calculus = great_distance(
                start_longitude=sp.x(),
                start_latitude=sp.y(),
                end_longitude=ep.x(),
                end_latitude=ep.y()
            )
            return calculus

    def transform_to_epsg_4326(self, point):
        if self.canvas.mapSettings().destinationCrs().authid() != 'EPSG:4326':
            crs_src = self.canvas.mapSettings().destinationCrs()
            crs_dest = QgsCoordinateReferenceSystem(4326)
            xform = QgsCoordinateTransform(crs_src, crs_dest, QgsCoordinateTransformContext())
            point.transform(xform)
            return point
        else:
            return point

    def set_units(self, current_index):
        if current_index == 0:
            self.ratio = 100
        elif current_index == 1:
            self.ratio = 1
        elif current_index == 2:
            self.ratio = 0.001
        if isinstance(self.distance, float):
            self.dock.geographic_distance.setText(
                str(self.distance * self.ratio)
            )
