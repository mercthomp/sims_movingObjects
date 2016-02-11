import os
import numpy as np
from lsst.sims.utils import haversine
import .chebyshevUtils as cheb
from .orbits import Orbits
from .ephemerides import PyEphemerides

__all__ = ['ChebyFits']

def v_three_sixy_to_neg(element, min, max):
    if (min < 100) & (max > 270):
        if element > 270:
            return element - 360.
        else:
            return element
    else:
        return element
v_360_to_neg = np.vectorize(three_sixy_to_neg)


class ChebyFits(object):
    """Generates chebyshev coefficients for a provided set of orbits.

    Calculates true ephemerides using PyEphemerides, then fits these positions with a constrained
    Chebyshev Polynomial, using the routines in chebyshevUtils.py.
    Many chebyshev polynomials are used to fit one moving object over a given timeperiod;
    typically, the length of each timespan of each fit is about two days.
    The timestep between computed ephemerides varies with population;
    typically, the positions are calculated approximately every 30 minutes.
    The exact timestep and length of each timestep is adjusted so that the residuals in RA/Dec position
    are less than skyTolerance - default = 2.5mas.

    Parameters
    ----------
    skyTolerance : float, optional
        The desired tolerance in mas between ephemerides calculated by OpenOrb and fitted values.
        Default 2.5 mas.
    ephFile : str, optional
        The path to the JPL ephemeris file to use. Default is '$OORB_DATA/de405.dat'.
    """
    def __init__(self, skyTolerance=2.5, ephFile=None):
        self.skyTolerance = skyTolerance
        if ephfile is None:
            ephfile = os.path.join(os.getenv('OORB_DATA'), 'de405.dat')
        self.pyephems = PyEphemerides(ephfile)

    def setOrbits(self, orbitObj):
        """Set the orbits, to be used to generate ephemerides.

        Parameters
        ----------
        orbitObj : Orbits
           The orbits to use to generate ephemerides.
        """
        if not isinstance(orbitObj, Orbits):
            raise ValueError('Need to provide an Orbits object, to validate orbital parameters.')
        self.orbitObj = orbitObj

    def generateEphemerides(self, times, obscode=807, timeScale='TAI'):
        """Generate ephemerides using OpenOrb for all orbits.

        Saves the resulting ephemerides in self.ephems.

        Parameters
        ----------
        times : numpy.ndarray
            The times to use for ephemeris generation.
        obscode : int
            The observatory code for ephemeris generation. Default is 807, CTIO/approximate LSST.
        timeScale : str, optional
            The default value of TAI is appropriate for most fitting purposes.
            Using UTC will induce discontinuities where the leap seconds between TAI and UTC occur.
        """
        self.pyephems.setOrbits(self.orbitObj)
        self.ephems = self.pyephems.generateEphemerides(times, obscode=obscode,
                                                        timeScale=timeScale, byObject=True)

    def _setGranularity(self, distance_moved):
        """
        Set the first pass values for timestep (for generating ephemerides) and chebyshev segment length.

        If distance is:
        < 0.8 degrees/day  treat same as MBA
        < 1.6 degrees/day  try gen 1 day at 64 points per day.
        < 3.2 deg/day      try gen 0.5 day at 128 points per day
        < 6.4 deg/day       try gen 0.25 day at 256 points per day
        < 12.8 deg.day     try gen 0.125 day at 512 points per day
        < 25.6 deg/day     try gen 0.0625 day at 1024 points per day
        < 51.2 deg/day     try gen 0.03125 day at 2048 points per day
        > try gen 0.015625 day at 4096 points per day
        ngran = 64 always, ngran = int(range/timestep)

        Parameters
        ----------
        distance_moved : float
            Distance moved across the sky, in degrees.
        """
        self.ngran = 64
        if distance_moved < 0.8:
            self.timestep = 0.03125  # 1/32 day
        elif distance < 1.6:
            self.timestep = 0.015625  # 1/64 day
        elif distance < 3.2:
            self.timestep = 0.0078125  # 1/128 day
        elif distance < 6.4:
            self.timestep = 0.00390625  # 1/256 day
        elif distance < 12.8:
            self.timestep = 0.001953125  # 1/512 day
        elif distance < 25.6:
            self.timestep = 0.0009765625  # 1/1024 day
        elif distance < 51.2:
            self.timestep = 0.00048828125  # 1/2048 day
        elif distance < 102.4:
            self.timestep = 0.000244140625  # 1/4096 day
        else:  # fastest it can go
            self.timestep = 0.0001220703125  # 1/8192 day
        self.ngran = 64
        self.length = self.ngran * self.timestep

    def _updateGranularity(self, p_resid, dec):
        """Update the granularity if the residuals in the position are beyond the tolerance.

        Parameters
        ----------
        p_resid : float
            Maximum positional residual, mas.
        dec : float
            Declination of the object, deg.
        """
        factor = 1.
        if p_resid > 1000:
            factor = 16.
        elif p_resid > 100:
            factor = 8.
        elif p_resid > 15:
            factor = 6.
        elif p_resid > 5:
            factor = 4.
        elif p_resid > 2:
            factor = 2.
        self.timestep = self.timestep / factor
        self.length = self.length / factor
        # cut it in half once more if chance to go over poles
        if dec < -75. or dec > 75.:
            self.timestep = self.timestep/2.
            self.length = self.length/2.

    def _calcCoeffs(self):
        """Call chebyfit to calculate coefficient for a given axes of the ephemerides."""
        pass
