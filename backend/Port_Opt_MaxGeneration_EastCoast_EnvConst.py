4#This code compute the optimal portfolio for wave wind and ocean current resources
#Considering transmission system costs, CAPEX and OPEX of each technology and its generation availability in a given region

#The objective function is the maximization of the total generation of the portfolio, costraint to limits in the portfolio LCOE, maximum
#Capacity of the transmission system, maximum number of turbines per site location, and maxmimum radious of the energy collection system.

#The model also takes into considering curtailment, and the possibility of chosing from a limited number of turbine designs.

#env Gurobi
import numpy as np
from pyomo.environ import *
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm
import sys
import os
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from  GetIdxInOutRadious import GetIdxOutRadious, GetIdxInRadious_Simple
from Port_Opt_Tools import GetOverlaps_Idx_Area

windCostScaling = 1.0 #0.8, 1.0, 1.2 for sensitivity analysis +-20%
kiteCostScaling = 1.0 #0.8, 1.0, 1.2 ""
waveCostScaling = 1.0
coaxialCostScaling = 1.0 #0.8, 1.0, 1.2 ""
tidalCostScaling = 1.0 #0.8, 1.0, 1.2 ""
transmissionCostScaling = 1.0 #0.8, 1.0, 1.2 ""


# =========================================================================
# Exclusion Zone Functions (Environmental & Shipping)
# =========================================================================

def compute_excluded_sites(tech_latlong, tech_resolution_degrees, exclusion_points):
    """Determine which technology sites overlap with exclusion zone points.

    A technology site is excluded if any exclusion point falls within the
    site's grid cell (half-resolution in each direction from the center).

    Parameters
    ----------
    tech_latlong : Nx2 array of [lat, lon] for each technology site
    tech_resolution_degrees : N-length array or scalar of grid cell size (degrees).
                              If negative or zero, spacing is estimated from data.
    exclusion_points : Mx2 array of [lat, lon] exclusion zone coordinates

    Returns
    -------
    excluded_indices : set of int — site indices that overlap with exclusion zones
    """
    if len(tech_latlong) == 0 or len(exclusion_points) == 0:
        return set()

    # Determine the half-cell size for spatial matching
    if np.isscalar(tech_resolution_degrees):
        half_res = abs(float(tech_resolution_degrees)) / 2.0
    elif len(tech_resolution_degrees) > 0:
        half_res = abs(float(tech_resolution_degrees[0])) / 2.0
    else:
        half_res = 0.0

    # Handle invalid resolution (e.g., -1.0) by estimating from data spacing
    if half_res <= 0.001:
        unique_lats = np.sort(np.unique(tech_latlong[:, 0]))
        if len(unique_lats) > 1:
            diffs = np.diff(unique_lats)
            diffs = diffs[diffs > 0.001]
            if len(diffs) > 0:
                half_res = np.median(diffs) / 2.0
            else:
                half_res = 0.04
        else:
            half_res = 0.04  # fallback ~0.08deg / 2
        print(f"    Resolution estimated from data: {half_res*2:.4f} deg")

    excluded = set()
    ex_lat = exclusion_points[:, 0]
    ex_lon = exclusion_points[:, 1]

    for i in range(len(tech_latlong)):
        lat_i, lon_i = tech_latlong[i]
        mask = (np.abs(ex_lat - lat_i) <= half_res) & (np.abs(ex_lon - lon_i) <= half_res)
        if np.any(mask):
            excluded.add(i)

    return excluded


def _build_exclusion_for_all_techs(InputDir, exclusion_points, label="Exclusion"):
    """Compute excluded site indices for all technologies given exclusion points.

    Parameters
    ----------
    InputDir : dict — prepared optimization inputs from PreparePotOptInputs
    exclusion_points : Mx2 array of [lat, lon] exclusion zone coordinates
    label : str — label for print output

    Returns
    -------
    excluded_dict : dict mapping tech name -> set of excluded site indices
    """
    if len(exclusion_points) == 0:
        print(f"  {label}: No exclusion points — no sites excluded.")
        return {}

    print(f"  {label}: {len(exclusion_points):,} exclusion points")

    excluded_dict = {}
    tech_configs = [
        ("Wind", "WindLatLong", "WindResolutionDegrees"),
        ("Wave", "WaveLatLong", "WaveResolutionDegrees"),
        ("Kite", "KiteLatLong", "KiteResolutionDegrees"),
        ("Coaxial", "CoaxialLatLong", "CoaxialResolutionDegrees"),
        ("Tidal", "TidalLatLong", "TidalResolutionDegrees"),
    ]

    total_excluded = 0
    for tech_name, ll_key, res_key in tech_configs:
        n_sites = len(InputDir[ll_key])
        if n_sites == 0:
            excluded_dict[tech_name] = set()
            continue

        excluded = compute_excluded_sites(
            InputDir[ll_key], InputDir[res_key], exclusion_points)

        excluded_dict[tech_name] = excluded
        pct = 100.0 * len(excluded) / n_sites if n_sites > 0 else 0
        print(f"    {tech_name}: {len(excluded):,} / {n_sites:,} sites excluded ({pct:.1f}%)")
        total_excluded += len(excluded)

    print(f"  {label} total sites excluded: {total_excluded:,}")
    return excluded_dict


def load_environmental_exclusions(hapc_path=None, prohibited_path=None, restricted_path=None):
    """Load environmental exclusion zone data and combine into a single [lat, lon] array.

    Each file is tab-delimited with columns: lat, long, Type

    Parameters
    ----------
    hapc_path : str or None — path to HAPC Hard Bottom Habitat file
    prohibited_path : str or None — path to Prohibited MPAs file
    restricted_path : str or None — path to Restricted De Facto MPAs file

    Returns
    -------
    combined : Nx2 array of [lat, lon] for all active exclusion zones
    """
    all_points = []
    for label, path in [('HAPC Hard Bottom', hapc_path),
                         ('Prohibited MPAs', prohibited_path),
                         ('Restricted De Facto MPAs', restricted_path)]:
        if path is not None and os.path.exists(path):
            data = pd.read_csv(path, sep='\t')
            pts = data[['lat', 'long']].values
            all_points.append(pts)
            print(f"    Loaded {label}: {len(pts):,} points")
        elif path is not None:
            print(f"    WARNING: File not found — {path}")

    if len(all_points) == 0:
        return np.empty((0, 2))

    return np.vstack(all_points)


def load_shipping_exclusion(shipping_path):
    """Load shipping traffic no-development zone data.

    File is tab-delimited with columns: X (longitude), Y (latitude), Type
    Note: column order is X=lon, Y=lat — reversed from environmental files.

    Parameters
    ----------
    shipping_path : str — path to shipping exclusion file

    Returns
    -------
    points : Nx2 array of [lat, lon] coordinates (converted to standard convention)
    """
    if shipping_path is None or not os.path.exists(shipping_path):
        if shipping_path is not None:
            print(f"    WARNING: File not found — {shipping_path}")
        return np.empty((0, 2))

    data = pd.read_csv(shipping_path, sep='\t')
    # Shipping file uses X=longitude, Y=latitude — convert to [lat, lon]
    points = data[['Y', 'X']].values
    print(f"    Loaded Shipping Exclusion: {len(points):,} points")
    return points


