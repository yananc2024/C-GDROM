##### functions to implement C+GDROM - Flood Control Model
import pandas as pd
import numpy as np
import copy
from sklearn.linear_model import LinearRegression


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def fc_module_calibration(df, df_Sty, f_threshold1, f_threshold2, size_ratio):
    df1 = df.copy()
    
    if type(df_Sty) == np.float:
        df1.loc[:,'typical_S'] = df_Sty
        df1.loc[:,'storage_diff'] = df1.apply(lambda row: row.storage - df_Sty, axis = 1)
    else:
        df1 = df1.merge(df_Sty, left_on=['month', 'day_of_month'], right_on=['month', 'day_of_month'])
        df1.loc[:,'storage_diff'] = df1.apply(lambda row: row.storage - row.typical_S, axis = 1)
    
    if size_ratio <= 0.15:
        M2a_feature = 'netinflow'
        M2a_intercept = True
        M2b_intercept = False
    else:
        M2a_feature = 'storage_diff'
        M2a_intercept = True
        M2b_intercept = True
        
    # ****************************
    # %M1: when I > major flood threshold (i.e., f_threshold1)
    df_M1 = df1[df1['netinflow'] >= f_threshold1]
    if len(df_M1) != 0:
        M1_model = df_M1['outflow'].mean()
    else:
        M1_model = 'default' #no major flood occured during the selected years; using default formulation

        
    # ****************************
    # %M2a: storage difference-driven linear module (for high flow conditions when I >= f_threshold2 while I <= f_threshold1)
    df_M2a = df1[(df1['storage_diff']>=0)&(df1['netinflow']<f_threshold1) & (df1['netinflow']>=f_threshold2)]
    
    if len(df_M2a) != 0:
        x = np.array(df_M2a[M2a_feature]).reshape((-1, 1))
        y = np.array(df_M2a['outflow'])
        M2a_model = LinearRegression(fit_intercept=M2a_intercept).fit(x, y)
        
        if M2a_feature == 'storage_diff' and M2a_model.coef_[0] < 0: # to ensure larger release with larger storage
            M2a_model = LinearRegression(fit_intercept=False).fit(x, y)
        
        M2a_coef =  M2a_model.coef_[0]
        M2a_intercept = M2a_model.intercept_
    
    else:
        M2a_coef = 'default'
        M2a_intercept = ''


    # ****************************
    # %M2b: storage difference-driven linear module (when I < f_threshold2)
    df_M2b = df1[(df1['storage_diff']>=0) & (df1['netinflow'] < f_threshold2)]

    if len(df_M2b) != 0:
        x = np.array(df_M2b['storage_diff']).reshape((-1, 1))
        y = np.array(df_M2b['outflow'])
        M2b_model = LinearRegression(fit_intercept=M2b_intercept).fit(x, y)
        
        if M2b_model.coef_[0] < 0: # to ensure larger release with larger storage
            M2b_model = LinearRegression(fit_intercept=False).fit(x, y)
            
        M2b_coef =  M2b_model.coef_[0]
        M2b_intercept = M2b_model.intercept_
    
    else:
        M2b_coef = 'default'
        M2b_intercept = ''

        
    # ****************************
    # %M3: constant release module
    df_M3 = df1[(df1['netinflow'] < f_threshold1) & (df1['storage'] < df1['typical_S'])]
    if len(df_M3) != 0:
        M3_model= df_M3['outflow'].median()
    else:
        M3_model = 'default'

    
    return M1_model, M2a_coef, M2a_intercept, M2b_coef, M2b_intercept, M3_model



# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def predict_fc_daily(It, St0, Rt0, daily_Sty, fc_modules, I_stat, S_info,
                     default_para, alpha=2, beta=0.5):
    
    # **********************
    # initialization
    M1_model, M2a_model, M2b_model, M3_model = fc_modules
    I99, I80, I50, I30, I10, I_mean = I_stat
    S_cap, S_dead, S_flood_cap, size_ratio =  S_info
    Q1, Q2, Q3, R_flood = default_para

    # **********************
    # predict current day release using C+GDROM Flood Control Model
    # %% Module 1 for major flood operations
    if It >= I99:
        if M1_model=='default' or np.isnan(M1_model)==True:
            Rt = R_flood
        else:
            Rt = min([M1_model, It])

        # further adjusting flood releases considering storage levels 
        if St0 < daily_Sty:
            Rt = Rt - (daily_Sty-St0)       
    
    # %% Module 2a applied when daily initial storage >= daily and I >= I80
    elif It >= I80 and St0 >= daily_Sty:
        if M2a_model[0]=='default' or  np.isnan(M2a_model[0])==True:
            Rt = (St0-daily_Sty)/(S_flood_cap-daily_Sty)*(Q1-Q2) + Q2
        else:
            if size_ratio > 0.15:
                Rt = min([(M2a_model[1] + M2a_model[0]*(St0-daily_Sty)), I99])
            else:
                Rt = min([(M2a_model[1] + M2a_model[0]*It), I99])

    # %% Module 2b applied when daily initial storage >= daily and I < I80
    elif St0 >= daily_Sty:
        if M2b_model[0]=='default' or np.isnan(M2b_model[0])==True:
            Rt = (St0-daily_Sty)/(S_flood_cap-daily_Sty)*(Q1-Q2) + Q2
        else:
            Rt = min([(M2b_model[1] + M2b_model[0]*(St0-daily_Sty)), I99])
    
    # %% Module 3 for normal operations when daily initial storage < daily typical values but >= S_dead
    elif St0 >= S_dead: 
        if M3_model=='default' or np.isnan(M3_model)==True:
            Rt = Q3
        else:
            Rt = M3_model

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
def predict_fc_series(df_I, df_Sty, S0, fc_modules, I_stat, S_info, default_para,
                      alpha=2, beta=0.5):
    
    pre_R = []
    pre_S = []
    Si = S0 # assign the initial storage of the studied period
    Ri = df_I['netinflow'][0]

    for i, row in df_I.iterrows():
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
        Ri, Si = predict_fc_daily(row['netinflow'], Si0, Ri0, daily_Sty, fc_modules, I_stat, S_info, default_para)
        pre_R.append(Ri)
            
    return pre_R, pre_S