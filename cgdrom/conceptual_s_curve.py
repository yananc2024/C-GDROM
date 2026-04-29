import pandas as pd
import numpy as np
import copy
from scipy.interpolate import CubicSpline

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# derive six-parameter conceptual storage regulation curve based on historical daily median storage
def derive_curve_parameters(S_median_series): 
    
    month_days = np.array([31,28,31,30,31,30,31,31,30,31,30,31]) # Days per month for non-leap year
    month_mid_doy = np.cumsum(month_days) - month_days + 15 # Day of year for the 15th of each month (non-leap year)
    daily_doy = np.arange(1, 366) # Daily day-of-year

    if len(S_median_series) == 12:
        # Extend for periodicity
        x_ext = np.concatenate(([month_mid_doy[-1] - 365], month_mid_doy))
        y_ext = np.concatenate(([S_median_series[-1]], S_median_series))
        # Interpolation (from monthly value to daily value)
        cs = CubicSpline(x_ext, y_ext, bc_type="periodic")
        S_median_series = cs(daily_doy)
        
        
    # create a data frame of daily median storage values for each DOY and the corresponding month 
    month_i = []
    for m, ndays in enumerate(month_days, start=1):
        for d in range(1, ndays + 1):
            month_i.append(m)

    df1 = pd.DataFrame({'month':month_i, 'storage': S_median_series})
    
    # initialization
    min_error = float('inf')
    best_a1 = None
    best_a2 = None
    best_a3 = None
    best_a4 = None

    # for all combinations of start and ending months for each stage
    for month_a1 in range(0, 8): 
        for month_a2 in range(month_a1+2, 11):
            for month_a3 in range(month_a2, 13):
                for month_a4 in range(month_a3+2, 20):
                    if month_a4 <= 12:
                        mask1 = (df1['month'] <= month_a1) | (df1['month'] >= month_a4)
                        mask4_p1 = (df1['month'] > month_a3) & (df1['month'] < month_a4)
                        mask4_p2 = []
                    else:
                        month_a4 = month_a4-12
                        if month_a4 > month_a1:
                            continue
                        else:
                            mask1 = (df1['month'] <= month_a1) & (df1['month'] >= month_a4)
                            mask4_p1 = (df1['month'] > month_a3)
                            mask4_p2 = (df1['month'] < month_a4)
                    
                    mask2 = (df1['month'] > month_a1) & (df1['month'] < month_a2)
                    mask3 = (df1['month'] >= month_a2) & (df1['month'] <= month_a3)

                    a1_data = df1.loc[mask1, 'storage']
                    a2_data = df1.loc[mask2, 'storage']
                    a3_data = df1.loc[mask3, 'storage']
                    a4_data_p1 = df1.loc[mask4_p1, 'storage']
                    a4_data_p1.reset_index(drop=True, inplace=True)
                    a4_data_p2 = df1.loc[mask4_p2, 'storage']
                    a4_data_p2.reset_index(drop=True, inplace=True)
                    a4_data = pd.concat([a4_data_p1, a4_data_p2])
                    
                    a1 = a1_data.mean()
                    a3 = a3_data.mean()
                    a2 = [a1+ i*(a3-a1)/len(a2_data) for i in range(1,len(a2_data)+1)]
                    a4 = [a3+ i*(a1-a3)/len(a4_data) for i in range(1,len(a4_data)+1)]   
                    

                    # compute the loss
                    error = ((a1_data - a1) ** 2).sum() + ((a2_data - a2) ** 2).sum()+((a3_data - a3) ** 2).sum() + ((a4_data - a4) ** 2).sum()
                    #print([month_a1, month_a2, month_a3, month_a4, a1, a3, error])

                    if error < min_error:
                        min_error = error
                        best_a1_month = month_a1
                        best_a2_month = month_a2
                        best_a3_month = month_a3
                        best_a4_month = month_a4
                        best_a1 = a1
                        best_a3 = a3

    
    # **********************
    print(f"A1：{best_a1_month:.0f}")
    print(f"A2：{best_a2_month:.0f}")
    print(f"A3：{best_a3_month:.0f}")
    print(f"A4：{best_a4_month:.0f}")
    
    print(f"S_A4-A1：{best_a1:.4f}")
    print(f"S_A2-A3：{best_a3:.4f}")
    
    return(best_a1_month, best_a2_month, best_a3_month, best_a4_month, best_a1, best_a3)



# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# a function used within the function 'doy_typical_storage' to determine typical storage level
def doy_Sty_interpolate(row, month1, month2, month3, month4, a1, a2, month1_end_DOY, month3_end_DOY, trans_month_length1, trans_month_length2): 
    if month4 > month1:  # month4 > month1
        if row['month']<= month1 or row['month']>=month4:
            return a1
        if row['month']>=month2 and row['month']<=month3:
            return a2
        if row['month']>month1 and row['month']<month2:
            return (a1+(a2-a1)* (row['DOY']-month1_end_DOY)/trans_month_length1)
        if row['month']>month3 and row['month']<month4:
            return (a2+(a1-a2)* (row['DOY']-month3_end_DOY)/trans_month_length2)
    else: # month4 <= month1
        if row['month']<= month1 and row['month']>=month4:
            return a1
        if row['month']>=month2 and row['month']<=month3:
            return a2
        if row['month']>month1 and row['month']<month2:
            return (a1+(a2-a1)* (row['DOY']-month1_end_DOY)/trans_month_length1)
        if row['month']>month3 or row['month']<month4:
            if row['DOY'] >= month3_end_DOY:
                return (a2+(a1-a2)* (row['DOY']-month3_end_DOY)/trans_month_length2)
            else:
                return (a2+(a1-a2)* (row['DOY']+365-month3_end_DOY)/trans_month_length2)


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def doy_typical_storage(month1, month2, month3, month4, a1, a2):
    
    dict_month_days = {
        1:31, 2:28, 3:31, 4:30, 5:31, 6:30,
        7:31, 8:31, 9:30, 10:31, 11:30, 12:31
    }
    
    dict_month_doy = {
        1:1, 2:32, 3:60, 4:91, 5:121, 6:152,
        7:182, 8:213, 9:244, 10:274, 11:305, 12:335, 13:366
    }
    
    # create an empty data frame with day of month and day of year
    days_per_month = [31,28,31,30,31,30,31,31,30,31,30,31] # Days per month for non-leap year
    data = []
    day_of_year = 1
    for m, ndays in enumerate(days_per_month, start=1):
        for d in range(1, ndays + 1):
            data.append([m, d, day_of_year])
            day_of_year += 1
    df_Sty = pd.DataFrame(data, columns=['month', 'day_of_month', 'DOY'])

    trans_month_length1 = sum([dict_month_days[month0] for month0 in range(month1+1, month2)])
    if month4 > month1:
        trans_month_length2 = sum([dict_month_days[month0] for month0 in range(month3+1, month4)])
    else:
        month_trans2 = [j for j in range(1, month4)]+[j for j in range(month3+1, 13)]
        trans_month_length2 = sum([dict_month_days[month0] for month0 in month_trans2])
    month3_end_DOY = dict_month_doy[month3+1]-1
    month1_end_DOY = dict_month_doy[month1+1]-1
        
    df_Sty["typical_S"] = df_Sty.apply(doy_Sty_interpolate, axis=1, args=(month1, month2, month3, month4, a1, a2, month1_end_DOY, month3_end_DOY, trans_month_length1, trans_month_length2))

    
    return df_Sty