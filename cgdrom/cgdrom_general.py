##### functions to implement C+GDROM - General Model 
import pandas as pd
import numpy as np

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def general_default_parameters(I_stat, size_ratio, flood_intercep=1, flood_coef=1.75):
    
    # initialization
    I99, I80, I50, I30, I10, I_mean = I_stat

    # **********************
    # recommended default parameters in the General Model 
    if size_ratio > 0.4:
        Q1 = I99
        Q2 = I_mean
        Q3 = I50
    else:
        Q1 = I99
        Q2 = I50
        Q3 = I30
    
    # empirical flood control release when It > I99
    R_flood = max([(flood_intercep - flood_coef*size_ratio)*I99, I_mean])
    
    return Q1, Q2, Q3, R_flood

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def predict_general_daily(It, St0, Rt0, daily_Sty, Q1, Q2, Q3, R_flood, I_stat, S_info, alpha=2, beta=0.5):    
    
    # **********************
    # initialization
    I99, I80, I50, I30, I10, I_mean = I_stat
    S_cap, S_dead, S_flood_cap, size_ratio =  S_info
    
    # **********************
    # predict current day release using C+GDROM General Model
    # %% Module 1 for major flood operations
    if It >= I99:           
        Rt = R_flood

        # further adjusting flood releases considering storage levels 
        if St0 < daily_Sty:
            Rt = Rt - (daily_Sty-St0)      
        else: 
            R2f = (St0-daily_Sty)/(S_cap-daily_Sty)*(Q1-Q2) + Q2
            if Rt > R2f: # in case that storage level is low and release under Module 2 is lower than that under Module 1
                Rt = R2f

    # %% Module 2 for normal operations when daily initial storage >= daily typical values
    elif St0 >= daily_Sty:
        Rt = (St0-daily_Sty)/(S_cap-daily_Sty)*(Q1-Q2) + Q2

    # %% Module 3 for normal operations when daily initial storage < daily typical values but >= S_dead
    elif St0 >= S_dead: 
        Rt = Q3

    # %% Additional rules in case daily initial storage is below dead storage level
    else:
        Rt = min([It, I10])

    # %% Additional rules in case daily initial storage is above the top of flood control zone
    if St0 > S_flood_cap:
        Rt = max([It, Rt])

    # **********************
    # ramping rate constraints
    if Rt > alpha * Rt0 and Rt0 != 0 and It < I80:
        Rt = alpha * Rt0
    if Rt < beta * Rt0:
        Rt = beta * Rt0
    if Rt < 0: # avoid nagative release
        Rt = 0 

    # **********************
    # determing daily ending storage based on water balance
    St = St0 + It - Rt
    if St > S_cap: # avoid overtopping in emergency conditions
        Rt = St0 + It - S_cap
        St = S_cap
    if St < 0: # avoid simulation deviation caused by errors in computed net inflow series (not needed when using simulated inflow series from hydrological models)
        St = 0
        Rt = 0
            
    return Rt, St


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def predict_general_series(df, df_Sty, S0, Q1, Q2, Q3, R_flood, I_stat, S_info, alpha=2, beta=0.5):
    
    pre_R = []
    pre_S = []
    Si = S0 # assign the initial storage of the studied period
    Ri = df['netinflow'][0]

    for i, row in df.iterrows():
        Ri0 = Ri
        Si0 = Si # the ending storage of previous day as the initial storage of current day 
        pre_S.append(Si0)
        
        # typical storage level for current DOY
        if type(df_Sty) != np.float:
            if (row['Time'].is_leap_year == True and row['month'] == 2 and row['day_of_month']==29):
                daily_Sty = df_Sty[(df_Sty['month']==2)&(df_Sty['day_of_month']==28)]['typical_S'].values[0]
            else:
                daily_Sty = df_Sty[(df_Sty['month']==row['month'])&(df_Sty['day_of_month']==row['day_of_month'])]['typical_S'].values[0]
        else:
            daily_Sty = df_Sty
            
        # daily operation simulation
        Ri, Si = predict_general_daily(row['netinflow'], Si0, Ri0, daily_Sty, Q1, Q2, Q3, R_flood, I_stat, S_info)
        pre_R.append(Ri)
            
    return pre_R, pre_S