def PreparePotOptInputs(PathWindDesigns, PathWaveDesigns, PathKiteDesigns, PathCoaxialDesigns, PathTidalDesigns, PathTransmissionDesign, LCOE_RANGE=range(200,30,-2)\
    ,Max_CollectionRadious=30, MaxDesignsWind=1, MaxDesignsWave=1, MaxDesignsKite=1, MaxDesignsCoaxial=1, MaxDesignsTidal=1,
    MinNumWindTurb=0, MinNumWaveTurb=0, MinNumKiteTrub=0, MinNumCoaxialTurb=0, MinNumTidalTurb=0,
    WindTurbinesPerSite=4, KiteTurbinesPerSite=390, WaveTurbinesPerSite=300, CoaxialTurbinesPerSite=390, TidalTurbinesPerSite=200):
    
    
    # WindTurbinesPerSite= 4 [MW/Km2]
    # KiteTurbinesPerSite= 25 per 2x2km cells, but the simulation is running on 0.08x0.08 degrees cells (as base resolution)
    # KiteTurbinesPerSite= 390 per 9x7km cells
    # WaveTurbinesPerSite=  1/15degees , from pelamis 12.5 devices per km2. This would be +500 devices, using 300 for now

    #WindTurbinesPerSite: Number of turbines per site location based on the initial wind resolution from NREL
    #KiteTurbinesPerSite: Number of turbines per site location based on the initial kite resolution from where the data was obtained (HYCOM, MABSAB)
    #WaveTurbinesPerSite: Number of turbines per site location based on the initial wave resolution from where the data was obtained (WWIII)  
    
    #Function to prepare the inputs for the optimization
    #All portfolio data needs to be at the same time resolution and range, unless the portfolio path is empty eg. PathWaveDesigns=[]
    # LCOE_RANGE=range(200,30,-2) #Max LCOE limits investigated
    # Max_CollectionRadious=30 #Radious for the energy collection system

    # TimeList will be set from the first technology that has data
    TimeList = None

    WindEnergy, WindLatLong, AnnualizedCostWind, MaxNumWindPerSite, WindDesign, TimeWindData,\
    RatedPowerWindTurbine, WindResolutionDegrees, WindResolutionKm = list(), list(), list(), list(), list(), list(), list(), list(), list()
    
    KiteEnergy, KiteLatLong, AnnualizedCostKite, MaxNumKitePerSite, KiteDesign, TimeKiteData,\
    RatedPowerKiteTurbine, KiteResolutionDegrees, KiteResolutionKm = list(), list(), list(), list(), list(), list(), list(), list(), list()
    
    WaveEnergy, WaveLatLong, AnnualizedCostWave, MaxNumWavePerSite, WaveDesign, TimeWaveData,\
    RatedPowerWaveTurbine, WaveResolutionDegrees, WaveResolutionKm = list(), list(), list(), list(), list(), list(), list(), list(), list()
    
    CoaxialEnergy, CoaxialLatLong, AnnualizedCostCoaxial, MaxNumCoaxialPerSite, CoaxialDesign, TimeCoaxialData,\
    RatedPowerCoaxialTurbine, CoaxialResolutionDegrees, CoaxialResolutionKm = list(), list(), list(), list(), list(), list(), list(), list(), list()
    
    TidalEnergy, TidalLatLong, AnnualizedCostTidal, MaxNumTidalPerSite, TidalDesign, TimeTidalData,\
    RatedPowerTidalTurbine, TidalResolutionDegrees, TidalResolutionKm = list(), list(), list(), list(), list(), list(), list(), list(), list()
    
    for i in range(len(PathWindDesigns)):
        Data=np.load(PathWindDesigns[i],allow_pickle=True)
        if i==0:
            
            WindEnergy=Data['Energy_pu']
            WindLatLong=Data['LatLong']
            AnnualizedCostWind=Data['AnnualizedCost']
            AnnualizedCostWind=AnnualizedCostWind*windCostScaling

            WindDesign=np.array([i]*len(Data["NumberOfCellsPerSite"]))
            TimeWindData=Data["TimeList"]
            RatedPowerWindTurbine=np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))
            WindResolutionDegrees=np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))
            WindResolutionKm=np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))
            
            # ORIGINAL: Computed max turbines from density (MW/km²) and grid cell aggregation.
            # WindTurbinesPerSite was a density (MW/km²), multiplied by ~4 km² cell area,
            # divided by turbine rated power to get devices per original grid cell.
            # Then multiplied by NumberOfCellsPerSite (how many raw grid cells were
            # aggregated into this site during preprocessing) to get total devices allowed.
            # This approach broke down after spatial resampling set NumberOfCellsPerSite=1.
            #TubPerSite=np.max([WindTurbinesPerSite*4/float(Data["RatedPower"]),1])
            #MaxNumWindPerSite=Data["NumberOfCellsPerSite"]*TubPerSite
            
            # NEW: WindTurbinesPerSite from config is used directly as the max devices per site.
            MaxNumWindPerSite=np.array([WindTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))
            
            if TimeList is None:
                TimeList=TimeWindData
            
            
        else:
            WindEnergy=np.concatenate((WindEnergy,Data['Energy_pu']),axis=1)
            WindLatLong=np.concatenate((WindLatLong,Data['LatLong']))
            AnnualizedCostWind=np.concatenate((AnnualizedCostWind,Data['AnnualizedCost']*windCostScaling))
            
            WindDesign=np.concatenate((WindDesign,[i]*len(Data["NumberOfCellsPerSite"])))
            RatedPowerWindTurbine=np.concatenate((RatedPowerWindTurbine,np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))))
            WindResolutionDegrees=np.concatenate((WindResolutionDegrees, np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))))
            WindResolutionKm=np.concatenate((WindResolutionKm, np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))))

            # ORIGINAL: Same density-based calculation for additional wind designs.
            #TubPerSite=np.max([(WindTurbinesPerSite*4/float(Data["RatedPower"])),1])     
            #MaxNumWindPerSite=np.concatenate((MaxNumWindPerSite,Data["NumberOfCellsPerSite"]*TubPerSite))
            
            # NEW: Direct config value.
            MaxNumWindPerSite=np.concatenate((MaxNumWindPerSite,np.array([WindTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))))
            
        Data.close()
        
    #Kite Data
    for i in range(len(PathKiteDesigns)):
        Data=np.load(PathKiteDesigns[i],allow_pickle=True)
        if i==0:
            KiteEnergy=Data['Energy_pu']
            KiteLatLong=Data['LatLong']
            AnnualizedCostKite=Data['AnnualizedCost']
            AnnualizedCostKite=AnnualizedCostKite*kiteCostScaling #Sensitivity analysis on costs

            # ORIGINAL: Multiplied device density by NumberOfCellsPerSite, which tracked
            # how many raw grid cells (from HYCOM/MABSAB source data) were aggregated
            # into each site. After spatial resampling, NumberOfCellsPerSite=1, making
            # this multiplication ineffective.
            #MaxNumKitePerSite=Data["NumberOfCellsPerSite"]*KiteTurbinesPerSite
            
            # NEW: KiteTurbinesPerSite from config is used directly as the max devices per site.
            MaxNumKitePerSite=np.array([KiteTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))
            KiteDesign=np.array([i]*len(Data["NumberOfCellsPerSite"]))
            TimeKiteData=Data["TimeList"]
            RatedPowerKiteTurbine=np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))
            KiteResolutionDegrees=np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))
            KiteResolutionKm=np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))
            
            if TimeList is None:
                TimeList=TimeKiteData
            
            
        else:
            KiteEnergy=np.concatenate((KiteEnergy,Data['Energy_pu']),axis=1)
            KiteLatLong=np.concatenate((KiteLatLong,Data['LatLong']))
            print(Data['AnnualizedCost'])
            AnnualizedCostKite=np.concatenate((AnnualizedCostKite,Data['AnnualizedCost']*kiteCostScaling))
            # ORIGINAL: Same cell-aggregation scaling for additional kite designs.
            #MaxNumKitePerSite=np.concatenate((MaxNumKitePerSite,KiteTurbinesPerSite*Data["NumberOfCellsPerSite"]))
            
            # NEW: Direct config value.
            MaxNumKitePerSite=np.concatenate((MaxNumKitePerSite,np.array([KiteTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))))
            KiteDesign=np.concatenate((KiteDesign,[i]*len(Data["NumberOfCellsPerSite"])))
            RatedPowerKiteTurbine=np.concatenate((RatedPowerKiteTurbine,np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))))
            KiteResolutionDegrees=np.concatenate((KiteResolutionDegrees, np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))))
            KiteResolutionKm=np.concatenate((KiteResolutionKm, np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))))
            
        Data.close()
        
    #Wave Data
    for i in range(len(PathWaveDesigns)):
        Data=np.load(PathWaveDesigns[i],allow_pickle=True)
        if i==0:
            WaveEnergy=Data['Energy_pu']
            WaveLatLong=Data['LatLong']
            AnnualizedCostWave=Data['AnnualizedCost']
            AnnualizedCostWave=AnnualizedCostWave*waveCostScaling #Sensitivity analysis on costs
            # ORIGINAL: Multiplied device density by NumberOfCellsPerSite, which tracked
            # how many raw WWIII grid cells were aggregated into each site. After spatial
            # resampling to a uniform grid, NumberOfCellsPerSite=1, so this always
            # collapsed to just WaveTurbinesPerSite.
            #MaxNumWavePerSite=Data["NumberOfCellsPerSite"]*WaveTurbinesPerSite
            
            # NEW: WaveTurbinesPerSite from config is used directly as the max devices per site.
            MaxNumWavePerSite=np.array([WaveTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))
            WaveDesign=np.array([i]*len(Data["NumberOfCellsPerSite"]))
            TimeWaveData=Data["TimeList"]
            RatedPowerWaveTurbine=np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))  
            WaveResolutionDegrees=np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))
            WaveResolutionKm=np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))
            
            if TimeList is None:
                TimeList=TimeWaveData
            
        else:
            WaveEnergy=np.concatenate((WaveEnergy,Data['Energy_pu']),axis=1)
            WaveLatLong=np.concatenate((WaveLatLong,Data['LatLong']))
            AnnualizedCostWave=np.concatenate((AnnualizedCostWave,Data['AnnualizedCost']*waveCostScaling))
            # ORIGINAL: Same cell-aggregation scaling for additional wave designs.
            #MaxNumWavePerSite=np.concatenate((MaxNumWavePerSite,WaveTurbinesPerSite*Data["NumberOfCellsPerSite"]))
            
            # NEW: Direct config value.
            MaxNumWavePerSite=np.concatenate((MaxNumWavePerSite,np.array([WaveTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))))
            WaveDesign=np.concatenate((WaveDesign,[i]*len(Data["NumberOfCellsPerSite"])))
            RatedPowerWaveTurbine=np.concatenate((RatedPowerWaveTurbine,np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))))
            WaveResolutionDegrees=np.concatenate((WaveResolutionDegrees, np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))))
            WaveResolutionKm=np.concatenate((WaveResolutionKm, np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))))

    #Coaxial Data
    for i in range(len(PathCoaxialDesigns)):
        Data=np.load(PathCoaxialDesigns[i],allow_pickle=True)
        if i==0:
            CoaxialEnergy=Data['Energy_pu']
            CoaxialLatLong=Data['LatLong']
            AnnualizedCostCoaxial=Data['AnnualizedCost']
            AnnualizedCostCoaxial=AnnualizedCostCoaxial*coaxialCostScaling
            MaxNumCoaxialPerSite=np.array([CoaxialTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))
            CoaxialDesign=np.array([i]*len(Data["NumberOfCellsPerSite"]))
            TimeCoaxialData=Data["TimeList"]
            RatedPowerCoaxialTurbine=np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))
            CoaxialResolutionDegrees=np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))
            CoaxialResolutionKm=np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))
            
            if TimeList is None:
                TimeList=TimeCoaxialData
            
        else:
            CoaxialEnergy=np.concatenate((CoaxialEnergy,Data['Energy_pu']),axis=1)
            CoaxialLatLong=np.concatenate((CoaxialLatLong,Data['LatLong']))
            AnnualizedCostCoaxial=np.concatenate((AnnualizedCostCoaxial,Data['AnnualizedCost']*coaxialCostScaling))
            MaxNumCoaxialPerSite=np.concatenate((MaxNumCoaxialPerSite,np.array([CoaxialTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))))
            CoaxialDesign=np.concatenate((CoaxialDesign,[i]*len(Data["NumberOfCellsPerSite"])))
            RatedPowerCoaxialTurbine=np.concatenate((RatedPowerCoaxialTurbine,np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))))
            CoaxialResolutionDegrees=np.concatenate((CoaxialResolutionDegrees, np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))))
            CoaxialResolutionKm=np.concatenate((CoaxialResolutionKm, np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))))
        Data.close()

    #Tidal Data
    for i in range(len(PathTidalDesigns)):
        Data=np.load(PathTidalDesigns[i],allow_pickle=True)
        if i==0:
            TidalEnergy=Data['Energy_pu']
            TidalLatLong=Data['LatLong']
            AnnualizedCostTidal=Data['AnnualizedCost']
            AnnualizedCostTidal=AnnualizedCostTidal*tidalCostScaling
            MaxNumTidalPerSite=np.array([TidalTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))
            TidalDesign=np.array([i]*len(Data["NumberOfCellsPerSite"]))
            TimeTidalData=Data["TimeList"]
            RatedPowerTidalTurbine=np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))
            TidalResolutionDegrees=np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))
            TidalResolutionKm=np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))
            
            if TimeList is None:
                TimeList=TimeTidalData
            
        else:
            TidalEnergy=np.concatenate((TidalEnergy,Data['Energy_pu']),axis=1)
            TidalLatLong=np.concatenate((TidalLatLong,Data['LatLong']))
            AnnualizedCostTidal=np.concatenate((AnnualizedCostTidal,Data['AnnualizedCost']*tidalCostScaling))
            MaxNumTidalPerSite=np.concatenate((MaxNumTidalPerSite,np.array([TidalTurbinesPerSite]*len(Data["NumberOfCellsPerSite"]))))
            TidalDesign=np.concatenate((TidalDesign,[i]*len(Data["NumberOfCellsPerSite"])))
            RatedPowerTidalTurbine=np.concatenate((RatedPowerTidalTurbine,np.array([float(Data["RatedPower"])]*len(Data["NumberOfCellsPerSite"]))))
            TidalResolutionDegrees=np.concatenate((TidalResolutionDegrees, np.array([float(Data["ResolutionDegrees"])]*len(Data["NumberOfCellsPerSite"]))))
            TidalResolutionKm=np.concatenate((TidalResolutionKm, np.array([float(Data["ResolutionKm"])]*len(Data["NumberOfCellsPerSite"]))))
        Data.close()

    # #Verify if all the data is at the same time resolution and range
    # if len(PathWindDesigns)!=0 and len(PathKiteDesigns)!=0:
        
    #     if np.all(TimeWindData==TimeKiteData)==False:
    #         return print("Time resolution of the wind, and wave data is not the same")
        
    # if len(PathWindDesigns)!=0 and len(PathWaveDesigns)!=0:
    #     if  np.all(TimeWindData==TimeWaveData)==False:
    #         return print("Time resolution of the wind, and wave data is not the same")

    # if len(PathKiteDesigns)!=0 and len(PathWaveDesigns)!=0:
    #     if  np.all(TimeKiteData==TimeWaveData)==False:
    #         return print("Time resolution of the kite, and wave data is not the same")

    # Validate that at least one technology has been specified
    if TimeList is None:
        raise ValueError("At least one technology (wind, wave, kite, coaxial, or tidal) must be specified with design paths.")
    
    # ---------------------------------------------------------------------------
    # Temporal resolution alignment
    # Different technologies may have different time resolutions (e.g., wind=1hr,
    # wave=3hr). Detect the coarsest resolution from loaded TimeLists and 
    # downsample finer-resolution technologies to match by striding.
    # ---------------------------------------------------------------------------
    
    # Collect (timestep_count, TimeList, label) for each loaded technology
    _time_info = []
    if len(PathWindDesigns) > 0:
        _time_info.append((WindEnergy.shape[0], TimeWindData, "Wind"))
    if len(PathKiteDesigns) > 0:
        _time_info.append((KiteEnergy.shape[0], TimeKiteData, "Kite"))
    if len(PathWaveDesigns) > 0:
        _time_info.append((WaveEnergy.shape[0], TimeWaveData, "Wave"))
    if len(PathCoaxialDesigns) > 0:
        _time_info.append((CoaxialEnergy.shape[0], TimeCoaxialData, "Coaxial"))
    if len(PathTidalDesigns) > 0:
        _time_info.append((TidalEnergy.shape[0], TimeTidalData, "Tidal"))
    
    # Find the coarsest resolution (fewest timesteps = largest time step)
    coarsest_count = min(info[0] for info in _time_info)
    
    # Downsample finer-resolution technologies to the coarsest, aligning by
    # TIMESTAMP (not array position) so phase/start offsets can't silently mispair.
    import pandas as _pd

    # target timestamps = the coarsest technology's TimeList
    _target = None
    for count, tdata, label in _time_info:
        if count == coarsest_count:
            _target = _pd.to_datetime(_pd.Series(list(tdata))).values  # datetime64[ns]
            break
    _target_set = set(_target.tolist())

    def _align_indices(tdata, count):
        """Rows of a fine-cadence tech that match the coarse timestamps.
        Falls back to positional stride if timestamps don't line up."""
        fine = _pd.to_datetime(_pd.Series(list(tdata))).values
        mask = np.isin(fine, _target)
        if int(mask.sum()) == coarsest_count:
            return np.flatnonzero(mask), True          # clean timestamp match
        # fallback: positional stride (keep 1, skip ratio-1), warn about phase risk
        ratio = max(count // coarsest_count, 1)
        idx = np.arange(0, count, ratio)[:coarsest_count]
        return idx, False

    for count, tdata, label in _time_info:
        if count > coarsest_count:
            idx, matched = _align_indices(tdata, count)
            if matched:
                print(f"  Aligning {label}: {count} -> {coarsest_count} timesteps by timestamp")
            else:
                print(f"  WARNING: {label} timestamps do not match the coarsest technology's "
                      f"clock (start {tdata[0]} vs {_target[0]}). Falling back to positional "
                      f"stride — verify the two series share a start time before trusting results.")
                print(f"  Downsampling {label} from {count} to {len(idx)} timesteps (stride)")
            if label == "Wind":
                WindEnergy = WindEnergy[idx, :];        TimeWindData = np.asarray(TimeWindData)[idx]
            elif label == "Kite":
                KiteEnergy = KiteEnergy[idx, :];        TimeKiteData = np.asarray(TimeKiteData)[idx]
            elif label == "Wave":
                WaveEnergy = WaveEnergy[idx, :];        TimeWaveData = np.asarray(TimeWaveData)[idx]
            elif label == "Coaxial":
                CoaxialEnergy = CoaxialEnergy[idx, :];  TimeCoaxialData = np.asarray(TimeCoaxialData)[idx]
            elif label == "Tidal":
                TidalEnergy = TidalEnergy[idx, :];      TimeTidalData = np.asarray(TimeTidalData)[idx]

    # Set TimeList from the coarsest technology
    for count, tdata, label in _time_info:
        if count == coarsest_count:
            TimeList = tdata
            break

    # Safety net: with timestamp alignment all techs now share the coarse timestamps,
    # so counts match and this trim is a no-op; it only guards a stride-fallback off-by-one.
    timestep_counts = []
    if len(PathWindDesigns) > 0:    timestep_counts.append(WindEnergy.shape[0])
    if len(PathKiteDesigns) > 0:    timestep_counts.append(KiteEnergy.shape[0])
    if len(PathWaveDesigns) > 0:    timestep_counts.append(WaveEnergy.shape[0])
    if len(PathCoaxialDesigns) > 0: timestep_counts.append(CoaxialEnergy.shape[0])
    if len(PathTidalDesigns) > 0:   timestep_counts.append(TidalEnergy.shape[0])

    NumTimeSteps = min(timestep_counts)
    TimeList = TimeList[:NumTimeSteps]
    if len(PathWindDesigns) > 0:    WindEnergy = WindEnergy[:NumTimeSteps, :]
    if len(PathKiteDesigns) > 0:    KiteEnergy = KiteEnergy[:NumTimeSteps, :]
    if len(PathWaveDesigns) > 0:    WaveEnergy = WaveEnergy[:NumTimeSteps, :]
    if len(PathCoaxialDesigns) > 0: CoaxialEnergy = CoaxialEnergy[:NumTimeSteps, :]
    if len(PathTidalDesigns) > 0:   TidalEnergy = TidalEnergy[:NumTimeSteps, :]

    print(f"  All technologies aligned to {NumTimeSteps} timesteps")
    
    # Initialize proper empty numpy arrays for any technology that has no designs,
    # so that downstream code (variables, constraints, sums) can iterate over range(0) safely.
    if len(PathWindDesigns) == 0:
        WindEnergy = np.empty((NumTimeSteps, 0))
        WindLatLong = np.empty((0, 2))
        AnnualizedCostWind = np.empty(0)
        MaxNumWindPerSite = np.empty(0)
        WindDesign = np.empty(0, dtype=int)
        RatedPowerWindTurbine = np.empty(0)
        WindResolutionDegrees = np.empty(0)
        WindResolutionKm = np.empty(0)
    
    if len(PathKiteDesigns) == 0:
        KiteEnergy = np.empty((NumTimeSteps, 0))
        KiteLatLong = np.empty((0, 2))
        AnnualizedCostKite = np.empty(0)
        MaxNumKitePerSite = np.empty(0)
        KiteDesign = np.empty(0, dtype=int)
        RatedPowerKiteTurbine = np.empty(0)
        KiteResolutionDegrees = np.empty(0)
        KiteResolutionKm = np.empty(0)
    
    if len(PathWaveDesigns) == 0:
        WaveEnergy = np.empty((NumTimeSteps, 0))
        WaveLatLong = np.empty((0, 2))
        AnnualizedCostWave = np.empty(0)
        MaxNumWavePerSite = np.empty(0)
        WaveDesign = np.empty(0, dtype=int)
        RatedPowerWaveTurbine = np.empty(0)
        WaveResolutionDegrees = np.empty(0)
        WaveResolutionKm = np.empty(0)
    
    if len(PathCoaxialDesigns) == 0:
        CoaxialEnergy = np.empty((NumTimeSteps, 0))
        CoaxialLatLong = np.empty((0, 2))
        AnnualizedCostCoaxial = np.empty(0)
        MaxNumCoaxialPerSite = np.empty(0)
        CoaxialDesign = np.empty(0, dtype=int)
        RatedPowerCoaxialTurbine = np.empty(0)
        CoaxialResolutionDegrees = np.empty(0)
        CoaxialResolutionKm = np.empty(0)
    
    if len(PathTidalDesigns) == 0:
        TidalEnergy = np.empty((NumTimeSteps, 0))
        TidalLatLong = np.empty((0, 2))
        AnnualizedCostTidal = np.empty(0)
        MaxNumTidalPerSite = np.empty(0)
        TidalDesign = np.empty(0, dtype=int)
        RatedPowerTidalTurbine = np.empty(0)
        TidalResolutionDegrees = np.empty(0)
        TidalResolutionKm = np.empty(0)

    

    #Transmission
    Data=np.load(PathTransmissionDesign,allow_pickle=True)["TransmissionLineParameters"].item()

    AnnualizedCostTransmission=Data['S_BestACost']
    TransLatLong=Data['TL_LatLong']
    EfficiencyTransmission=Data['S_Efficiency']
    RatedPowerMWTransmissionMW=Data['RatedPowerMW']


    #Site counts are now derived directly from the LatLong arrays (which are proper
    #numpy arrays even when empty, thanks to the initialization above).

    PortImputDir={  #Wind data
                    "WindEnergy":WindEnergy,
                    "WindLatLong":WindLatLong,
                    "AnnualizedCostWind":AnnualizedCostWind, #Costs should be in M$/year
                    "MaxNumWindPerSite":MaxNumWindPerSite,
                    "WindDesign":WindDesign,
                    "RatedPowerWindTurbine":RatedPowerWindTurbine, #shoud be in MW
                    "NumWindSites": len(WindLatLong),
                    "WindResolutionDegrees":WindResolutionDegrees,
                    "WindResolutionKm":WindResolutionKm,
                    
                    
                    #Kite data
                    "KiteEnergy":KiteEnergy,
                    "KiteLatLong":KiteLatLong,
                    "AnnualizedCostKite":AnnualizedCostKite,
                    "MaxNumKitePerSite":MaxNumKitePerSite,
                    "KiteDesign":KiteDesign,
                    "RatedPowerKiteTurbine":RatedPowerKiteTurbine,
                    "NumKiteSites": len(KiteLatLong),
                    "KiteResolutionDegrees":KiteResolutionDegrees,
                    "KiteResolutionKm":KiteResolutionKm,

                                                     
                    #Wavedata
                    "WaveEnergy":WaveEnergy,
                    "WaveLatLong":WaveLatLong,
                    "AnnualizedCostWave":AnnualizedCostWave,
                    "MaxNumWavePerSite":MaxNumWavePerSite,
                    "WaveDesign":WaveDesign,
                    "RatedPowerWaveTurbine":RatedPowerWaveTurbine,
                    "NumWaveSites": len(WaveLatLong),
                    "WaveResolutionDegrees":WaveResolutionDegrees,
                    "WaveResolutionKm":WaveResolutionKm,
                    
                    #Coaxial data
                    "CoaxialEnergy":CoaxialEnergy,
                    "CoaxialLatLong":CoaxialLatLong,
                    "AnnualizedCostCoaxial":AnnualizedCostCoaxial,
                    "MaxNumCoaxialPerSite":MaxNumCoaxialPerSite,
                    "CoaxialDesign":CoaxialDesign,
                    "RatedPowerCoaxialTurbine":RatedPowerCoaxialTurbine,
                    "NumCoaxialSites": len(CoaxialLatLong),
                    "CoaxialResolutionDegrees":CoaxialResolutionDegrees,
                    "CoaxialResolutionKm":CoaxialResolutionKm,
                    
                    #Tidal data
                    "TidalEnergy":TidalEnergy,
                    "TidalLatLong":TidalLatLong,
                    "AnnualizedCostTidal":AnnualizedCostTidal,
                    "MaxNumTidalPerSite":MaxNumTidalPerSite,
                    "TidalDesign":TidalDesign,
                    "RatedPowerTidalTurbine":RatedPowerTidalTurbine,
                    "NumTidalSites": len(TidalLatLong),
                    "TidalResolutionDegrees":TidalResolutionDegrees,
                    "TidalResolutionKm":TidalResolutionKm,
                    
                    
                    "TimeList":TimeList,
                    "NumTimeSteps":len(TimeList),
                    
                    #Transmission
                    "RatedPowerMWTransmissionMW":RatedPowerMWTransmissionMW,
                    "AnnualizedCostTransmission":AnnualizedCostTransmission,
                    "TransLatLong":TransLatLong,
                    "EfficiencyTransmission":EfficiencyTransmission,
                    "NumTransSites": len(TransLatLong),
                    
                    #Optimization Params
                    "LCOE_RANGE":LCOE_RANGE,
                    "Max_CollectionRadious":Max_CollectionRadious,
                    "MaxDesignsWind":MaxDesignsWind,
                    "MaxDesignsWave":MaxDesignsWave,
                    "MaxDesignsKite":MaxDesignsKite,
                    "MaxDesignsCoaxial":MaxDesignsCoaxial,
                    "MaxDesignsTidal":MaxDesignsTidal,
                    "MinNumWindTurb":MinNumWindTurb,
                    "MinNumWaveTurb":MinNumWaveTurb,
                    "MinNumKiteTrub":MinNumKiteTrub,
                    "MinNumCoaxialTurb":MinNumCoaxialTurb,
                    "MinNumTidalTurb":MinNumTidalTurb,
                
                }
    return PortImputDir

def SolvePortOpt_MaxGen_Model(PathWindDesigns, PathWaveDesigns, PathKiteDesigns, PathCoaxialDesigns, PathTidalDesigns, PathTransmissionDesign, LCOE_RANGE\
    ,Max_CollectionRadious,MaxDesignsWind, MaxDesingsWave, MaxDesingsKite, MaxDesignsCoaxial, MaxDesignsTidal,
    MinNumWindTurb,MinNumWaveTurb,MinNumKiteTrub, MinNumCoaxialTurb, MinNumTidalTurb,
    WindTurbinesPerSite=4, WaveTurbinesPerSite=300, KiteTurbinesPerSite=390, CoaxialTurbinesPerSite=390, TidalTurbinesPerSite=200):


    #Create and solve the optimization problem
    InputDir=PreparePotOptInputs(PathWindDesigns, PathWaveDesigns,PathKiteDesigns, PathCoaxialDesigns, PathTidalDesigns, PathTransmissionDesign, LCOE_RANGE\
        ,Max_CollectionRadious,MaxDesignsWind, MaxDesingsWave, MaxDesingsKite, MaxDesignsCoaxial, MaxDesignsTidal,
        MinNumWindTurb,MinNumWaveTurb,MinNumKiteTrub, MinNumCoaxialTurb, MinNumTidalTurb,
        WindTurbinesPerSite=WindTurbinesPerSite, WaveTurbinesPerSite=WaveTurbinesPerSite, KiteTurbinesPerSite=KiteTurbinesPerSite,
        CoaxialTurbinesPerSite=CoaxialTurbinesPerSite, TidalTurbinesPerSite=TidalTurbinesPerSite)

    # --- Upcast all floating-point input arrays to float64 (float16 overflow fix) ---
    for _k, _v in list(InputDir.items()):
        if isinstance(_v, np.ndarray) and np.issubdtype(_v.dtype, np.floating):
            InputDir[_k] = _v.astype(np.float64)

    NumWindDesigns=len(PathWindDesigns)
    NumWaveDesigns=len(PathWaveDesigns)
    NumKiteDesigns=len(PathKiteDesigns)
    NumCoaxialDesigns=len(PathCoaxialDesigns)
    NumTidalDesigns=len(PathTidalDesigns)

    Model = ConcreteModel()
    # BigM must exceed the max possible total device count across all techs.
    # A fixed value (previously 1000) silently caps small-rated devices: e.g. a
    # 0.06 MW WEC needs ~20,000 units to fill a 1200 MW line, so a 1000-device
    # ceiling makes wave-heavy / wave-only cases infeasible (0 feasible LCOE
    # solutions) and forces wave to only ever appear alongside wind.
    BigM = int(InputDir["MaxNumWindPerSite"].sum()
               + InputDir["MaxNumWavePerSite"].sum()
               + InputDir["MaxNumKitePerSite"].sum()
               + InputDir["MaxNumCoaxialPerSite"].sum()
               + InputDir["MaxNumTidalPerSite"].sum()) + 10 #Big M for the maximum total number of turbines allowed to be installed

    # =========================================================================
    # Technology registry — defines each tech generically so we can loop
    # =========================================================================
    # Each entry maps a tech name to its InputDir keys, design count, and limits.
    # Only technologies with designs > 0 will have active variables & constraints.
    
    TECH_DEFS = [
        {"name": "Wind", "num_designs": NumWindDesigns,
         "energy_key": "WindEnergy",   "latlong_key": "WindLatLong",
         "cost_key": "AnnualizedCostWind", "maxnum_key": "MaxNumWindPerSite",
         "design_key": "WindDesign",   "power_key": "RatedPowerWindTurbine",
         "numsites_key": "NumWindSites",
         "reskm_key": "WindResolutionKm", "resdeg_key": "WindResolutionDegrees",
         "max_designs": InputDir["MaxDesignsWind"], "min_turbines": InputDir["MinNumWindTurb"]},
        {"name": "Wave", "num_designs": NumWaveDesigns,
         "energy_key": "WaveEnergy",   "latlong_key": "WaveLatLong",
         "cost_key": "AnnualizedCostWave", "maxnum_key": "MaxNumWavePerSite",
         "design_key": "WaveDesign",   "power_key": "RatedPowerWaveTurbine",
         "numsites_key": "NumWaveSites",
         "reskm_key": "WaveResolutionKm", "resdeg_key": "WaveResolutionDegrees",
         "max_designs": InputDir["MaxDesignsWave"], "min_turbines": InputDir["MinNumWaveTurb"]},
        {"name": "Kite", "num_designs": NumKiteDesigns,
         "energy_key": "KiteEnergy",   "latlong_key": "KiteLatLong",
         "cost_key": "AnnualizedCostKite", "maxnum_key": "MaxNumKitePerSite",
         "design_key": "KiteDesign",   "power_key": "RatedPowerKiteTurbine",
         "numsites_key": "NumKiteSites",
         "reskm_key": "KiteResolutionKm", "resdeg_key": "KiteResolutionDegrees",
         "max_designs": InputDir["MaxDesignsKite"], "min_turbines": InputDir["MinNumKiteTrub"]},
        {"name": "Coaxial", "num_designs": NumCoaxialDesigns,
         "energy_key": "CoaxialEnergy",   "latlong_key": "CoaxialLatLong",
         "cost_key": "AnnualizedCostCoaxial", "maxnum_key": "MaxNumCoaxialPerSite",
         "design_key": "CoaxialDesign",   "power_key": "RatedPowerCoaxialTurbine",
         "numsites_key": "NumCoaxialSites",
         "reskm_key": "CoaxialResolutionKm", "resdeg_key": "CoaxialResolutionDegrees",
         "max_designs": InputDir["MaxDesignsCoaxial"], "min_turbines": InputDir["MinNumCoaxialTurb"]},
        {"name": "Tidal", "num_designs": NumTidalDesigns,
         "energy_key": "TidalEnergy",   "latlong_key": "TidalLatLong",
         "cost_key": "AnnualizedCostTidal", "maxnum_key": "MaxNumTidalPerSite",
         "design_key": "TidalDesign",   "power_key": "RatedPowerTidalTurbine",
         "numsites_key": "NumTidalSites",
         "reskm_key": "TidalResolutionKm", "resdeg_key": "TidalResolutionDegrees",
         "max_designs": InputDir["MaxDesignsTidal"], "min_turbines": InputDir["MinNumTidalTurb"]},
    ]
    
    # Filter to active technologies only
    active_techs = [t for t in TECH_DEFS if t["num_designs"] > 0]
    all_tech_names = [t["name"] for t in TECH_DEFS]  # Wind, Wave, Kite, Coaxial, Tidal — always in this order
    
    # =========================================================================
    # Create Variables — always create all three Y and W vars (range(0) is fine for inactive)
    # This preserves the Model.Y_Wind / Y_Wave / Y_Kite interface for the rest of the code.
    # =========================================================================
    Model.Y_Wind = Var(range(InputDir["NumWindSites"]), domain=NonNegativeIntegers)
    Model.Y_Wave = Var(range(InputDir["NumWaveSites"]), domain=NonNegativeIntegers)
    Model.Y_Kite = Var(range(InputDir["NumKiteSites"]), domain=NonNegativeIntegers)
    Model.Y_Coaxial = Var(range(InputDir["NumCoaxialSites"]), domain=NonNegativeIntegers)
    Model.Y_Tidal = Var(range(InputDir["NumTidalSites"]), domain=NonNegativeIntegers)
    
    Model.W_Wind = Var(range(NumWindDesigns), domain=Binary)
    Model.W_Wave = Var(range(NumWaveDesigns), domain=Binary)
    Model.W_Kite = Var(range(NumKiteDesigns), domain=Binary)
    Model.W_Coaxial = Var(range(NumCoaxialDesigns), domain=Binary)
    Model.W_Tidal = Var(range(NumTidalDesigns), domain=Binary)
    
    Model.s     = Var(range(InputDir["NumTransSites"]), domain=Binary)
    Model.Delta = Var(range(InputDir["NumTimeSteps"]),  domain=NonNegativeReals)
    
    # Map tech names to their Pyomo variables for generic access
    Y_vars = {"Wind": Model.Y_Wind, "Wave": Model.Y_Wave, "Kite": Model.Y_Kite, "Coaxial": Model.Y_Coaxial, "Tidal": Model.Y_Tidal}
    W_vars = {"Wind": Model.W_Wind, "Wave": Model.W_Wave, "Kite": Model.W_Kite, "Coaxial": Model.W_Coaxial, "Tidal": Model.W_Tidal}
    
    # =========================================================================
    # Objective Function — sum over all techs generically
    # =========================================================================
    def objective_rule(Model):
        total_gen = 0
        for tdef in TECH_DEFS:
            name = tdef["name"]
            n = InputDir[tdef["numsites_key"]]
            Y = Y_vars[name]
            total_gen += sum(Y[i] * InputDir[tdef["energy_key"]][:, i].mean() * InputDir[tdef["power_key"]][i]
                             for i in range(n))
        
        TotalCurtailment = sum(Model.Delta[t] for t in range(InputDir["NumTimeSteps"])) / InputDir["NumTimeSteps"]
        return (total_gen - TotalCurtailment) * 24 * 365.25

    Model.OBJ = Objective(rule=objective_rule, sense=maximize)

    # =========================================================================
    # Per-site max turbine constraints — generic loop
    # =========================================================================
    for tdef in active_techs:
        name = tdef["name"]
        n = InputDir[tdef["numsites_key"]]
        Y = Y_vars[name]
        
        def _max_turb_rule(Model, i, _n=name, _tdef=tdef):
            return Y_vars[_n][i] <= InputDir[_tdef["maxnum_key"]][i]
        
        setattr(Model, f"Turbines_Cell_{name}",
                Constraint(range(n), rule=_max_turb_rule))

    # =========================================================================
    # Curtailment constraint — sum over all techs
    # =========================================================================
    def Curtailment_rule(Model, t):
        total_gen = 0
        for tdef in TECH_DEFS:
            name = tdef["name"]
            n = InputDir[tdef["numsites_key"]]
            Y = Y_vars[name]
            total_gen += sum(Y[i] * InputDir[tdef["energy_key"]][t, i] * InputDir[tdef["power_key"]][i]
                             for i in range(n))
        return -Model.Delta[t] + total_gen <= InputDir["RatedPowerMWTransmissionMW"]

    Model.Curtailment = Constraint(range(InputDir["NumTimeSteps"]), rule=Curtailment_rule)

    # =========================================================================
    # Collection system center selection — generic radious exclusion
    # =========================================================================
    Model.ChooseOneCircle = Constraint(expr=sum(Model.s[i] for i in range(InputDir["NumTransSites"])) == 1)

    IdxOut = {}
    for tdef in TECH_DEFS:
        name = tdef["name"]
        n = InputDir[tdef["numsites_key"]]
        if n > 0:
            IdxOut[name] = GetIdxOutRadious(InputDir["TransLatLong"], InputDir[tdef["latlong_key"]],
                                            InputDir["Max_CollectionRadious"])
        else:
            IdxOut[name] = [[] for _ in range(InputDir["NumTransSites"])]

    def MaximumRadious(Model, i):
        total = 0
        for tdef in TECH_DEFS:
            total += sum(Y_vars[tdef["name"]][j] for j in IdxOut[tdef["name"]][i])
        return total <= (1 - Model.s[i]) * BigM

    Model.Maximum_Radious = Constraint(range(InputDir["NumTransSites"]), rule=MaximumRadious)

    # =========================================================================
    # Design tracking and limits — generic loop
    # =========================================================================
    for tdef in active_techs:
        name = tdef["name"]
        nd = tdef["num_designs"]
        Y = Y_vars[name]
        W = W_vars[name]
        
        def _track_design_rule(Model, d, _name=name, _tdef=tdef):
            IdxVarPartOfDesign = np.where(InputDir[_tdef["design_key"]] == d)[0]
            return sum(Y_vars[_name][i] for i in IdxVarPartOfDesign) <= W_vars[_name][d] * BigM
        
        setattr(Model, f"TrackDesigns_{name}",
                Constraint(range(nd), rule=_track_design_rule))
        
        setattr(Model, f"LimitDesigns_{name}",
                Constraint(expr=sum(W[d] for d in range(nd)) == tdef["max_designs"]))
        
        n = InputDir[tdef["numsites_key"]]
        setattr(Model, f"SetLB_{name}",
                Constraint(expr=sum(Y[i] for i in range(n)) >= tdef["min_turbines"]))

    # =========================================================================
    # Overlap Constraints
    # =========================================================================
    # Physical co-location rules:
    #   - Wind occupies the air above the ocean surface (turbine + nacelle).
    #   - Wave devices (WECs) operate at/near the ocean surface.
    #   - Kites operate at depth in ocean currents (tethered, mobile).
    #   - Coaxial turbines are fixed on the seabed in ocean currents.
    #   - Tidal turbines are fixed on the seabed in tidal channels.
    #
    # Co-location compatibility:
    #   - Wind + Wave:     CAN coexist (WECs fit between wind platform moorings).
    #   - Wind + Kite:     CAN coexist (wind is airborne, kites are subsurface).
    #   - Wind + Coaxial:  CAN coexist (wind is airborne, coaxial is on seabed).
    #   - Wind + Tidal:    CAN coexist (wind is airborne, tidal is on seabed).
    #   - Wave + Kite:     CANNOT coexist (both occupy the water column).
    #   - Wave + Coaxial:  CANNOT coexist (surface moorings conflict with seabed).
    #   - Wave + Tidal:    CANNOT coexist (surface moorings conflict with seabed).
    #   - Kite + Coaxial:  CANNOT coexist (both subsurface in current flows).
    #   - Kite + Tidal:    CANNOT coexist (both subsurface in current flows).
    #   - Coaxial + Tidal: CANNOT coexist (both seabed-mounted current devices).
    #
    # Therefore we enforce:
    #   1. Self-overlaps for all techs to prevent double-counting designs.
    #   2. Cross-tech overlaps for all incompatible pairs listed above.
    #
    # The max collection radius constraint already ensures all devices are
    # within the same general region for transmission purposes.
    # =========================================================================

    _empty_overlap = (np.empty((0, 2), dtype=int), np.empty(0),
                      np.empty((0, 2)), np.empty((0, 2)), np.empty(0))

    _tdef_lookup = {d["name"]: d for d in TECH_DEFS}

    OVERLAP_PAIRS = []

    # Self-overlaps for all active techs
    for tdef in active_techs:
        OVERLAP_PAIRS.append((tdef["name"], tdef["name"], True, "self"))

    # Cross-tech incompatible pairs (both directions)
    _incompatible_pairs = [
        ("Wave", "Kite"), ("Wave", "Coaxial"), ("Wave", "Tidal"),
        ("Kite", "Coaxial"), ("Kite", "Tidal"),
        ("Coaxial", "Tidal"),
    ]
    _active_names = {t["name"] for t in active_techs}
    for a, b in _incompatible_pairs:
        if a in _active_names and b in _active_names:
            OVERLAP_PAIRS.append((a, b, False, "cross"))
            OVERLAP_PAIRS.append((b, a, False, "cross"))

    # Compute overlaps for each defined pair
    overlaps = {}
    for a, b, is_self, ctype in OVERLAP_PAIRS:
        tdef_a = _tdef_lookup[a]
        tdef_b = _tdef_lookup[b]
        overlaps[(a, b)] = GetOverlaps_Idx_Area(
            InputDir[tdef_a["latlong_key"]], InputDir[tdef_a["reskm_key"]],
            InputDir[tdef_a["resdeg_key"]], InputDir[tdef_a["maxnum_key"]],
            InputDir[tdef_b["latlong_key"]], InputDir[tdef_b["reskm_key"]],
            InputDir[tdef_b["resdeg_key"]], InputDir[tdef_b["maxnum_key"]],
            SameTech=(1 if is_self else 0), PrintName=f"{a}-{b}")

    # Build overlap constraints per tech: for each tech A, gather all pairs
    # where A is the "reference" tech and build a single constraint set.
    for tdef_a in active_techs:
        a = tdef_a["name"]

        # Find all pairs where this tech is the reference (first element)
        relevant_pairs = [(a2, b2, s2, c2) for a2, b2, s2, c2 in OVERLAP_PAIRS if a2 == a]

        if len(relevant_pairs) == 0:
            continue

        # Collect unique site indices for tech A that have ANY overlap
        all_idx_arrays = [overlaps[(a2, b2)][0] for a2, b2, _, _ in relevant_pairs]
        nonempty = [arr for arr in all_idx_arrays if len(arr) > 0]

        if len(nonempty) == 0:
            continue

        combined = np.concatenate(nonempty)
        unique_idx = np.unique(combined[:, 0])

        # Pre-extract overlap data for this tech's pairs (avoids repeated lookups in rule)
        _pairs_data = []
        for a2, b2, is_self, ctype in relevant_pairs:
            _pairs_data.append({
                "b": b2, "is_self": is_self, "ctype": ctype,
                "idx_ov": overlaps[(a2, b2)][0],
                "area_ref": overlaps[(a2, b2)][2],
                "max_turb": overlaps[(a2, b2)][3],
                "pct_ov": overlaps[(a2, b2)][4],
            })

        def _overlap_rule(Model, i, _a=a, _pairs=_pairs_data):
            Y_a = Y_vars[_a]
            expr = Y_a[i] - InputDir[_tdef_lookup[_a]["maxnum_key"]][i]

            for pair in _pairs:
                idx_ov = pair["idx_ov"]
                if len(idx_ov) == 0:
                    continue

                mask = idx_ov[:, 0] == i
                j_indices = idx_ov[mask, 1]

                if len(j_indices) == 0:
                    continue

                Y_b = Y_vars[pair["b"]]

                if pair["ctype"] == "self":
                    # Self-overlap: simple integer deduction
                    expr -= sum(Y_b[j_indices[k]] for k in range(len(j_indices)))
                else:
                    # Cross-tech: area-weighted deduction
                    area_f = pair["area_ref"][mask]
                    mt_f = pair["max_turb"][mask]
                    pct_f = pair["pct_ov"][mask]
                    expr -= sum(
                        (area_f[k, 1] / mt_f[k, 1] * Y_b[j_indices[k]]) * pct_f[k]
                        * mt_f[k, 0] / area_f[k, 0]
                        for k in range(len(j_indices)))

            return expr <= 0

        setattr(Model, f"Overlap_{a}_ALL",
                Constraint(list(unique_idx), rule=_overlap_rule))

    ################################### Overlap Constraints ################################### End

    # =========================================================================
    # Strict Kite <-> Coaxial mutual exclusion at coincident ocean-current sites
    # -------------------------------------------------------------------------
    # Kites and coaxial turbines both harvest the ocean current at the SAME depth,
    # so they physically cannot occupy the same location. The area-weighted overlap
    # rule above does not strictly forbid this, so we add a hard exclusion: at each
    # shared site, kites OR coaxial may be deployed, never both. Only active when
    # both technologies are selected.
    # =========================================================================
    if "Kite" in _active_names and "Coaxial" in _active_names:
        _kite_ll = InputDir["KiteLatLong"]
        _coax_ll = InputDir["CoaxialLatLong"]
        _max_kite = InputDir["MaxNumKitePerSite"]
        _max_coax = InputDir["MaxNumCoaxialPerSite"]

        def _loc_key(p):
            return (round(float(p[0]), 5), round(float(p[1]), 5))

        _kite_by_loc = {}
        for _k in range(len(_kite_ll)):
            _kite_by_loc.setdefault(_loc_key(_kite_ll[_k]), []).append(_k)
        _coax_by_loc = {}
        for _c in range(len(_coax_ll)):
            _coax_by_loc.setdefault(_loc_key(_coax_ll[_c]), []).append(_c)

        _shared_locs = [loc for loc in _kite_by_loc if loc in _coax_by_loc]

        if _shared_locs:
            _n_excl = len(_shared_locs)
            _kc_kite_idx = [_kite_by_loc[loc] for loc in _shared_locs]
            _kc_coax_idx = [_coax_by_loc[loc] for loc in _shared_locs]
            _kc_kite_cap = [sum(float(_max_kite[k]) for k in _kite_by_loc[loc]) for loc in _shared_locs]
            _kc_coax_cap = [sum(float(_max_coax[c]) for c in _coax_by_loc[loc]) for loc in _shared_locs]

            Model.KiteCoax_UseKite = Var(range(_n_excl), domain=Binary)
            Model.KiteCoax_UseCoax = Var(range(_n_excl), domain=Binary)

            def _kc_kite_link(Model, L):
                return sum(Model.Y_Kite[k] for k in _kc_kite_idx[L]) <= _kc_kite_cap[L] * Model.KiteCoax_UseKite[L]
            Model.KiteCoax_KiteLink = Constraint(range(_n_excl), rule=_kc_kite_link)

            def _kc_coax_link(Model, L):
                return sum(Model.Y_Coaxial[c] for c in _kc_coax_idx[L]) <= _kc_coax_cap[L] * Model.KiteCoax_UseCoax[L]
            Model.KiteCoax_CoaxLink = Constraint(range(_n_excl), rule=_kc_coax_link)

            def _kc_excl(Model, L):
                return Model.KiteCoax_UseKite[L] + Model.KiteCoax_UseCoax[L] <= 1
            Model.KiteCoax_Exclusion = Constraint(range(_n_excl), rule=_kc_excl)

            print("Added strict Kite<->Coaxial exclusion at %d shared ocean-current site(s)." % _n_excl)

    # #LCOE Target (Attached later on the LCOE iterator)
    # def LCOETarget(Model, LCOE_Max):  
    #     EGWind=sum(Model.Y_Wind[i]*InputDir["WindEnergy"][:,i].mean()*InputDir["RatedPowerWindTurbine"][i]  for i in range(InputDir["NumWindSites"])) #Energy generation from wind turbines [MW Avg]
    #     EGWave=sum(Model.Y_Wave[i]*InputDir["WaveEnergy"][:,i].mean()*InputDir["RatedPowerWaveTurbine"][i]  for i in range(InputDir["NumWaveSites"])) #Energy generation from wave turbines [MW Avg]
    #     EGKite=sum(Model.Y_Kite[i]*InputDir["KiteEnergy"][:,i].mean()*InputDir["RatedPowerKiteTurbine"][i]  for i in range(InputDir["NumKiteSites"])) #Energy generation from kite turbines [MW Avg]

    #     TotalCurtailment=sum(Model.Delta[t] for t in range(InputDir["NumTimeSteps"]))/InputDir["NumTimeSteps"] #Average curtailment MW

    #     MWhYear=(EGWind+EGWave+EGKite-TotalCurtailment)*24*365.25 # MWh Avg per year


    #     Cost_Wind=sum(Model.Y_Wind[i]*InputDir["AnnualizedCostWind"][i]  for i in range(InputDir["NumWindSites"]))
    #     Cost_Wave=sum(Model.Y_Wave[i]*InputDir["AnnualizedCostWave"][i]  for i in range(InputDir["NumWaveSites"]))
    #     Cost_Kite=sum(Model.Y_Kite[i]*InputDir["AnnualizedCostKite"][i]  for i in range(InputDir["NumKiteSites"]))
        
        
    #     Cost_Transmission=sum(Model.s[i]*InputDir["AnnualizedCostTransmission"][i] for i in Model.SiteTrs)
        
    #     TotalCost=Cost_Wind+Cost_Wave+Cost_Kite+Cost_Transmission
        

    #     return TotalCost<=LCOE_Max*MWhYear  

    return Model, InputDir


# ============================================================================
#  Helper functions for per-LCOE output generation
# ============================================================================

def _make_time_axis(TimeList):
    """Convert the TimeList from the model into matplotlib-compatible datetimes."""
    try:
        if isinstance(TimeList[0], (datetime,)):
            return list(TimeList)
        elif isinstance(TimeList[0], np.datetime64):
            return [t.astype('datetime64[ms]').astype(datetime) for t in TimeList]
        else:
            return [datetime.strptime(str(t), "%Y-%m-%d %H:%M:%S") for t in TimeList]
    except Exception:
        return list(np.arange(len(TimeList)))


def _compute_timeseries(InputDir, Optimal_Y_Wind, Optimal_Y_Wave, Optimal_Y_Kite, Optimal_Y_Coaxial, Optimal_Y_Tidal, Optimal_Delta):
    """Compute full MW generation time series for each technology and curtailment."""
    T = InputDir["NumTimeSteps"]

    ts_wind = np.zeros(T)
    if InputDir["NumWindSites"] > 0 and InputDir["WindEnergy"].ndim == 2:
        for i in range(InputDir["NumWindSites"]):
            if Optimal_Y_Wind[i] > 0:
                ts_wind += Optimal_Y_Wind[i] * InputDir["WindEnergy"][:, i] * InputDir["RatedPowerWindTurbine"][i]

    ts_wave = np.zeros(T)
    if InputDir["NumWaveSites"] > 0 and InputDir["WaveEnergy"].ndim == 2:
        for i in range(InputDir["NumWaveSites"]):
            if Optimal_Y_Wave[i] > 0:
                ts_wave += Optimal_Y_Wave[i] * InputDir["WaveEnergy"][:, i] * InputDir["RatedPowerWaveTurbine"][i]

    ts_kite = np.zeros(T)
    if InputDir["NumKiteSites"] > 0 and InputDir["KiteEnergy"].ndim == 2:
        for i in range(InputDir["NumKiteSites"]):
            if Optimal_Y_Kite[i] > 0:
                ts_kite += Optimal_Y_Kite[i] * InputDir["KiteEnergy"][:, i] * InputDir["RatedPowerKiteTurbine"][i]

    ts_coaxial = np.zeros(T)
    if InputDir["NumCoaxialSites"] > 0 and InputDir["CoaxialEnergy"].ndim == 2:
        for i in range(InputDir["NumCoaxialSites"]):
            if Optimal_Y_Coaxial[i] > 0:
                ts_coaxial += Optimal_Y_Coaxial[i] * InputDir["CoaxialEnergy"][:, i] * InputDir["RatedPowerCoaxialTurbine"][i]

    ts_tidal = np.zeros(T)
    if InputDir["NumTidalSites"] > 0 and InputDir["TidalEnergy"].ndim == 2:
        for i in range(InputDir["NumTidalSites"]):
            if Optimal_Y_Tidal[i] > 0:
                ts_tidal += Optimal_Y_Tidal[i] * InputDir["TidalEnergy"][:, i] * InputDir["RatedPowerTidalTurbine"][i]

    ts_curtailment = np.array(Optimal_Delta)
    ts_total = ts_wind + ts_wave + ts_kite + ts_coaxial + ts_tidal - ts_curtailment

    return ts_wind, ts_wave, ts_kite, ts_coaxial, ts_tidal, ts_curtailment, ts_total


def _plot_total_generation(time_axis, ts_total, LCOETarget, CurrentLCOE, trans_capacity, save_path):
    """Plot total net generation vs. time."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(time_axis, ts_total, color='#2166ac', linewidth=0.4, alpha=0.85)
    ax.axhline(y=trans_capacity, color='red', linestyle='--', linewidth=1.0,
               label='Transmission Capacity (%.0f MW)' % trans_capacity)
    ax.set_xlabel('Time')
    ax.set_ylabel('Net Generation (MW)')
    ax.set_title('Total Net Generation - LCOE Target: %d $/MWh | Achieved: %.1f $/MWh' % (LCOETarget, CurrentLCOE))
    ax.legend(loc='upper right')
    ax.set_xlim(time_axis[0], time_axis[-1])
    ax.set_ylim(bottom=0)
    if isinstance(time_axis[0], datetime):
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)


def _plot_stacked_generation(time_axis, ts_wind, ts_wave, ts_kite, ts_coaxial, ts_tidal, LCOETarget, CurrentLCOE, trans_capacity, save_path):
    """Stacked area plot of generation by technology."""
    fig, ax = plt.subplots(figsize=(14, 5))
    labels, series, colors = [], [], []
    if ts_wind.sum() > 0:
        labels.append('Wind'); series.append(ts_wind); colors.append('#4393c3')
    if ts_wave.sum() > 0:
        labels.append('Wave'); series.append(ts_wave); colors.append('#f4a582')
    if ts_kite.sum() > 0:
        labels.append('Kite'); series.append(ts_kite); colors.append('#92c5de')
    if ts_coaxial.sum() > 0:
        labels.append('Coaxial'); series.append(ts_coaxial); colors.append('#8da0cb')
    if ts_tidal.sum() > 0:
        labels.append('Tidal'); series.append(ts_tidal); colors.append('#66c2a5')
    if len(series) > 0:
        ax.stackplot(time_axis, *series, labels=labels, colors=colors, alpha=0.85)
    ax.axhline(y=trans_capacity, color='red', linestyle='--', linewidth=1.0,
               label='Transmission Capacity (%.0f MW)' % trans_capacity)
    ax.set_xlabel('Time')
    ax.set_ylabel('Gross Generation (MW)')
    ax.set_title('Generation by Technology - LCOE Target: %d $/MWh | Achieved: %.1f $/MWh' % (LCOETarget, CurrentLCOE))
    ax.legend(loc='upper right')
    ax.set_xlim(time_axis[0], time_axis[-1])
    ax.set_ylim(bottom=0)
    if isinstance(time_axis[0], datetime):
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)


def _plot_curtailment(time_axis, ts_curtailment, LCOETarget, CurrentLCOE, save_path):
    """Plot curtailment vs. time."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.fill_between(time_axis, 0, ts_curtailment, color='#d6604d', alpha=0.7)
    ax.plot(time_axis, ts_curtailment, color='#b2182b', linewidth=0.4)
    ax.set_xlabel('Time')
    ax.set_ylabel('Curtailment (MW)')
    ax.set_title('Curtailment - LCOE Target: %d $/MWh | Achieved: %.1f $/MWh' % (LCOETarget, CurrentLCOE))
    ax.set_xlim(time_axis[0], time_axis[-1])
    ax.set_ylim(bottom=0)
    if isinstance(time_axis[0], datetime):
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)


