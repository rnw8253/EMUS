# -*- coding: utf-8 -*-
"""
Example script with basic usage of the EMUS package.  The script follows the quickstart guide closely, with slight adjustments (for simplicity we have moved all plotting commands to the bottom of the script).
"""
import numpy as np                  
from emus import usutils as uu
from emus import emus, avar

import matplotlib
matplotlib.use('Qt4Agg')
import matplotlib.pyplot as plt

# Define Simulation Parameters
T = 310                             # Temperature in Kelvin
k_B = 1.9872041E-3                  # Boltzmann factor in kcal/mol
kT = k_B * T
meta_file = 'wham_meta.txt'         # Path to Meta File
dim = 1                             # 1 Dimensional CV space.
period = 360                        # Dihedral Angles periodicity

# Load data
psis, cv_trajs, neighbors = uu.data_from_WHAMmeta('wham_meta.txt',dim,T=T,k_B=k_B,period=period)

# Calculate the partition function for each window
z, F = emus.calculate_zs(psis,neighbors=neighbors,) 

# Calculate error in each z value from the first iteration.
zerr, zcontribs, ztaus  = avar.partition_functions(psis,z,F,iat_method='acor')

# Calculate the PMF
domain = ((-180.0,180.))            # Range of dihedral angle values
pmf = emus.calculate_pmf(cv_trajs,psis,domain,z,nbins=60,kT=kT)   # Calculate the pmf

# Calculate z using the MBAR iteration.
z_MBAR_1, F_MBAR_1 = emus.calculate_zs(psis,nMBAR=1)
z_MBAR_2, F_MBAR_2 = emus.calculate_zs(psis,nMBAR=2)
z_MBAR_5, F_MBAR_5 = emus.calculate_zs(psis,nMBAR=5)
z_MBAR_1k, F_MBAR_1k = emus.calculate_zs(psis,nMBAR=1000)
# Calculate new PMF
MBARpmf = emus.calculate_pmf(cv_trajs,psis,domain,nbins=60,z=z_MBAR_1k,kT=kT)

# Estimate probability of being in C7 ax basin
fdata =  [(traj>25) & (traj<100) for traj in cv_trajs]
# Calculate the probability and perform error analysis.
iat, probC7ax, probC7ax_contribs = avar.average_ratio(psis,z,F,fdata,iat_method='acor')
probC7ax_std = np.sqrt(np.sum(probC7ax_contribs))
# This command just calculates the probability, without error analysis.
#prob_C7ax = emus.calculate_obs(psis,z,fdata) # Just calculate the probability


### Data Output Section ###

# Plot the EMUS, MBAR pmfs.
centers = np.linspace(-177,177,60)  # Center of the histogram bins
plt.figure()
plt.plot(centers,pmf,label='EMUS PMF')
plt.plot(centers,MBARpmf,label='MBAR PMF')
plt.xlabel('$\psi$ dihedral angle')
plt.ylabel('Unitless FE')
plt.legend()
plt.title('EMUS and MBAR potentials of Mean Force')
plt.show()

# Plot the relative normalization constants as fxn of max iteration. 
plt.plot(-np.log(z),label="Iteration 0")
plt.plot(-np.log(z_MBAR_1),label="Iteration 1")
plt.plot(-np.log(z_MBAR_1k),label="Iteration 1k",linestyle='--')
plt.xlabel('Window Index')
plt.ylabel('Unitless Free Energy')
plt.title('Window Free Energies and MBAR Iter No.')
plt.legend(loc='upper left')
plt.show()

# Print the C7 ax basin probability
print "Probability of C7ax basin is %f +/- %f"% (probC7ax,probC7ax_std)

# err, taus = avar_zfe(psis,z,F,5,16)
print "Asymptotic coefficient of variation for each partition function:"
print np.sqrt(zerr)/z
