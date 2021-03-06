from __future__ import print_function
import numpy as np
import unittest
import lsst.utils.tests
from lsst.obs.lsstSim import LsstSimMapper
from lsst.sims.coordUtils import lsst_camera
from lsst.sims.movingObjects import LsstCameraFootprint
from lsst.sims.coordUtils import clean_up_lsst_camera

class TestCamera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.camera = LsstSimMapper().camera

    @classmethod
    def tearDownClass(cls):
        del cls.camera
        clean_up_lsst_camera()

    def setUp(self):
        obj_ra = np.array([10.0, 12.1], float)
        obj_dec = np.array([-30.0, -30.0], float)
        obj_mjd = np.array([59580.16, 59580.16], float)
        self.ephems = np.array(list(zip(obj_ra, obj_dec, obj_mjd)),
                               dtype=([('ra', float), ('dec', float), ('mjd', float)]))
        obs_ra = np.array([10.0, 10.0], float)
        obs_dec = np.array([-30.0, -30.0], float)
        obs_mjd = np.array([59580.16, 59580.16], float)
        obs_rotSkyPos = np.zeros(2)
        self.obs = np.array(list(zip(obs_ra, obs_dec, obs_rotSkyPos, obs_mjd)),
                            dtype=([('ra', float), ('dec', float), ('rotSkyPos', float), ('mjd', float)]))

    def testCameraFov(self):
        cameraFootprint = LsstCameraFootprint()
        idxObs = cameraFootprint.inCameraFov(self.ephems, self.obs, epoch=2000.0,
                                                timeCol='mjd')
        self.assertEqual(idxObs, [0])

class TestMemory(lsst.utils.tests.MemoryTestCase):
    pass


def setup_module(module):
    lsst.utils.tests.init()


if __name__ == "__main__":
    lsst.utils.tests.init()
    unittest.main()