def _plot_deployment_map(InputDir, Optimal_Y_Wind, Optimal_Y_Wave, Optimal_Y_Kite, Optimal_Y_Coaxial, Optimal_Y_Tidal, Optimal_s,
                         LCOETarget, CurrentLCOE, total_units, save_path,
                         HAPCExclusionPath=None, ProhibitedMPAExclusionPath=None,
                         RestrictedMPAExclusionPath=None, ShippingExclusionPath=None):
    """Plot site deployment map with coastline, bathymetry contours, and ocean fill."""
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D

    TECH_COLORS = {"Wind": "dodgerblue", "Wave": "darkorange", "Kite": "limegreen", "Coaxial": "mediumorchid", "Tidal": "crimson"}

    # --- Attempt to load geospatial overlays ---
    # Look for files relative to cwd (East Coast Model directory) or common paths
    _base_candidates = [
        os.getcwd(),
        os.path.join(os.getcwd(), ".."),
        r"C:\Users\rmiller9\Documents\East Coast Model",
    ]

    geo_loaded = False
    for _base in _base_candidates:
        _depth_nc = os.path.join(_base, "Depths_EastCoast_Offshore.nc")
        _coast_shp = os.path.join(_base, "Geospatial Data", "CoastLine", "ne_10m_coastline.shp")
        _borders_shp = os.path.join(_base, "Geospatial Data", "CoastLine", "ne_10m_admin_1_states_provinces_lines.shp")
        if os.path.exists(_depth_nc) and os.path.exists(_coast_shp):
            try:
                import geopandas as gpd
                import xarray as xr

                ds = xr.open_dataset(_depth_nc)
                lat_d = ds["lat"].values[::2]
                lon_d = ds["lon"].values[::2]
                depth_bathy = ds["depth"].values[::2, ::2]
                LonGrid, LatGrid = np.meshgrid(lon_d, lat_d)
                ds.close()

                coast = gpd.read_file(_coast_shp)
                borders = gpd.read_file(_borders_shp)
                coast = coast.set_crs(epsg=4326) if coast.crs is None else coast.to_crs(epsg=4326)
                borders = borders.set_crs(epsg=4326) if borders.crs is None else borders.to_crs(epsg=4326)
                geo_loaded = True
                break
            except Exception:
                pass

    DEPTH_LEVELS = [30, 100, 500, 1000, 2000]
    DEPTH_COLORS = {30: "purple", 100: "royalblue", 500: "teal", 1000: "darkorange", 2000: "gold"}

    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_facecolor("#d9d9d9")

    # Ocean fill
    if geo_loaded:
        _dmax = np.nanmax(depth_bathy)   # ignore land NaN cells (bathymetry has NaN over land)
        if np.isfinite(_dmax) and _dmax > 0:
            ax.contourf(LonGrid, LatGrid, depth_bathy,
                         levels=[0, _dmax], colors=["aliceblue"], zorder=1)

    legend_handles = []
    all_lons = []
    all_lats = []
    n_total = 0

    tech_data = [
        ("Wind", Optimal_Y_Wind, InputDir["WindLatLong"]),
        ("Wave", Optimal_Y_Wave, InputDir["WaveLatLong"]),
        ("Kite", Optimal_Y_Kite, InputDir["KiteLatLong"]),
        ("Coaxial", Optimal_Y_Coaxial, InputDir["CoaxialLatLong"]),
        ("Tidal", Optimal_Y_Tidal, InputDir["TidalLatLong"]),
    ]

    for tech_name, Y_arr, LatLong in tech_data:
        if len(Y_arr) == 0 or len(LatLong) == 0:
            continue
        active = np.where(Y_arr > 0.5)[0]
        if len(active) == 0:
            continue
        ll = LatLong[active]
        units = Y_arr[active]
        color = TECH_COLORS.get(tech_name, "gray")
        sizes = np.clip(15 + units * 8, 15, 150)
        ax.scatter(ll[:, 1], ll[:, 0], s=sizes, c=color,
                   edgecolors="black", linewidths=0.3, alpha=0.85, zorder=4)
        n_sites = len(units)
        n_units = int(units.sum())
        n_total += n_units
        legend_handles.append(
            Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
                   markeredgecolor="black", markersize=8,
                   label="%s: %d sites, %d units" % (tech_name, n_sites, n_units)))
        all_lons.extend(ll[:, 1])
        all_lats.extend(ll[:, 0])

    # Transmission hub
    TransLatLong = InputDir["TransLatLong"]
    hub_idx = np.argmax(Optimal_s)
    hub_ll = TransLatLong[hub_idx]
    ax.scatter(hub_ll[1], hub_ll[0], s=250, c="red", marker="*",
              edgecolors="black", linewidths=0.8, zorder=6)
    legend_handles.append(
        Line2D([0], [0], marker="*", color="w", markerfacecolor="red",
               markeredgecolor="black", markersize=14, label="Transmission Hub"))
    all_lons.append(hub_ll[1])
    all_lats.append(hub_ll[0])

    # Collection radius
    r_km = InputDir["Max_CollectionRadious"]
    r_lat = r_km / 110.574
    r_lon = r_km / (111.32 * np.cos(np.radians(hub_ll[0])))
    circle = mpatches.Ellipse(
        (hub_ll[1], hub_ll[0]), width=2*r_lon, height=2*r_lat,
        fill=False, edgecolor="red", linewidth=1.5, linestyle="--", zorder=5)
    ax.add_patch(circle)
    legend_handles.append(
        Line2D([0], [0], color="red", linestyle="--", lw=1.5,
               label="Collection radius (%.0f km)" % r_km))

    # Domain bounds
    PAD = 2.0
    if len(all_lons) > 0:
        xlim = (min(all_lons) - PAD, max(all_lons) + PAD)
        ylim = (min(all_lats) - PAD, max(all_lats) + PAD)
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)

    # Geospatial overlays
    if geo_loaded:
        for lvl in DEPTH_LEVELS:
            cs = ax.contour(LonGrid, LatGrid, depth_bathy,
                            levels=[lvl], colors=[DEPTH_COLORS[lvl]],
                            linewidths=1.0, zorder=3)
            ax.clabel(cs, inline=True, fontsize=7, fmt={lvl: f"{lvl} m"})

        # --- Exclusion zones (only those enabled for this run) ---
        # style matches the standalone Environmental_Risk_Plot_Code
        import matplotlib.patches as _mpatches
        _EXCL = [
            ("HAPC hard bottom", HAPCExclusionPath, "env", "#e31a1c"),
            ("Prohibited MPA", ProhibitedMPAExclusionPath, "env", "#ff7f00"),
            ("Restricted MPA", RestrictedMPAExclusionPath, "env", "#6a3d9a"),
            ("Shipping lane", ShippingExclusionPath, "ship", "#1f78b4"),
        ]
        for _lab, _path, _kind, _col in _EXCL:
            if not _path:
                continue
            try:
                if _kind == "env":
                    _pts = load_environmental_exclusions(hapc_path=_path if _lab.startswith("HAPC") else None,
                                                         prohibited_path=_path if "Prohibited" in _lab else None,
                                                         restricted_path=_path if "Restricted" in _lab else None)
                else:
                    _pts = load_shipping_exclusion(_path)
            except Exception:
                _pts = np.empty((0, 2))
            if len(_pts) == 0:
                continue
            _s = 3.0 if len(_pts) < 1000 else 0.5
            ax.scatter(_pts[:, 1], _pts[:, 0], s=_s, c=_col, alpha=0.6, zorder=4, rasterized=True)
            legend_handles.append(
                _mpatches.Patch(color=_col, alpha=0.7, label="Exclusion: %s (%s pts)" % (_lab, format(len(_pts), ",")))
            )

        coast.plot(ax=ax, linewidth=1.2, color="black", zorder=5)
        borders.plot(ax=ax, linewidth=0.6, color="black", zorder=5)

        depth_handles = [
            Line2D([0], [0], color=DEPTH_COLORS[l], lw=2, label=f"{l} m")
            for l in DEPTH_LEVELS
        ]

        leg1 = ax.legend(handles=legend_handles, loc="upper left",
                         frameon=True, framealpha=0.9, facecolor="white", title="Deployments")
        ax.add_artist(leg1)
        ax.legend(handles=depth_handles, loc="lower right",
                  frameon=True, framealpha=0.9, facecolor="white", title="Bathymetry")
    else:
        ax.legend(handles=legend_handles, loc="upper left",
                  frameon=True, framealpha=0.9, facecolor="white", title="Deployments")

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Portfolio Deployment - LCOE Target: %d $/MWh | Achieved: %.1f $/MWh | %d total units"
                 % (LCOETarget, CurrentLCOE, n_total), fontsize=11)
    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _plot_efficient_frontier(lcoe_targets, mw_avgs, save_path):
    """Efficient frontier: average generation (x) vs LCOE target (y)."""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(mw_avgs, lcoe_targets, 'o-', color='#2166ac', markersize=8, linewidth=2)
    for x, y in zip(mw_avgs, lcoe_targets):
        ax.annotate("%.0f MW" % x, (x, y), textcoords="offset points",
                    xytext=(8, 4), fontsize=8, color='#333333')
    ax.set_xlabel("Average Net Generation (MW)")
    ax.set_ylabel("LCOE Target ($/MWh)")
    ax.set_title("Efficient Frontier: Generation vs LCOE Target")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)


