# -*- coding: utf-8 -*-
"""
Container for the primary EMUS routines.
"""
import numpy as np
import linalg as lm

def calc_obs(psis,z,f1data,f2data=None):
    """Estimates the value of an observable or ratio of observables.

    Parameters
    ----------
    psis : 3D data structure
        Data structure containing psi values.  See documentation in emus.py for a detailed explanation.
    z : 1D array
        Array containing the normalization constants
    f1data : 2D data structure
        Trajectory of observable in the numerator.  First dimension corresponds to the umbrella index and the second to the point in the trajectory.
    f2data : 2D data structure, optional
        Trajectory of observable in the denominator.  

    Returns
    -------
    avg : float
        The estimate of <f_1>/<f_2>.

    """
    f1avg = 0
    f2avg = 0
    for i,psi_i in enumerate(psis):
        psi_xi = np.array(psi_i)
        psi_i_sum = np.sum(psi_xi,axis=1)
        f1_i = np.array(f1data[i])/psi_i_sum
        if f2data is None:
            f2_i = 1./psi_i_sum
        else:
            f2_i = np.array(f2data[i])/psi_i_sum
        f1avg_i = np.average(f1_i)
        f2avg_i = np.average(f2_i)
        f1avg += z[i]*f1avg_i
        f2avg += z[i]*f2avg_i
    return f1avg / f2avg

def make_pmf(cv_trajs, psis, domain, z, nbins = 100,kT=1.):
    """Calculates the free energy surface for an umbrella sampling run.

    Parameters
    ----------
    cv_trajs : 2D data structure
        Data structure containing trajectories in the collective variable space.  See documentation in emus object for more detail.
    psis : 3D data structure
        Data structure containing psi values.  See documentation in emus object for a detailed explanation.
    domain : tuple
        Tuple containing the dimensions of the space over which to construct the pmf, e.g. (-180,180) or ((0,1),(-3.14,3.14)) z (1D array or list): Normalization constants for each state
    nbins : int or tuple, optional
        Number of bins to use.  If int, uses that many bins in each dimension.  If tuple, e.g. (100,20), uses 100 bins in the first dimension and 20 in the second.
    kT : float, optional
        Value of kT to scale the PMF by.  If not provided, set to 1.0

    Returns
    -------
    pmf : nd array
        Returns the potential of mean force as a d dimensional array, where d is the number of collective variables.

    """    
    if domain is None:
        raise NotImplementedError

    domain = np.asarray(domain)
    if len(np.shape(domain)) == 1:
        domain = np.reshape(domain,(1,len(domain)))
    ndims = np.shape(domain)[0]
    if type(nbins) is int: # Make nbins to an iterable in the 1d case.
        nbins = [nbins]*ndims
    domainwdth = domain[:,1] - domain[:,0]
    
    # Calculate the PMF
    hist = np.zeros(nbins)
    for i,xtraj_i in enumerate(cv_trajs):
        xtraj_i = (xtraj_i - domain[:,0])%domainwdth + domain[:,0]
        hist_i = np.zeros(nbins) # Histogram of umbrella i
        for n,coord in enumerate(xtraj_i):
            psi_i_n = psis[i][n]
            # We find the coordinate of the bin we land in.
            coordbins = (coord - domain[:,0])/domainwdth*nbins
            coordbins = tuple(coordbins.astype(int))
            weight = 1./np.sum(psi_i_n)
            hist_i[coordbins] += weight
        hist+=hist_i/len(xtraj_i)*z[i]
    pmf =-kT* np.log(hist)
    pmf -= min(pmf.flatten())

    # Calculate the centers of each histogram bin.
    return pmf


def emus_iter(psis, Avals=None, neighbors=None, return_iats = False,iat_method='ipce'):
    """Performs one step of the the EMUS iteration.
    
    Parameters
    ----------
    psis : 3D data structure
        Data structure containing psi values.  See documentation in emus.py for a detailed explanation.
    Avals : 2D matrix, optional
        Weights in front of :math:`\psi` in the overlap matrix.
    neighbors : 2D array, optional
        List showing which states neighbor which.  See neighbors_harmonic in usutils. 
    return_iats : bool, optional
        Whether or not to calculate integrated autocorrelation times of :math:`\psi_ii^*` for each window.
    iat_method : string, optional
        Routine to use for calculating said iats.  Accepts 'ipce', 'acor', and 'icce'.
    
    Returns
    -------
    z : 1D array
        Normalization constants for each state
    F : 2D array
        The overlap matrix constructed for the eigenproblem.
    iats : 1D array
        If return_iats chosen, returns the iats that have been estimated.
    """
    
    # Initialize variables
    L = len(psis) # Number of Windows
    F = np.zeros((L,L)) # Initialize F Matrix
    if return_iats:
        iats = np.ones(L)
        iatroutine=_get_iat_method(iat_method)
        
    
    if Avals is None:
        Avals = np.ones((L,L))
    
    if neighbors is None:
        neighbors = np.outer(np.ones(L),range(L)).astype(int)
        
    # Calculate Fi: for each i
    for i in xrange(L):
        Avi = Avals[i]
        nbrs_i = neighbors[i]
        psi_i = np.array(psis[i])
        A_nbs = Avi[nbrs_i]
        denom = np.dot(psi_i,A_nbs)
        for j_index, j in enumerate(nbrs_i):
            Ftraj = psi_i[:,j_index]/denom
            Fijunnorm = np.average(Ftraj)
            F[i,j] = Fijunnorm*Avi[i]
            if return_iats and (i == j):
                iat = iatroutine(Ftraj)[0]
                if not np.isnan(iat):
                    iats[i] = iat
    z = lm.stationary_distrib(F)
    if return_iats:
        return z, F, iats
    else:
        return z, F
		
def _get_iat_method(iatmethod):
    """Control routine for selecting the method used to calculate integrated
    autocorrelation times (iat)

    Parameters
    ----------
    iat_method : string, optional
        Routine to use for calculating said iats.  Accepts 'ipce', 'acor', and 'icce'.
    
    Returns
    -------
    iatroutine : function
        The function to be called to estimate the integrated autocorrelation time.

    """
    if iatmethod=='acor':
        from acor import acor
        iatroutine = acor
    elif iatmethod == 'ipce':
        from autocorrelation import ipce
        iatroutine = ipce
    elif iatmethod == 'icce':
        from autocorrelation import icce
        iatroutine = icce
    return iatroutine


