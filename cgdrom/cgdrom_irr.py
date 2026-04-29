##### functions to implement C+GDROM - Irrigation Model
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def module_trans_doys(I_S_data):
    
    # when the input is a data frame of inflow and storage series during multiple years
    if type(I_S_data) == pd.core.frame.DataFrame:  
        # adjusting DOY to avoid issues related to leap year 
        df_adjusted = I_S_data.copy()
        df_adjusted['Time'] = pd.to_datetime(df_adjusted["Time"])
        df_adjusted["is_leap_year"] = df_adjusted.Time.dt.is_leap_year
        df_adjusted["DOY_adjusted"] = df_adjusted.apply(
        lambda row: row.DOY - 1 
        if (row.is_leap_year and row.DOY >= 60) 
        else row.DOY, 
        axis=1)
    
        doy_avg_in = df_adjusted.groupby(['DOY_adjusted'])['netinflow'].mean()
        doy_avg_s = df_adjusted.groupby(['DOY_adjusted'])['storage'].mean()
    
    # when the input is a list of mean inflow & storage series for each day of year
    else:
        doy_avg_in, doy_avg_s = I_S_data
        doy_avg_in = pd.Series(doy_avg_in)
    
    # determining the critical DOYs
    DOY_lst = [i for i in range(1,366)]
    annual_avg_in = doy_avg_in.mean()
    rolling_avg_in = doy_avg_in.rolling(7).mean()
    
    DOY1 = int(np.interp(annual_avg_in, rolling_avg_in[60:150], DOY_lst[60:150]))

    DOY2 = DOY_lst[np.where(doy_avg_s==doy_avg_s.min())[0][0]]
    if DOY2 <150:
        DOY2 = 300
        
    DOY3 = DOY_lst[np.where(doy_avg_s==doy_avg_s.max())[0][0]] 

    return DOY1, DOY2, DOY3


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def irr_module_calibration(df1, df_Sty, IR_DOY1, IR_DOY2, IR_DOY3, I99, I80):
    
    if type(df_Sty) == np.float:
        df1['typical_S'] = df_Sty
        df1['storage_diff'] = df1['storage'] - df_Sty
    else:
        df1 = df1.merge(df_Sty[['month', 'day_of_month', 'typical_S']], left_on=['month', 'day_of_month'], right_on=['month', 'day_of_month'])
        df1['storage_diff'] = df1['storage'] - df1['typical_S']  
        
    # ****************************
    # %M1: when I > major flood threshold (i.e., f_threshold1)
    df_M1 = df1[df1['netinflow']>=I99]
    if len(df_M1) != 0:
        M1_release = df_M1['outflow'].mean()
    else:
        M1_release = 'default'

    # ****************
    # %M2: governing high-flow condition (I99 >= I >= I80), typically in snow-melt period in U.S.
    # recommended to using default formulations of Module 2 in the General Model
        
        
    # ****************
    # %M3: Irrigation season release
    df_M3 = df1[(df1['DOY']>=IR_DOY3) & (df1['DOY']<IR_DOY2)]
    df_M3 = df_M3[(df_M3['netinflow']<I80)]
    M3_release = (df_M3['outflow'].median())

    
    # ****************
    # %M4: constant release, applied during spring high-flow season
    df_M4 = df1[(df1['DOY']>=IR_DOY1) & (df1['DOY']<IR_DOY3)]
    df_M4 = df_M4[(df_M4['netinflow']<I80)]
    if len(df_M4!=0):
        M4_release = df_M4['outflow'].median()
    else:
        M4_release = M3_release # in case no  
    
    
    # ****************************
    # %M5: constant release, applied during winter low-flow season
    df_M5 = df1[(df1['DOY']<IR_DOY1) | (df1['DOY']>=IR_DOY2)] 
    df_M5 = df_M5[df_M5['netinflow']<I80]
    M5_release = df_M5['outflow'].median()

                 
    return M1_release, M3_release, M4_release, M5_release


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def predict_irr_daily(It, St0, Rt0, DOYt, daily_Sty, irr_modules, irr_DOYs, I_stat, S_info,
                     default_para, alpha=2, beta=0.5):
    
    # **********************
    # initialization
    M1_R, M3_R, M4_R, M5_R = irr_modules
    IR_DOY1, IR_DOY2, IR_DOY3 = irr_DOYs
    I99, I80, I50, I30, I10, I_mean = I_stat
    S_cap, S_dead, S_flood_cap, size_ratio =  S_info
    Q1, Q2, Q3, R_flood = default_para

    # **********************
    # predict current day release using C+GDROM Irrigation Model
    # %% Module 1 for major flood operations
    if It >= I99:
        if M1_R == 'default':
            Rt = R_flood
        else:
            Rt = min([float(M1_R), It])

        # further adjusting flood releases considering storage levels 
        if St0 < daily_Sty:
            Rt = Rt - (daily_Sty-St0)       
    
    # %% Module 2 applied when I99 >= I >= I80
    elif It >= I80:
        Rt = max([(St0-daily_Sty)/(S_flood_cap-daily_Sty)*(I99-Q2) + Q2, Q2])
                
        # further adjusting flood releases considering storage levels 
        if St0 < daily_Sty:
            Rt = Rt - (daily_Sty-St0)   

    # %% Module 3 applied during irrigation season 
    elif DOYt >= IR_DOY3 and DOYt < IR_DOY2:
        if St0-daily_Sty > 0:
            Rt = max([M3_R, (St0-daily_Sty)/(S_flood_cap-daily_Sty)*(I99-Q2) + Q2])
        else:
            Rt = M3_R
     
    # %% Module 4 applied during spring high-flow season
    elif DOYt >= IR_DOY1 and DOYt < IR_DOY2:
        if St0-daily_Sty > 0:
            Rt = max([M4_R, (St0-daily_Sty)/(S_flood_cap-daily_Sty)*(I99-Q2) + Q2])
        else:
            Rt = M4_R
    
    # %% Module 5 applied during winter low-flow season
    else:
        if St0-daily_Sty > 0:
            Rt = max([M5_R, (St0-daily_Sty)/(S_flood_cap-daily_Sty)*(I99-Q2) + Q2])
        else:
            Rt = M5_R

    # %% Additional rules in case daily initial storage is below dead storage level
    if St0 < S_dead:
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
def predict_irr_series(df_I, df_Sty, S0, irr_modules, irr_DOYs, I_stat, S_info, default_para, 
                       alpha=2, beta=0.5):
    
    pre_R = []
    pre_S = []
    Si = S0 # assign the initial storage of the studied period
    Ri = df_I['netinflow'][0]

    for i, row in df_I.iterrows():
        Ri0 = Ri
        Si0 = Si # the ending storage of previous day as the initial storage of current day 
        pre_S.append(Si0)
        DOYi = row['DOY']
        
        # typical storage level for current DOY
        if type(df_Sty) != np.float:
            if (row['Time'].is_leap_year == True and row['month'] == 2 and row['day_of_month']==29):
                daily_Sty = df_Sty[(df_Sty['month']==2)&(df_Sty['day_of_month']==28)]['typical_S'].values[0]
            else:
                daily_Sty = df_Sty[(df_Sty['month']==row['month'])&(df_Sty['day_of_month']==row['day_of_month'])]['typical_S'].values[0]
        else:
            daily_Sty = df_Sty
            
        # daily operation simulation
        Ri, Si = predict_irr_daily(row['netinflow'], Si0, Ri0, DOYi, daily_Sty, irr_modules, irr_DOYs, I_stat, S_info, default_para)
        pre_R.append(Ri)
            
    return pre_R, pre_S