def _plot_stacked_costs(lcoe_targets, costs_wind, costs_wave, costs_kite, costs_coaxial, costs_tidal, costs_trans, save_path):
    """Stacked bar chart of annualized costs by technology at each LCOE target."""
    fig, ax = plt.subplots(figsize=(8, 6))
    x = np.arange(len(lcoe_targets))
    width = 0.6
    labels_str = ["%d" % t for t in lcoe_targets]

    bottom = np.zeros(len(lcoe_targets))
    tech_items = [
        ("Wind", np.array(costs_wind), '#4393c3'),
        ("Wave", np.array(costs_wave), '#f4a582'),
        ("Kite", np.array(costs_kite), '#92c5de'),
        ("Coaxial", np.array(costs_coaxial), '#8da0cb'),
        ("Tidal", np.array(costs_tidal), '#66c2a5'),
        ("Transmission", np.array(costs_trans), '#d6604d'),
    ]
    for label, vals, color in tech_items:
        if vals.sum() > 0:
            ax.bar(x, vals, width, bottom=bottom, label=label, color=color)
            bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(labels_str)
    ax.set_xlabel("LCOE Target ($/MWh)")
    ax.set_ylabel("Annualized Cost (M$/year)")
    ax.set_title("Annualized System Cost Breakdown by Technology")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)


