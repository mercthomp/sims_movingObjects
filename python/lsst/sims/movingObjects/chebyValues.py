import os
import warnings
import numpy as np
import pandas as pd
import chebyshevUtils as cheb
from .orbits import Orbits
from .ephemerides import PyOrbEphemerides

__all__ = ['ChebyValues']


class ChebyValues(object):
    """Calculates positions, velocities, deltas, vmags and elongations, given a series of coefficients generated by ChebyFits.
    """
    def __init__(self):
        self.coeffs = {}
        self.coeffKeys = ['objId', 'tStart', 'tEnd', 'ra', 'dec', 'delta', 'vmag', 'elongation']
        self.ephemerisKeys = ['ra', 'dradt', 'dec', 'ddecdt', 'delta', 'vmag', 'elongation']

    def setCoefficients(self, chebyFits):
        """Set coefficients using a ChebyFits object.
        (which contains a dictionary of objId, tStart, tEnd, ra, dec, delta, vmag, and elongation lists).

        Parameters
        ----------
        chebyFits : chebyFits
            ChebyFits object, with attribute 'coeffs' - a dictionary of lists of coefficients.
        """
        self.coeffs = chebyFits.coeffs
        # Convert list of coefficients into numpy arrays.
        for k in self.coeffs:
            self.coeffs[k] = np.array(self.coeffs[k])
        # Check that expected values
        if len(set(self.coeffKeys) - set(self.coeffs)) > 0:
            raise ValueError('Did not receive all expected coefficient keys from chebyFitsCoefficients')
        self.coeffs['meanRA'] = self.coeffs['ra'].swapaxes(0, 1)[0]
        self.coeffs['meanDec'] = self.coeffs['dec'].swapaxes(0, 1)[0]

    def readCoefficients(self, chebyFitsFile):
        """Read coefficients from output file written by ChebyFits.

        Parameters
        ----------
        chebyFitsFile : str
            The filename of the coefficients file.
        """
        if not os.path.isfile(chebyFitsFile):
            raise IOError('Could not find chebyFitsFile at %s' % (chebyFitsFile))
        # Read the coefficients file.
        coeffs = pd.read_table(chebyFitsFile, delim_whitespace=True)
        # The header line provides information on the number of coefficients for each parameter.
        datacols = coeffs.columns.values
        cols = {}
        coeff_cols = ['ra', 'dec', 'delta', 'vmag', 'elongation']
        for k in coeff_cols:
            cols[k] = [x for x in datacols if x.startswith(k)]
        # Translate dataframe to dictionary of numpy arrays
        # while consolidating RA/Dec/Delta/Vmag/Elongation coeffs.
        self.coeffs['objId'] = coeffs.objId.as_matrix()
        self.coeffs['tStart'] = coeffs.tStart.as_matrix()
        self.coeffs['tEnd'] = coeffs.tEnd.as_matrix()
        for k in coeff_cols:
            self.coeffs[k] = np.empty([len(cols[k]), len(coeffs)], float)
            for i in range(len(cols[k])):
                self.coeffs[k][i] = coeffs['%s_%d' % (k, i)].as_matrix()
        # Add the mean RA and Dec columns (before swapping the coefficients axes).
        self.coeffs['meanRA'] = self.coeffs['ra'][0]
        self.coeffs['meanDec'] = self.coeffs['dec'][0]
        # Swap the coefficient axes so that they are [segment, coeff].
        for k in coeff_cols:
            self.coeffs[k] = self.coeffs[k].swapaxes(0, 1)

    def _evalSegment(self, segmentIdx, time, subsetSegments=None):
        """Evaluate the ra/dec/delta/vmag/elongation values for a given segment at a given time.

        Parameters
        ----------
        segmentIdx : int
            The index in self.coeffs for the segment.
        time : float
            The time at which to evaluate the segment.
        subsetSegments : numpy.ndarray, optional
            Optionally specify a subset of the total segment indexes.

        Returns
        -------
        dict
           Dictionary of RA, Dec, delta, vmag, and elongation values for the segment indicated,
           at the time indicated.
        """
        if subsetSegments is None:
            subsetSegments = np.ones(len(self.coeffs['objId']), dtype=bool)
        tStart = self.coeffs['tStart'][subsetSegments][segmentIdx]
        tEnd = self.coeffs['tEnd'][subsetSegments][segmentIdx]
        if (time < tStart) or (time > tEnd):
            raise ValueError('Time requested (%f) is out of bounds for segment index (valid %f to %f).'
                             % (time, tStart, tEnd))
        tScaled = time - tStart
        tInterval = np.array([tStart, tEnd]) - tStart
        # Evaluate RA/Dec/Delta/Vmag/elongation.
        ephemeris = {}
        ephemeris['ra'], ephemeris['dradt'] = cheb.chebeval(tScaled, self.coeffs['ra'][subsetSegments][segmentIdx],
                                                            interval=tInterval, doVelocity=True)
        ephemeris['dec'], ephemeris['ddecdt'] = cheb.chebeval(tScaled, self.coeffs['dec'][subsetSegments][segmentIdx],
                                                              interval=tInterval, doVelocity=True)
        ephemeris['dradt'] = ephemeris['dradt'] * np.cos(np.radians(ephemeris['dec']))
        for k in ('delta', 'vmag', 'elongation'):
            ephemeris[k], _ = cheb.chebeval(tScaled, self.coeffs[k][subsetSegments][segmentIdx],
                                         interval=tInterval, doVelocity=False)
        return ephemeris

    def getEphemerides(self, time, objIds=None):
        """Find the ephemeris information for 'objIds' at 'time'.

        Parameters
        ----------
        time : float
            The time to calculate ephemeris positions.
        objIds : numpy.ndarray, optional
            The object ids for which to generate ephemerides. If None, then just uses all objects.

        Returns
        -------
        numpy.ndarray
            The ephemeris positions for all objects. Note that these may not be sorted in the same order as objIds.
        """
        ephemerides = {}
        if objIds is None:
            objMatch = np.ones(len(self.coeffs['objId']), dtype=bool)
            ephemerides['objId'] = np.unique(self.coeffs['objId'])
        else:
            if isinstance(objIds, str) or isinstance(objIds, int):
                objIds = np.array([objIds])
            objMatch = np.in1d(self.coeffs['objId'], objIds)
            ephemerides['objId'] = objIds
        ephemerides['time'] = np.zeros(len(ephemerides['objId']), float) + time
        for k in self.ephemerisKeys:
            ephemerides[k] = np.zeros(len(ephemerides['objId']), float)
        segments = np.where((self.coeffs['tStart'][objMatch] <= time) & (self.coeffs['tEnd'][objMatch] > time))[0]
        for i, segmentIdx in enumerate(segments):
            ephemeris = self._evalSegment(segmentIdx, time, objMatch)
            for k in self.ephemerisKeys:
                ephemerides[k][i] = ephemeris[k]
            ephemerides['objId'][i] = self.coeffs['objId'][objMatch][segmentIdx]
        if objIds is not None:
            if set(ephemerides['objId']) != set(objIds):
                raise ValueError('Expected to find match between objIds provided and ephemeride objIds, but did not')
        return ephemerides

    def findObjectsInCircle(self, raCen, decCen, dRaDt=None, dDecDt=None, radius=1.75):
        """Find the objects within radius of raCen/decCen."""
        #x, y, z =
        pass