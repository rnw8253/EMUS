# -*- coding: utf-8 -*-
""" Container for the primary EMUS routines.

"""
import numpy as np
import linalg as lm
import autocorrelation as ac
from usutils import unpackNbrs
from _defaults import *

def calculate_obs(psis,z,g1data,g2data=None,neighbors=None,use_MBAR=True):
    """Estimates the value of an observable or ratio of observables.

    Parameters
    ----------
    psis : 3D data structure
        The values of the bias functions evaluated each window and timepoint.  See `datastructures <../datastructures.html#data-from-sampling>`__ for more information.
    z : 1D array
        Array containing the normalization constants
    g1data : 2D data structure
        Trajectory of observable in the numerator.  First dimension corresponds to the window index and the second to the point in the trajectory.
    g2data : 2D data structure, optional
        Trajectory of observable in the denominator.  
    neighbors : 2D array-like, optional
        List showing which windows neighbor which.  See neighbors_harmonic in usutils. 
    use_MBAR : bool, optional
        Use the MBAR estimator for the average of f.  If true (default), uses the estimator :math:`\sum_i < g / (\sum_j \psi_j/z_j) >_i`.  Otherwise, uses the first iteration EMUS estimator, :math:`\sum_i <g / \sum_j \psi_j >_i z_i`.

    Returns
    -------
    avg : float
        The estimate of :math:`<g_1>/<g_2>`.

    """
    # Clean the input and set defaults
    g1data = [np.array(g1i).flatten() for g1i in g1data]
    if g2data is None:
        g2data = [np.ones(np.shape(g1data_i)) for g1data_i in g1data]
        
    g1star = _calculate_win_avgs(psis,z,g1data,neighbors,use_MBAR)
    g2star = _calculate_win_avgs(psis,z,g2data,neighbors,use_MBAR)
    return np.dot(g1star,z)/np.dot(g2star,z)