def _write_summary_csv(save_path, lcoe_targets, lcoe_achieved, mw_avgs,
                       mw_wind, mw_wave, mw_kite, mw_coaxial, mw_tidal, mw_curtailment,
                       costs_wind, costs_wave, costs_kite, costs_coaxial, costs_tidal, costs_trans):
    """Write a CSV summary table of all feasible LCOE solutions."""
    with open(save_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "LCOE_Target_$/MWh", "LCOE_Achieved_$/MWh",
            "Total_MW_Avg", "Wind_MW_Avg", "Wave_MW_Avg", "Kite_MW_Avg", "Coaxial_MW_Avg", "Tidal_MW_Avg", "Curtailment_MW_Avg",
            "Cost_Wind_M$/yr", "Cost_Wave_M$/yr", "Cost_Kite_M$/yr", "Cost_Coaxial_M$/yr", "Cost_Tidal_M$/yr",
            "Cost_Transmission_M$/yr", "Total_Cost_M$/yr"
        ])
        for i in range(len(lcoe_targets)):
            total_cost = costs_wind[i] + costs_wave[i] + costs_kite[i] + costs_coaxial[i] + costs_tidal[i] + costs_trans[i]
            writer.writerow([
                lcoe_targets[i], "%.4f" % lcoe_achieved[i],
                "%.4f" % mw_avgs[i],
                "%.4f" % mw_wind[i], "%.4f" % mw_wave[i], "%.4f" % mw_kite[i],
                "%.4f" % mw_coaxial[i], "%.4f" % mw_tidal[i],
                "%.4f" % mw_curtailment[i],
                "%.6f" % costs_wind[i], "%.6f" % costs_wave[i], "%.6f" % costs_kite[i],
                "%.6f" % costs_coaxial[i], "%.6f" % costs_tidal[i],
                "%.6f" % costs_trans[i], "%.6f" % total_cost
            ])



