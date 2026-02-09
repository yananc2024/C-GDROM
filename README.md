# C+GDROM: Hybrid Empirical–Conceptual Reservoir Operation Model

This repository provides an open-source implementation of **C+GDROM**, a hybrid empirical–conceptual reservoir operation framework for daily reservoir release and storage simulation, designed for use in large-scale hydrological and land surface modeling applications. C+GDROM represents reservoir operations using a **module-based structure** with explicit transition logic and release formulations.

This repository contains the source code and documentation for implementing the **C+GDROM** framework (in Python), with the parameters of 256 studied U.S. reservoirs provided. As a generic reservoir model, users can follow the demonstration example to prepare input data and run the model for their reservoirs. Further details of the framework are described in the manuscript **A Hybrid Empirical and Conceptual Model for Improving the Representation of Reservoirs with Limited Data in Hydrological Models** submitted to *Water Resources Research*.

## Status
This repository accompanies a manuscript currently under revision at *Water Resources Research*. The code will continue to be updated.

## Repository Structure

### `data`
Historical in-situ operation records (1990–2015 or longer) for six U.S. reservoirs used in demonstration examples. Files are named using GRanD IDs. For the full dataset of studied reservoirs, please refer to the HydroShare repository (Chen et al., 2025).

Note: Demonstration reservoirs include long-term in-situ data for validation purposes. In-situ data are not required to apply C+GDROM in practice.

### `parameters`
- `metadata_256reservoirs.csv`: Conceptual storage curve parameters, statistics of reservoir inflows, and information of reservoir storage capacity, for each of 256 studied U.S. reservoirs. This file includes all the needed model setup information to run C+GDROM *General Model*.
- `fc_parameters_cali0809.csv`: release module parameters of *Flood Control Model* for 127 flood control-dominated reservoirs, calibrated using operation data of 2008-2009.
- `irr_parameters_cali0809.csv`: release module parameters (including three critical days-of-year associated with module transitions) of *Irrigation Model* for 64 irrigation-dominated reservoirs, calibrated using operation data of 2008-2009.

### `cgdrom`
Source code for implementing C+GDROM framework:
- `conceptual_s_curve.py`: deriving the reservoir-specific conceptual storage regulation curve
- `cgdrom_general.py`: *General Model*, a model applicable to reservoirs with different purposes and sizes; no module calibration required 
- `cgdrom_fc.py`: *Flood Control Model*, a model variant for flood control-dominated reservoirs; requires module calibration with >=2-year operation data (inflow, release, storage)
- `cgdrom_irr.py`: *Irrigation Model*, a model variant for irrigation-dominated reservoirs; requires module calibration with >=2-year operation data (inflow, release, storage)

### `notebooks`
- `Conceptual_S_curve.ipynb`: walk-through example to derive the six parameters that define the conceptual storage regulation curve based on historical storage series (either observed or remotely sensed).
- `General_Model_demo.ipynb`: walk-through example for *General Model* implementation with default module parameters.
- `Flood_Control_Model_demo.ipynb` & `Irrigation_Model_demo.ipynb` : walk-through example for model implementation based on pre-calibrated module parameters, and model calibration procedure using 2-year operation data.

`README.md`: Project description and setup guide

`LICENSE`: License file 


## How to Run the C+GDROM *General Model*

This section provides a step-by-step guide to applying the C+GDROM *General Model* to a reservoir. The process involves preparing input data, deriving conceptual-storage-cruve parameters, and executing the model through provided Jupyter notebooks.

### Step 1: Prepare input data

To run the model, the following reservoir data information is required:

**1. Inflow statistics**
Daily inflow statistics, including:
- the 99th, 80th, 50th, 30th, 10th (*I99, I80, I50, I30, I10*), and mean of daily inflow values (*I_mean*)

These statistics may be computed from observed inflow records, or streamflow simulations from hydrological models.

**2. Storage capacity information**
Required parameters:
- Total capacity (*S_cap*)
- Dead storage (*S_dead*)
- Flood control capacity (*S_flood_cap*)

These values can be obtained from GRanD or similar reservoir databases.  
If unavailable, approximate values may be used:
- *S_dead ≈ 0.1 × S_cap*  
- *S_flood_cap ≈ 0.99 × S_cap*  

**3. Storage data**
Historical in-situ or remotely sensed storage data for deriving the conceptual storage curve.

**4. Inflow time series**
Daily inflow and date for the simulation period.

Note: `metadata_256reservoirs.csv` includes the statistics of reservoir inflows, and information of storage capacity for the 256 reservoirs covered in the paper. For some reservoirs, there exist negative inflow statistics (10th and 30th inflows, referred to as I10 and I30 in the csv file). This is because these statistics were obtained based on the series of *net* inflow to reservoirs (computed using daily water balance; detailed in Chen et al., 2025), which may be negative due to large evaporation loss in dry season. Errors in release or storage observations may also cause such issues in net inflow series. When negative inflow statistics are used as recommended release decisions, we adjust the release to zero. In addition, since all the studied reservoirs have long-term operation records (≥25 years), this study retrieved the storage capacity features from historical data for simplicity and reliability. Specifically, historical maximum and minimum storage values are used to approximate total storage capacity (*S_cap*) and dead storage capacity (*S_dead*), respectively.


### Step 2: Derive conceptual-storage-cruve parameters