def calculate_pmf(cv_trajs, psis, domain, z,neighbors=None, nbins = 100,kT=DEFAULT_KT, use_MBAR=True):
    """Calculates the free energy surface along a coordinate.

    Parameters
    ----------
    cv_trajs : 2D data structure
        Data structure containing trajectories in the collective variable space.  See `datastructures <../datastructures.html#data-from-sampling>`__ for more information.
    psis : 3D data structure
        The values of the bias functions evaluated each window and timepoint.  See `datastructures <../datastructures.html#data-from-sampling>`__ for more information.
    domain : tuple
        Tuple containing the dimensions of the space over which to construct the pmf, e.g. (-180,180) or ((0,1),(-3.14,3.14)) z (1D array or list): Normalization constants for each window
    z : 1D array
        Array containing the normalization constants
    neighbors : 2D array-like, optional
        List showing which windows neighbor which.  See neighbors_harmonic in usutils. 
    nbins : int or tuple, optional
        Number of bins to use.  If int, uses that many bins in each dimension.  If tuple, e.g. (100,20), uses 100 bins in the first dimension and 20 in the second.
    kT : float, optional
        Value of kT to scale the PMF by.  If not provided, set to 1.0
    use_MBAR : bool, optional
        Use the MBAR estimator for the average of f.  If true (default), uses the estimator :math:`\sum_i < g / (\sum_j \psi_j/z_j) >_i`.  Otherwise, uses the first iteration EMUS estimator, :math:`\sum_i <g / \sum_j \psi_j >_i z_i`.

    Returns
    -------
    pmf : ndarray
        Returns the potential of mean force as a d dimensional array, where d is the number of collective variables.
    edges : ndarray
        Edges of the histogram bins, in the syntax and order used by numpy's histogramdd method.

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
#        xtraj_i = (xtraj_i - domain[:,0])%domainwdth + domain[:,0]
        hist_i = np.zeros(nbins) # Histogram of window i
        if use_MBAR:
            L = len(psis) # Number of windows
            neighbors = np.outer(np.ones(L),range(L)).astype(int)
            nbrs_i = neighbors[i]
            z_nbr = z[nbrs_i]
            weights = 1./(z[i]*np.dot(psis[i],1./z_nbr))
            hist_i,edges = np.histogramdd(xtraj_i,nbins,domain,normed=False,weights=weights)
        else:
            psi_sum = np.sum(psis[i],axis=1)
            hist_i,edges = np.histogramdd(xtraj_i,nbins,domain,normed=False,weights=1./psi_sum)
            hist_i /= len(xtraj_i)
#        for n,coord in enumerate(xtraj_i):
#            psi_i_n = psis[i][n]
#            # We find the coordinate of the bin we land in.
#            coordbins = (coord - domain[:,0])/domainwdth*nbins
#            coordbins = np.array(coordbins.astype(int))
#            weight = 1./np.sum(psi_i_n)
#            if ((coordbins >= 0).all() and (coordbins < nbins).all()):
#                hist_i[coordbins] += weight
        hist+=hist_i/len(xtraj_i)*z[i]
    pmf =-kT* np.log(hist)
    pmf -= min(pmf.flatten())

    return pmf,edges

def calculate_zs(psis,neighbors=None,nMBAR=0,tol=DEFAULT_MBAR_TOL,use_iats=False,iat_method=DEFAULT_IAT):
    """Calculates the normalization constants for the windows.

    Parameters
    ----------
    nMBAR : int, optional (default 0)
         Maximum number of MBAR iterations to perform.
    tol : float, optional (see _defaults.py for default)
        If the relative residual falls beneath the tolerance, the MBAR iteration is truncated.
    use_iats : bool, optional
        If true, estimate integrated autocorrelation time in each MBAR iteration.  Likely unnecessary unless dynamics are expected to be drastically different in each window. If iats is provided, the iteration will use those rather than estimating them in each step.
    iat_method : string, optional
        Routine to use for calculating integrated autocorrelation times.  Currently accepts DEFAULT_IAT, 'acor', and 'icce'.
    
    Returns
    -------
    z : 1D array
        Values for the Normalization constant in each window.
    F : 2D array
        Matrix to take the eigenvalue of for MBAR.
    iats : 1D array
        Estimated values of the autocorrelation time.  Only returned if use_iats is true.

    """
    L = len(psis) # Number of windows
    Npnts = np.array([len(psis_i) for psis_i in psis]).astype('float')
    Npnts /= np.max(Npnts)

    if use_iats:
        z,F,iats = emus_iter(psis,neighbors=neighbors,return_iats=use_iats,iat_method=iat_method)
    else:
        z,F = emus_iter(psis,neighbors=neighbors,return_iats=use_iats,iat_method=iat_method)
        iats = np.ones(z.shape)

    # we perform the self-consistent polishing iteration
    for n in xrange(nMBAR):
        z_old = z
        Apart = Npnts/z_old
        Amat = np.outer(np.ones(L),Apart)
        Amat /= np.outer(np.ones(L),iats)
        if use_iats:
            z, F, iats = emus_iter(psis,Amat,neighbors=neighbors,return_iats=True,iat_method=iat_method)
        else:
            z, F = emus_iter(psis,Amat,neighbors=neighbors)
        # Check if we have converged.	
        if np.max(np.abs(z-z_old)/z_old) < tol:
            break
                            
    if use_iats:
        return z, F, iats
    else:
        return z, F


def emus_iter(psis, Avals=None, neighbors=None, return_iats = False,iat_method=DEFAULT_IAT):
    """Performs one step of the the EMUS iteration.
    
    Parameters
    ----------
    psis : 3D data structure
        The values of the bias functions evaluated each window and timepoint.  See `datastructures <../datastructures.html#data-from-sampling>`__ for more information.
    Avals : 2D array-like, optional
        Weights in front of :math:`\psi` in the overlap matrix.
    neighbors : 2D array-like, optional
        List showing which windows neighbor which.  See neighbors_harmonic in usutils. 
    return_iats : bool, optional
        Whether or not to calculate integrated autocorrelation times of :math:`\psi_ii^*` for each window.
    iat_method : string, optional
        Routine to use for calculating said iats.  Accepts 'ipce', 'acor', and 'icce'.
    
    Returns
    -------
    z : 1D array
        Normalization constants for each window
    F : 2D array
        The overlap matrix constructed for the eigenproblem.
    iats : 1D array
        If return_iats chosen, returns the iats that have been estimated.

    """
    
    # Initialize variables
    L = len(psis) # Number of windows
    F = np.zeros((L,L)) # Initialize F Matrix
    # Take care of defaults..
    if return_iats:
        iats = np.ones(L)
        iatroutine = ac._get_iat_method(iat_method)
    if Avals is None:
        Avals = np.ones((L,L))
    if neighbors is None:
        neighbors = np.outer(np.ones(L),range(L)).astype(int)
        
    for i in xrange(L):
        nbrs_i = neighbors[i]
        A_nbs = Avals[i][nbrs_i]
        nbr_index = list(nbrs_i).index(i)
        Fi_out = calculate_Fi(psis[i],nbr_index,A_nbs,return_iats)
        if return_iats:
            Fi, trajs = Fi_out
            iats[i] = iatroutine(trajs[nbr_index])[0]
        else:
            Fi = Fi_out
        # Unpack the Neighbor list
        F[i] = unpackNbrs(Fi,nbrs_i,L)
#    np.save('Fmat',F)
    z = lm.stationary_distrib(F)
    if return_iats:
        return z, F, iats
    else:
        return z, F

def calculate_Fi(psi_i, i, Avals_i=None, return_trajs=False):
    """Calculates the values of a single row in the F matrix.  If neighborlists are being used, psi_i, and Avals_i should be the neighborlisted data structure, and the row will be need to be unpacked using the neighborlist.
    
    Parameters
    ----------
    psi_i : 2D array-like
        Values of :math:`\psi` collected in window i.  The j'th column corresponds to the j'th neighboring window.
    i : int
        Index of the window where the data was collected.
    Avals_i : 1D array-like
        Weights in front of :math:`\psi_{ij}` in the overlap matrix.
    return_trajs : bool, optional
        Whether or not to return the trajectories that are averaged to calculate the values of F.  These can be useful for estimating autocorrelation times and performing error analysis.
    
    Returns
    -------
    Fi : 1D array 
        The (neighborlisted) row in the F matrix
    trajs : 2D array, optional
        If return_trajs is True, returns the trajectories used in calculating the values of F
    
    """
    # Setup
    L = np.shape(psi_i)[1] # Number of neighboring windows
    Fi = np.zeros(L)
    # Take care of defaults
    if Avals_i is None:
        Avals_i = np.ones(L)
     
    psi_i = np.array(psi_i)
    denom = np.dot(psi_i,Avals_i) 
    if return_trajs:
        trajs = np.zeros(psi_i.shape)
    for j in xrange(L):
        Ftraj = psi_i[:,j]/denom # traj \psi_j/{\sum_k \psi_k A_k}
        Fi[j] = np.average(Ftraj)
        Fi[j] *= Avals_i[i]
        if return_trajs:
            trajs[:,j] = Ftraj
    if return_trajs:
        return Fi, trajs
    else:
        return Fi
    
def _calculate_win_avgs(psis,z,gdata,neighbors=None,use_MBAR=True):
    """Helper method estimating the scaled averages in each window.

    Parameters
    ----------
    psis : 3D data structure
        The values of the bias functions evaluated each window and timepoint.  See `datastructures <../datastructures.html#data-from-sampling>`__ for more information.
    z : ndarray
        Array containing the normalization constants
    gdata : 2D data structure
        Trajectory of observable in the numerator.  First dimension corresponds to the window index and the second to the point in the trajectory.
    neighbors : 2D array-like, optional
        List showing which windows neighbor which.  See neighbors_harmonic in usutils. 
    use_MBAR : bool, optional
        Use the MBAR estimator for the average of f.  If true (default), uses the estimator :math:`\sum_i < g / (\sum_j \psi_j/z_j) >_i`.  Otherwise, uses the first iteration EMUS estimator, :math:`\sum_i <g / \sum_j \psi_j >_i z_i`.

    Returns
    -------
    gstar : 1D array
        Array where element i is the estimate of :math:`<g^*>` in window i.

    """
    gstar = []
    if use_MBAR:
        # Initialize neighbors if they don't exist.
        L = len(psis) # Number of windows
        if neighbors is None:
            neighbors = np.outer(np.ones(L),range(L)).astype(int)
        for i,psi_i in enumerate(psis):
            nbrs_i = neighbors[i]
            z_nbr = z[nbrs_i]
            denom_i = 1./np.dot(psi_i,1./z_nbr)
            gstar.append(np.average(gdata[i]*denom_i)/z[i])
    else:
        for i,psi_i in enumerate(psis):
            denom_i = 1./np.sum(psi_i,axis=1)
            gstar.append(np.average(gdata[i]*denom_i))
    return np.array(gstar)