def _design_names(paths):
    """Short design label per path index (strips the run/region/year tail)."""
    names=[]
    for pth in paths:
        base=os.path.basename(pth)[:-4]
        names.append(base)
    return names

def _per_design_breakdown(Y, DesignIdx, LatLong, design_names):
    """Return list of (design_name, n_sites, n_units, [(lat,lon,units)...]) for placed units."""
    Y=np.asarray(Y); DesignIdx=np.asarray(DesignIdx)
    rows=[]
    if len(Y)==0: return rows
    active=np.where(Y>0.5)[0]
    for d in np.unique(DesignIdx[active]) if len(active) else []:
        sel=active[DesignIdx[active]==d]
        units=Y[sel]
        name=design_names[int(d)] if int(d)<len(design_names) else f"design_{int(d)}"
        placements=[(float(LatLong[s][0]), float(LatLong[s][1]), float(Y[s])) for s in sel]
        rows.append((name, len(sel), int(round(units.sum())), placements))
    return rows

def SolvePortOpt_MaxGen_LCOE_Iterator(PathWindDesigns, PathWaveDesigns, PathKiteDesigns, PathCoaxialDesigns, PathTidalDesigns, PathTransmissionDesign, LCOE_RANGE\
    ,Max_CollectionRadious,MaxDesignsWind, MaxDesingsWave, MaxDesingsKite, MaxDesignsCoaxial, MaxDesignsTidal,
    MinNumWindTurb,MinNumWaveTurb,MinNumKiteTrub, MinNumCoaxialTurb, MinNumTidalTurb\
    ,ReadMe,SavePath=None, PerLCOE_OutputFolder=None,
    WindTurbinesPerSite=4, WaveTurbinesPerSite=300, KiteTurbinesPerSite=390, CoaxialTurbinesPerSite=390, TidalTurbinesPerSite=200,
    HAPCExclusionPath=None, ProhibitedMPAExclusionPath=None, RestrictedMPAExclusionPath=None,
    ShippingExclusionPath=None):

    # ---------------------------------------------------------------------
    # Make output paths unique per cost-scaling scenario, so runs with the same
    # techs/transmission but different *CostScaling values don't overwrite each
    # other. Only scalings that differ from 1.0 are added (e.g. "_wave0.1").
    # ---------------------------------------------------------------------
    _scaling_pairs = [("wind", windCostScaling), ("wave", waveCostScaling),
                      ("kite", kiteCostScaling), ("coax", coaxialCostScaling),
                      ("tidal", tidalCostScaling)]
    _scaling_tag = "".join("_%s%g" % (nm, val) for nm, val in _scaling_pairs if val != 1.0)
    if _scaling_tag:
        if SavePath is not None:
            SavePath = SavePath + _scaling_tag
        if PerLCOE_OutputFolder is not None:
            PerLCOE_OutputFolder = PerLCOE_OutputFolder + _scaling_tag
    print("Cost-scaling tag for outputs: '%s'" % (_scaling_tag or "(all 1.0 - no tag)"))
    if PerLCOE_OutputFolder is not None:
        print("Per-LCOE output folder:", PerLCOE_OutputFolder)

    #Create inputs and main model structure
    Model, InputDir=SolvePortOpt_MaxGen_Model(PathWindDesigns, PathWaveDesigns, PathKiteDesigns, PathCoaxialDesigns, PathTidalDesigns, PathTransmissionDesign, LCOE_RANGE\
        ,Max_CollectionRadious,MaxDesignsWind, MaxDesingsWave, MaxDesingsKite, MaxDesignsCoaxial, MaxDesignsTidal,
        MinNumWindTurb,MinNumWaveTurb,MinNumKiteTrub, MinNumCoaxialTurb, MinNumTidalTurb,
        WindTurbinesPerSite=WindTurbinesPerSite, WaveTurbinesPerSite=WaveTurbinesPerSite, KiteTurbinesPerSite=KiteTurbinesPerSite,
        CoaxialTurbinesPerSite=CoaxialTurbinesPerSite, TidalTurbinesPerSite=TidalTurbinesPerSite)

    # =========================================================================
    # Environmental Exclusion Zones
    # =========================================================================
    _has_env = any([HAPCExclusionPath, ProhibitedMPAExclusionPath, RestrictedMPAExclusionPath])
    _has_ship = ShippingExclusionPath is not None

    if _has_env or _has_ship:
        print("\n" + "=" * 70)
        print("SITE EXCLUSION CONSTRAINTS")
        print("=" * 70)

        Y_var_map = {
            "Wind": Model.Y_Wind, "Wave": Model.Y_Wave, "Kite": Model.Y_Kite,
            "Coaxial": Model.Y_Coaxial, "Tidal": Model.Y_Tidal
        }

        # --- Environmental exclusions ---
        if _has_env:
            print("\n  Loading environmental exclusion zones...")
            env_points = load_environmental_exclusions(
                hapc_path=HAPCExclusionPath,
                prohibited_path=ProhibitedMPAExclusionPath,
                restricted_path=RestrictedMPAExclusionPath)
            env_excluded = _build_exclusion_for_all_techs(InputDir, env_points,
                                                          label="Environmental")

            env_constrained = 0
            for tech_name, Y_var in Y_var_map.items():
                if tech_name in env_excluded and len(env_excluded[tech_name]) > 0:
                    for i in env_excluded[tech_name]:
                        Y_var[i].setub(0)
                    env_constrained += len(env_excluded[tech_name])
            print(f"\n  Environmental: {env_constrained:,} site-variables set to Y=0")
        else:
            print("\n  Environmental exclusions: DISABLED (no paths provided)")

        # --- Shipping exclusions ---
        if _has_ship:
            print("\n  Loading shipping exclusion zones...")
            ship_points = load_shipping_exclusion(ShippingExclusionPath)
            ship_excluded = _build_exclusion_for_all_techs(InputDir, ship_points,
                                                            label="Shipping")

            ship_constrained = 0
            for tech_name, Y_var in Y_var_map.items():
                if tech_name in ship_excluded and len(ship_excluded[tech_name]) > 0:
                    for i in ship_excluded[tech_name]:
                        Y_var[i].setub(0)
                    ship_constrained += len(ship_excluded[tech_name])
            print(f"\n  Shipping: {ship_constrained:,} site-variables set to Y=0")
        else:
            print("\n  Shipping exclusions: DISABLED (no path provided)")

        print("=" * 70 + "\n")
    else:
        print("\n  All exclusion constraints: DISABLED\n")

    opt = SolverFactory('gurobi', solver_io="python")
    opt.options['mipgap'] = 0.02

    #LCOE Target
    def LCOETarget_rule(Model, LCOE_Max):  
        EGWind=sum(Model.Y_Wind[i]*InputDir["WindEnergy"][:,i].mean()*InputDir["RatedPowerWindTurbine"][i]  for i in range(InputDir["NumWindSites"])) #Energy generation from wind turbines [MW Avg]
        EGWave=sum(Model.Y_Wave[i]*InputDir["WaveEnergy"][:,i].mean()*InputDir["RatedPowerWaveTurbine"][i]  for i in range(InputDir["NumWaveSites"])) #Energy generation from wave turbines [MW Avg]
        EGKite=sum(Model.Y_Kite[i]*InputDir["KiteEnergy"][:,i].mean()*InputDir["RatedPowerKiteTurbine"][i]  for i in range(InputDir["NumKiteSites"])) #Energy generation from kite turbines [MW Avg]
        EGCoaxial=sum(Model.Y_Coaxial[i]*InputDir["CoaxialEnergy"][:,i].mean()*InputDir["RatedPowerCoaxialTurbine"][i]  for i in range(InputDir["NumCoaxialSites"])) #Energy generation from coaxial turbines [MW Avg]
        EGTidal=sum(Model.Y_Tidal[i]*InputDir["TidalEnergy"][:,i].mean()*InputDir["RatedPowerTidalTurbine"][i]  for i in range(InputDir["NumTidalSites"])) #Energy generation from tidal turbines [MW Avg]

        TotalCurtailment=sum(Model.Delta[t] for t in range(InputDir["NumTimeSteps"]))/InputDir["NumTimeSteps"] #Average curtailment MW

        MWhYear=(EGWind+EGWave+EGKite+EGCoaxial+EGTidal-TotalCurtailment)*24*365.25 # MWh Avg per year


        Cost_Wind=sum(Model.Y_Wind[i]*InputDir["AnnualizedCostWind"][i]  for i in range(InputDir["NumWindSites"]))
        Cost_Wave=sum(Model.Y_Wave[i]*InputDir["AnnualizedCostWave"][i]  for i in range(InputDir["NumWaveSites"]))
        Cost_Kite=sum(Model.Y_Kite[i]*InputDir["AnnualizedCostKite"][i]  for i in range(InputDir["NumKiteSites"]))
        Cost_Coaxial=sum(Model.Y_Coaxial[i]*InputDir["AnnualizedCostCoaxial"][i]  for i in range(InputDir["NumCoaxialSites"]))
        Cost_Tidal=sum(Model.Y_Tidal[i]*InputDir["AnnualizedCostTidal"][i]  for i in range(InputDir["NumTidalSites"]))
        
        
        Cost_Transmission=sum(Model.s[i]*InputDir["AnnualizedCostTransmission"][i] for i in range(InputDir["NumTransSites"]))
        
        TotalCost=Cost_Wind+Cost_Wave+Cost_Kite+Cost_Coaxial+Cost_Tidal+Cost_Transmission #M$
        TotalCost=TotalCost*10**6 #USD (Convert from M$ to USD)


        return TotalCost<=LCOE_Max*MWhYear  

    SaveFeasibility, Save_LCOETarget, Save_LCOE_Achieved, SaveTotalMWAvg = list(), list(), list(), list()
    Save_Y_Wind, Save_Y_Wave, Save_Y_Kite, Save_Y_Coaxial, Save_Y_Tidal = list(), list(), list(), list(), list()
    Save_W_Wind, Save_W_Wave, Save_W_Kite, Save_W_Coaxial, Save_W_Tidal = list(), list(), list(), list(), list()
    Save_s, Save_Delta = list(), list()
    Save_TotalMWAvgWind, Save_TotalMWAvgWave, Save_TotalMWAvgKite, Save_TotalMWAvgCoaxial, Save_TotalMWAvgTidal, Save_totalMWAvgCurtailment = list(), list(), list(), list(), list(), list()
    Save_CostWind, Save_CostWave, Save_CostKite, Save_CostCoaxial, Save_CostTidal, Save_CostTransmission = list(), list(), list(), list(), list(), list()

    LowestLCOE=10**10
    for LCOETarget in tqdm(InputDir["LCOE_RANGE"]):
        
        #Skip based on the algorithm progress, avoid repeating the same LCOE*
        if LCOETarget<LowestLCOE:    
            Bypass=0
            
            #Upperbound For the LCOE Activate Constraint
            LCOETarget_rule_tmp=LCOETarget_rule(Model,LCOETarget)
            Model.LCOE_Target = Constraint(rule=LCOETarget_rule_tmp)
            print("Running Model With LCOE= %.2f" % LCOETarget)
            
            try:
                results=opt.solve(Model, tee=True)
            except:
                Bypass=1
                Model.del_component(Model.LCOE_Target)  
        
            if Bypass==0:
                if (results.solver.status == SolverStatus.ok) and (results.solver.termination_condition == TerminationCondition.optimal):
                    SaveFeasibility.append(1)
                    Save_LCOETarget.append(LCOETarget)
                    
                    Optimal_Y_Wind=np.array([Model.Y_Wind[i].value for i in range(InputDir["NumWindSites"])])
                    Optimal_Y_Wave=np.array([Model.Y_Wave[i].value for i in range(InputDir["NumWaveSites"])])
                    Optimal_Y_Kite=np.array([Model.Y_Kite[i].value for i in range(InputDir["NumKiteSites"])])
                    Optimal_Y_Coaxial=np.array([Model.Y_Coaxial[i].value for i in range(InputDir["NumCoaxialSites"])])
                    Optimal_Y_Tidal=np.array([Model.Y_Tidal[i].value for i in range(InputDir["NumTidalSites"])])
                    Optimal_W_Wind=np.array([Model.W_Wind[i].value for i in range(len(Model.W_Wind))])
                    Optimal_W_Wave=np.array([Model.W_Wave[i].value for i in range(len(Model.W_Wave))])
                    Optimal_W_Kite=np.array([Model.W_Kite[i].value for i in range(len(Model.W_Kite))])
                    Optimal_W_Coaxial=np.array([Model.W_Coaxial[i].value for i in range(len(Model.W_Coaxial))])
                    Optimal_W_Tidal=np.array([Model.W_Tidal[i].value for i in range(len(Model.W_Tidal))])
                    Optimal_s=np.array([Model.s[i].value for i in range(InputDir["NumTransSites"])])
                    Optimal_Delta=np.array([Model.Delta[i].value for i in range(InputDir["NumTimeSteps"])])
                    
                    Save_Y_Wind.append(Optimal_Y_Wind)
                    Save_Y_Wave.append(Optimal_Y_Wave)
                    Save_Y_Kite.append(Optimal_Y_Kite)
                    Save_Y_Coaxial.append(Optimal_Y_Coaxial)
                    Save_Y_Tidal.append(Optimal_Y_Tidal)
                    Save_W_Wind.append(Optimal_W_Wind)
                    Save_W_Wave.append(Optimal_W_Wave)
                    Save_W_Kite.append(Optimal_W_Kite)
                    Save_W_Coaxial.append(Optimal_W_Coaxial)
                    Save_W_Tidal.append(Optimal_W_Tidal)
                    Save_s.append(Optimal_s)
                    Save_Delta.append(Optimal_Delta)
                    

                    #Current LCOE
                    EGWind=sum(Optimal_Y_Wind[i]*InputDir["WindEnergy"][:,i].mean()*InputDir["RatedPowerWindTurbine"][i]  for i in range(InputDir["NumWindSites"])) #Energy generation from wind turbines [MW Avg]
                    EGWave=sum(Optimal_Y_Wave[i]*InputDir["WaveEnergy"][:,i].mean()*InputDir["RatedPowerWaveTurbine"][i]  for i in range(InputDir["NumWaveSites"])) #Energy generation from wave turbines [MW Avg]
                    EGKite=sum(Optimal_Y_Kite[i]*InputDir["KiteEnergy"][:,i].mean()*InputDir["RatedPowerKiteTurbine"][i]  for i in range(InputDir["NumKiteSites"])) #Energy generation from kite turbines [MW Avg]
                    EGCoaxial=sum(Optimal_Y_Coaxial[i]*InputDir["CoaxialEnergy"][:,i].mean()*InputDir["RatedPowerCoaxialTurbine"][i]  for i in range(InputDir["NumCoaxialSites"])) #Energy generation from coaxial turbines [MW Avg]
                    EGTidal=sum(Optimal_Y_Tidal[i]*InputDir["TidalEnergy"][:,i].mean()*InputDir["RatedPowerTidalTurbine"][i]  for i in range(InputDir["NumTidalSites"])) #Energy generation from tidal turbines [MW Avg]

                    TotalCurtailment=sum(Optimal_Delta[t] for t in range(InputDir["NumTimeSteps"]))/InputDir["NumTimeSteps"] #Average curtailment MW

                    MWhYear=(EGWind+EGWave+EGKite+EGCoaxial+EGTidal-TotalCurtailment)*24*365.25 # MWh Avg per year


                    Cost_Wind=sum(Optimal_Y_Wind[i]*InputDir["AnnualizedCostWind"][i]  for i in range(InputDir["NumWindSites"]))
                    Cost_Wave=sum(Optimal_Y_Wave[i]*InputDir["AnnualizedCostWave"][i]  for i in range(InputDir["NumWaveSites"]))
                    Cost_Kite=sum(Optimal_Y_Kite[i]*InputDir["AnnualizedCostKite"][i]  for i in range(InputDir["NumKiteSites"]))
                    Cost_Coaxial=sum(Optimal_Y_Coaxial[i]*InputDir["AnnualizedCostCoaxial"][i]  for i in range(InputDir["NumCoaxialSites"]))
                    Cost_Tidal=sum(Optimal_Y_Tidal[i]*InputDir["AnnualizedCostTidal"][i]  for i in range(InputDir["NumTidalSites"]))
                    
                    
                    Cost_Transmission=sum(Optimal_s[i]*InputDir["AnnualizedCostTransmission"][i] for i in range(InputDir["NumTransSites"]))
                    
                    TotalCost=Cost_Wind+Cost_Wave+Cost_Kite+Cost_Coaxial+Cost_Tidal+Cost_Transmission #M$
                    TotalCost=TotalCost*10**6 #USD
                
                    CurrentLCOE=TotalCost/MWhYear
                    LowestLCOE=CurrentLCOE
                    
                    Save_LCOE_Achieved.append(CurrentLCOE)
                    SaveTotalMWAvg.append(MWhYear/(24*365.25))
                    Save_TotalMWAvgWind.append(EGWind)
                    Save_TotalMWAvgWave.append(EGWave)
                    Save_TotalMWAvgKite.append(EGKite)
                    Save_TotalMWAvgCoaxial.append(EGCoaxial)
                    Save_TotalMWAvgTidal.append(EGTidal)
                    Save_totalMWAvgCurtailment.append(TotalCurtailment)
                    Save_CostWind.append(Cost_Wind)
                    Save_CostWave.append(Cost_Wave)
                    Save_CostKite.append(Cost_Kite)
                    Save_CostCoaxial.append(Cost_Coaxial)
                    Save_CostTidal.append(Cost_Tidal)
                    Save_CostTransmission.append(Cost_Transmission)
                    
                    
                    tqdm.write(
                        "LCOE %6.1f | Wind %8.1f  Wave %8.1f  Kite %8.1f  Coaxial %8.1f  Tidal %8.1f"
                        "  | Curtail %8.1f  Total %8.1f MW"
                        % (CurrentLCOE, EGWind, EGWave, EGKite, EGCoaxial, EGTidal,
                           TotalCurtailment,
                           EGWind+EGWave+EGKite+EGCoaxial+EGTidal-TotalCurtailment))

                    # --- per-design breakdown (which designs were chosen, how many, where) ---
                    _wind_names=_design_names(PathWindDesigns); _wave_names=_design_names(PathWaveDesigns)
                    _kite_names=_design_names(PathKiteDesigns); _coax_names=_design_names(PathCoaxialDesigns)
                    _tidal_names=_design_names(PathTidalDesigns)
                    _breakdown={
                        "Wind":   _per_design_breakdown(Optimal_Y_Wind,   InputDir["WindDesign"],   InputDir["WindLatLong"],   _wind_names),
                        "Wave":   _per_design_breakdown(Optimal_Y_Wave,   InputDir["WaveDesign"],   InputDir["WaveLatLong"],   _wave_names),
                        "Kite":   _per_design_breakdown(Optimal_Y_Kite,   InputDir["KiteDesign"],   InputDir["KiteLatLong"],   _kite_names),
                        "Coaxial":_per_design_breakdown(Optimal_Y_Coaxial,InputDir["CoaxialDesign"],InputDir["CoaxialLatLong"],_coax_names),
                        "Tidal":  _per_design_breakdown(Optimal_Y_Tidal,  InputDir["TidalDesign"],  InputDir["TidalLatLong"],  _tidal_names),
                    }
                    for _tech,_rows in _breakdown.items():
                        for _name,_ns,_nu,_pl in _rows:
                            tqdm.write("      %-8s %-52s %5d units across %3d sites" % (_tech, _name, _nu, _ns))
                    
                    # === Per-LCOE output: save .npz, plots, and deployment map in subfolder ===
                    if PerLCOE_OutputFolder is not None:
                        lcoe_tag = "LCOE_%d" % int(LCOETarget)
                        lcoe_subfolder = os.path.join(PerLCOE_OutputFolder, lcoe_tag)
                        os.makedirs(lcoe_subfolder, exist_ok=True)
                        
                        # Compute full time series for this solution
                        ts_wind, ts_wave, ts_kite, ts_coaxial, ts_tidal, ts_curtailment, ts_total = _compute_timeseries(
                            InputDir, Optimal_Y_Wind, Optimal_Y_Wave, Optimal_Y_Kite, Optimal_Y_Coaxial, Optimal_Y_Tidal, Optimal_Delta)
                        
                        time_axis = _make_time_axis(InputDir["TimeList"])
                        trans_capacity = InputDir["RatedPowerMWTransmissionMW"]
                        
                        # Save per-LCOE .npz
                        npz_path = os.path.join(lcoe_subfolder, "Portfolio_%s.npz" % lcoe_tag)
                        np.savez(npz_path,
                            LCOE_Target=LCOETarget,
                            LCOE_Achieved=CurrentLCOE,
                            Total_MW_Avg=MWhYear/(24*365.25),
                            Wind_MW_Avg=EGWind,
                            Wave_MW_Avg=EGWave,
                            Kite_MW_Avg=EGKite,
                            Coaxial_MW_Avg=EGCoaxial,
                            Tidal_MW_Avg=EGTidal,
                            Curtailment_MW_Avg=TotalCurtailment,
                            Cost_Wind_MperYear=Cost_Wind,
                            Cost_Wave_MperYear=Cost_Wave,
                            Cost_Kite_MperYear=Cost_Kite,
                            Cost_Coaxial_MperYear=Cost_Coaxial,
                            Cost_Tidal_MperYear=Cost_Tidal,
                            Cost_Transmission_MperYear=Cost_Transmission,
                            # per-design deployment (object arrays: name, units, sites, placements)
                            DesignBreakdown_Wind=np.array(_breakdown["Wind"], dtype=object),
                            DesignBreakdown_Wave=np.array(_breakdown["Wave"], dtype=object),
                            DesignBreakdown_Kite=np.array(_breakdown["Kite"], dtype=object),
                            DesignBreakdown_Coaxial=np.array(_breakdown["Coaxial"], dtype=object),
                            DesignBreakdown_Tidal=np.array(_breakdown["Tidal"], dtype=object),
                            Total_Cost_MperYear=Cost_Wind+Cost_Wave+Cost_Kite+Cost_Coaxial+Cost_Tidal+Cost_Transmission,
                            Y_Wind=Optimal_Y_Wind,
                            Y_Wave=Optimal_Y_Wave,
                            Y_Kite=Optimal_Y_Kite,
                            Y_Coaxial=Optimal_Y_Coaxial,
                            Y_Tidal=Optimal_Y_Tidal,
                            W_Wind=Optimal_W_Wind,
                            W_Wave=Optimal_W_Wave,
                            W_Kite=Optimal_W_Kite,
                            W_Coaxial=Optimal_W_Coaxial,
                            W_Tidal=Optimal_W_Tidal,
                            s_Transmission=Optimal_s,
                            Delta=Optimal_Delta,
                            TimeSeries_Wind_MW=ts_wind,
                            TimeSeries_Wave_MW=ts_wave,
                            TimeSeries_Kite_MW=ts_kite,
                            TimeSeries_Coaxial_MW=ts_coaxial,
                            TimeSeries_Tidal_MW=ts_tidal,
                            TimeSeries_Curtailment_MW=ts_curtailment,
                            TimeSeries_Total_MW=ts_total,
                            TimeList=InputDir["TimeList"],
                            Transmission_Capacity_MW=trans_capacity,
                        )
                        print("  Saved per-LCOE file: %s" % npz_path)
                        
                        # Generate time series plots
                        _plot_total_generation(time_axis, ts_total, LCOETarget, CurrentLCOE, trans_capacity,
                            os.path.join(lcoe_subfolder, "Plot_TotalGeneration.png"))
                        _plot_stacked_generation(time_axis, ts_wind, ts_wave, ts_kite, ts_coaxial, ts_tidal, LCOETarget, CurrentLCOE, trans_capacity,
                            os.path.join(lcoe_subfolder, "Plot_StackedGenByTech.png"))
                        _plot_curtailment(time_axis, ts_curtailment, LCOETarget, CurrentLCOE,
                            os.path.join(lcoe_subfolder, "Plot_Curtailment.png"))
                        
                        # Generate deployment map
                        _plot_deployment_map(InputDir, Optimal_Y_Wind, Optimal_Y_Wave, Optimal_Y_Kite, Optimal_Y_Coaxial, Optimal_Y_Tidal, Optimal_s,
                            LCOETarget, CurrentLCOE, int(Optimal_Y_Wind.sum()+Optimal_Y_Wave.sum()+Optimal_Y_Kite.sum()+Optimal_Y_Coaxial.sum()+Optimal_Y_Tidal.sum()),
                            os.path.join(lcoe_subfolder, "Plot_DeploymentMap.png"),
                            HAPCExclusionPath=HAPCExclusionPath, ProhibitedMPAExclusionPath=ProhibitedMPAExclusionPath,
                            RestrictedMPAExclusionPath=RestrictedMPAExclusionPath, ShippingExclusionPath=ShippingExclusionPath)
                        
                        print("  Saved all outputs for %s" % lcoe_tag)
                    # === End per-LCOE output ===
                    
                    #Delete constraint for its modification in the next step of the for loop
                    Model.del_component(Model.LCOE_Target)

                else:# Something else is wrong
                    Model.del_component(Model.LCOE_Target)
                    SaveFeasibility.append(0)
                    Save_LCOETarget.append(None)
                    Save_LCOE_Achieved.append(None)
                    SaveTotalMWAvg.append(None)   
                    
                    Save_Y_Wind.append(None)
                    Save_Y_Wave.append(None)
                    Save_Y_Kite.append(None)
                    Save_Y_Coaxial.append(None)
                    Save_Y_Tidal.append(None)
                    Save_W_Wind.append(None)
                    Save_W_Wave.append(None)
                    Save_W_Kite.append(None)
                    Save_W_Coaxial.append(None)
                    Save_W_Tidal.append(None)
                    Save_s.append(None)
                    Save_Delta.append(None)
                    Save_TotalMWAvgWind.append(None)
                    Save_TotalMWAvgWave.append(None)
                    Save_TotalMWAvgKite.append(None)
                    Save_TotalMWAvgCoaxial.append(None)
                    Save_TotalMWAvgTidal.append(None)
                    Save_totalMWAvgCurtailment.append(None)
                    break

    #Save Results
    if SavePath!=None:
        np.savez(SavePath, 
                ReadMe=ReadMe,
                #Model Inputs
                PathWindDesigns=PathWindDesigns,
                PathWaveDesigns=PathWaveDesigns,
                PathKiteDesigns=PathKiteDesigns,
                PathCoaxialDesigns=PathCoaxialDesigns,
                PathTidalDesigns=PathTidalDesigns,
                PathTransmissionDesign=PathTransmissionDesign,
                LCOE_RANGE=LCOE_RANGE,
                Max_CollectionRadious=Max_CollectionRadious,
                MaxDesignsWind=MaxDesignsWind,
                MaxDesingsWave=MaxDesingsWave,
                MaxDesingsKite=MaxDesingsKite,
                MaxDesignsCoaxial=MaxDesignsCoaxial,
                MaxDesignsTidal=MaxDesignsTidal,
                MinNumWindTurb=MinNumWindTurb,
                MinNumWaveTurb=MinNumWaveTurb,
                MinNumKiteTrub=MinNumKiteTrub,
                MinNumCoaxialTurb=MinNumCoaxialTurb,
                MinNumTidalTurb=MinNumTidalTurb,

                #Model Outputs
                SaveFeasibility=SaveFeasibility,
                Save_LCOETarget=Save_LCOETarget,
                Save_LCOE_Achieved=Save_LCOE_Achieved,
                SaveTotalMWAvg=SaveTotalMWAvg,
                Save_TotalMWAvgWind=Save_TotalMWAvgWind,
                Save_TotalMWAvgWave=Save_TotalMWAvgWave,
                Save_TotalMWAvgKite=Save_TotalMWAvgKite,
                Save_TotalMWAvgCoaxial=Save_TotalMWAvgCoaxial,
                Save_TotalMWAvgTidal=Save_TotalMWAvgTidal,
                Save_totalMWAvgCurtailment=Save_totalMWAvgCurtailment,
                
                Save_Y_Wind=Save_Y_Wind,
                Save_Y_Wave=Save_Y_Wave,
                Save_Y_Kite=Save_Y_Kite,
                Save_Y_Coaxial=Save_Y_Coaxial,
                Save_Y_Tidal=Save_Y_Tidal,
                Save_W_Wind=Save_W_Wind,
                Save_W_Wave=Save_W_Wave,
                Save_W_Kite=Save_W_Kite,
                Save_W_Coaxial=Save_W_Coaxial,
                Save_W_Tidal=Save_W_Tidal,
                Save_s=Save_s,
                Save_Delta=Save_Delta,
                )

    # === Run-level summary outputs (CSV, efficient frontier, stacked costs) ===
    if PerLCOE_OutputFolder is not None:
        os.makedirs(PerLCOE_OutputFolder, exist_ok=True)

        # Save combined .npz into the main run folder
        combined_path = os.path.join(PerLCOE_OutputFolder, "Combined_AllLCOE.npz")
        np.savez(combined_path,
                ReadMe=ReadMe,
                PathWindDesigns=PathWindDesigns,
                PathWaveDesigns=PathWaveDesigns,
                PathKiteDesigns=PathKiteDesigns,
                PathCoaxialDesigns=PathCoaxialDesigns,
                PathTidalDesigns=PathTidalDesigns,
                PathTransmissionDesign=PathTransmissionDesign,
                LCOE_RANGE=LCOE_RANGE,
                Max_CollectionRadious=Max_CollectionRadious,
                MaxDesignsWind=MaxDesignsWind,
                MaxDesingsWave=MaxDesingsWave,
                MaxDesingsKite=MaxDesingsKite,
                MaxDesignsCoaxial=MaxDesignsCoaxial,
                MaxDesignsTidal=MaxDesignsTidal,
                MinNumWindTurb=MinNumWindTurb,
                MinNumWaveTurb=MinNumWaveTurb,
                MinNumKiteTrub=MinNumKiteTrub,
                MinNumCoaxialTurb=MinNumCoaxialTurb,
                MinNumTidalTurb=MinNumTidalTurb,
                SaveFeasibility=SaveFeasibility,
                Save_LCOETarget=Save_LCOETarget,
                Save_LCOE_Achieved=Save_LCOE_Achieved,
                SaveTotalMWAvg=SaveTotalMWAvg,
                Save_TotalMWAvgWind=Save_TotalMWAvgWind,
                Save_TotalMWAvgWave=Save_TotalMWAvgWave,
                Save_TotalMWAvgKite=Save_TotalMWAvgKite,
                Save_TotalMWAvgCoaxial=Save_TotalMWAvgCoaxial,
                Save_TotalMWAvgTidal=Save_TotalMWAvgTidal,
                Save_totalMWAvgCurtailment=Save_totalMWAvgCurtailment,
                Save_CostWind=Save_CostWind,
                Save_CostWave=Save_CostWave,
                Save_CostKite=Save_CostKite,
                Save_CostCoaxial=Save_CostCoaxial,
                Save_CostTidal=Save_CostTidal,
                Save_CostTransmission=Save_CostTransmission,
                Save_Y_Wind=Save_Y_Wind,
                Save_Y_Wave=Save_Y_Wave,
                Save_Y_Kite=Save_Y_Kite,
                Save_Y_Coaxial=Save_Y_Coaxial,
                Save_Y_Tidal=Save_Y_Tidal,
                Save_W_Wind=Save_W_Wind,
                Save_W_Wave=Save_W_Wave,
                Save_W_Kite=Save_W_Kite,
                Save_W_Coaxial=Save_W_Coaxial,
                Save_W_Tidal=Save_W_Tidal,
                Save_s=Save_s,
                Save_Delta=Save_Delta,
                )
        print("Saved combined results: %s" % combined_path)

        # Filter to feasible solutions only for summary plots
        feas_idx = [i for i, f in enumerate(SaveFeasibility) if f == 1]
        if len(feas_idx) > 0:
            f_lcoe_target = [Save_LCOETarget[i] for i in feas_idx]
            f_lcoe_achieved = [Save_LCOE_Achieved[i] for i in feas_idx]
            f_mw_avg = [SaveTotalMWAvg[i] for i in feas_idx]
            f_mw_wind = [Save_TotalMWAvgWind[i] for i in feas_idx]
            f_mw_wave = [Save_TotalMWAvgWave[i] for i in feas_idx]
            f_mw_kite = [Save_TotalMWAvgKite[i] for i in feas_idx]
            f_mw_coaxial = [Save_TotalMWAvgCoaxial[i] for i in feas_idx]
            f_mw_tidal = [Save_TotalMWAvgTidal[i] for i in feas_idx]
            f_mw_curt = [Save_totalMWAvgCurtailment[i] for i in feas_idx]
            f_cost_wind = [Save_CostWind[i] for i in feas_idx]
            f_cost_wave = [Save_CostWave[i] for i in feas_idx]
            f_cost_kite = [Save_CostKite[i] for i in feas_idx]
            f_cost_coaxial = [Save_CostCoaxial[i] for i in feas_idx]
            f_cost_tidal = [Save_CostTidal[i] for i in feas_idx]
            f_cost_trans = [Save_CostTransmission[i] for i in feas_idx]

            # Reverse order so lowest LCOE comes first (more intuitive for plots/CSV)
            f_lcoe_target = f_lcoe_target[::-1]
            f_lcoe_achieved = f_lcoe_achieved[::-1]
            f_mw_avg = f_mw_avg[::-1]
            f_mw_wind = f_mw_wind[::-1]
            f_mw_wave = f_mw_wave[::-1]
            f_mw_kite = f_mw_kite[::-1]
            f_mw_coaxial = f_mw_coaxial[::-1]
            f_mw_tidal = f_mw_tidal[::-1]
            f_mw_curt = f_mw_curt[::-1]
            f_cost_wind = f_cost_wind[::-1]
            f_cost_wave = f_cost_wave[::-1]
            f_cost_kite = f_cost_kite[::-1]
            f_cost_coaxial = f_cost_coaxial[::-1]
            f_cost_tidal = f_cost_tidal[::-1]
            f_cost_trans = f_cost_trans[::-1]

            # CSV summary
            _write_summary_csv(
                os.path.join(PerLCOE_OutputFolder, "Summary.csv"),
                f_lcoe_target, f_lcoe_achieved, f_mw_avg,
                f_mw_wind, f_mw_wave, f_mw_kite, f_mw_coaxial, f_mw_tidal, f_mw_curt,
                f_cost_wind, f_cost_wave, f_cost_kite, f_cost_coaxial, f_cost_tidal, f_cost_trans)
            print("Saved Summary.csv")

            # Efficient frontier plot
            _plot_efficient_frontier(f_lcoe_target, f_mw_avg,
                os.path.join(PerLCOE_OutputFolder, "Plot_EfficientFrontier.png"))
            print("Saved Plot_EfficientFrontier.png")

            # Stacked cost plot
            _plot_stacked_costs(f_lcoe_target, f_cost_wind, f_cost_wave, f_cost_kite, f_cost_coaxial, f_cost_tidal, f_cost_trans,
                os.path.join(PerLCOE_OutputFolder, "Plot_StackedCosts.png"))
            print("Saved Plot_StackedCosts.png")
    # === End run-level summary outputs ===