Reservoir-specific conceptual storage regulation curve is required input for C+GDROM, which is parameterized using six parameters: $A1$-$A4$ (timing parameters) and ${S_{A4-A1}$ & ${S_{A2-A3}$ (representative storage levels of transition stages). `conceptual_s_curve.py` defines a function `derive_curve_parameters()` to derive these parameters for individual reservoirs. `conceptual_s_curve.py` provides another function `doy_typical_storage()`, which returns the typical storage levels for each day-of-year (DOY) based on the pre-derived storage curve parameters for C+GDROM implementation.

Based on historical storage data (observed or RS-derived), users can compute daily median storage for each DOY, which serves as the input (series length=365) to the function `derive_curve_parameters()`. To better accommodate the temporal resolution of RS storage estimates, function `derive_curve_parameters()` also takes the series of monthly characteristic storage levels (series length=12, representing January to December) as input. Users need to process RS storage data on their own and only provide monthly median values (or other monthly representative values).

After obtaining these curve parameters, reservoir size ratio, an important reservoir feature used in C+GDROM, can be computed using:
$$size ratio = S_cap-min\{S_{A4-A1}, S_{A2-A3}\} / I_mean*365$$ 
where *I_mean* represents multi-year average daily inflow volume.

Notably, when the relative difference between ${S_{A4-A1}$ and ${S_{A2-A3}$ is less than 10%, seasonal storage variation is considered negligible, and a single constant value (i.e., median storage) is used as the characteristic storage level throughout the year (with curve shape noted as 'single'). 

The derived conceptual-storage-curve parameters for 256 studied reservoirs are provided in `metadata_256reservoirs.csv` for demonstration. Users may follow the steps in `Conceptual_S_curve.ipynb` to derive curve parameters for their reservoirs.

### Step 3: Run the model

Given basic reservoir features and pre-derived conceptual-storage-curve parameters (all saved in `metadata_256reservoirs.csv`), C+GDROM *General Model* can be easily implemented following the steps in the notebook `General_Model_demo.ipynb`.

Core functions of *General Model* are defined in the script `cgdrom_general.py`, including:
* general_default_parameters(): returning the default release module parameters in *General Model* based on inflow statistics and reservoir size ratio
* predict_general_daily(): returning the predicted release decision and end-of-day storage using *General Model* for a day
* predict_general_series(): returning the predicted release and storage series using *General Model* for multiple days (given inflow series of studied period)

Details of the parameters for each function can be found in the notebook `General_Model_demo.ipynb` and source code `cgdrom_general.py`.


## How to Run the C+GDROM *Flood Control Model* & *Irrigation Model*

The basic procedure to run specialized C+GDROM models (*Flood Control Model* & *Irrigation Model*) are consistent with those of *General Model*. The only difference is that specialized models require release module calibration using limited in-situ operation records (>= 2 years of daily inflow, release, and storage). We assume that the operation records from 2008 to 2009 are available for module calibration, and provide the calibrated module parameters in `fc_parameters_cali0809.csv` (for 127 flood control-dominated reservoirs) and `irr_parameters_cali0809.csv` (for 64 flood irrigation-dominated reservoirs). Model implementation based on pre-calibrated module parameters, and model calibration procedure using 2-year operation data, are specificed in the Jupyter notebooks `Flood_Control_Model_demo.ipynb` and `Irrigation_Model_demo.ipynb`.

Core functions of *Flood Control Model* are defined in the script `cgdrom_fc.py`, including: 
* fc_module_calibration(): returning the calibrated release module parameters in *Flood Control Model* based on the provided operation records
* predict_fc_daily(): returning the predicted release decision and end-of-day storage using *Flood Control Model* for a day
* predict_fc_series(): returning the predicted release and storage series using *Flood Control Model* for multiple days (given inflow series of studied period)

Core functions of *Irrigation Model* are defined in the script `cgdrom_irr.py`, including: 
* module_trans_doys(): returning three critical DOYs associated with module transition in *Irrigation Model*
* irr_module_calibration(): returning the calibrated release module parameters in *Irrigation Model* based on the provided operation records
* predict_irr_daily(): returning the predicted release decision and end-of-day storage using *Irrigation Model* for a day
* predict_irr_series(): returning the predicted release and storage series using *Irrigation Model* for multiple days (given inflow series of studied period)

For details on the parameters used in each function, please refer to the notebooks and source code.


## Tips on coupling the C+GDROM with hydrological models

This repository provides the source code to implement C+GDROM for reservoir operation simulation in Python. If users intend to integrate the C+GDROM into a hydrological model for improved reservoir representation, we suggest that users follow the steps introduced here to prepare parameter files in Python (e.g., `metadata_256reservoirs.csv`), and then add a reservoir component following the daily operation prediction function (i.e., `predict_general_daily()`, or `predict_fc_daily()`, or `predict_irr_daily()`) to the hydrological models. This reservoir component receives daily streamflow simulated from hydrological models as input, and and returns reservoir releases as altered streamflow for downstream hydrologic modeling to achieve two-way coupling.
 

## License
This project is licensed under the MIT License.

## Contact
If you have any questions or would like to contribute, please contact Yanan Chen (yananc2024@outlook.com; chenyn@sustech.edu.cn)


## References
- Chen, Y., Zheng, Y., Cai, X., Bin Y., and Zheng, Z. (under revision). [A Hybrid Empirical and Conceptual Model for Improving the Representation of Reservoirs with Limited Data in Hydrological Models], *Water Resources Research*.
- Chen, Y., Cai, X., and Li, D. (2025). [Historical Operation Data of 256 Reservoirs in Contiguous United States], *HydroShare*, https://www.hydroshare.org/resource/092720588e2e4524bf2674235ff69d81.


