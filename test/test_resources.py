# coding=utf-8
"""Resources test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'ar_gaeta@yahoo.it'
__date__ = '2016-10-17'
__copyright__ = 'Copyright 2016, ar_gaeta@yahoo.it'

import unittest

from PyQt4.QtGui import QIcon



class EsportaAtlanteHailDialogTest(unittest.TestCase):
    """Test rerources work."""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_icon_png(self):
        """Test we can click OK."""
        path = ':/plugins/EsportaAtlanteHail/icon.png'
        icon = QIcon(path)
        self.assertFalse(icon.isNull())

if __name__ == "__main__":
    suite = unittest.makeSuite(EsportaAtlanteHailResourcesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)



