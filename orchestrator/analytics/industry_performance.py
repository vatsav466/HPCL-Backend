import pandas as pd
Industry_performance_23_24 = "/tmp/industry_data_23-24.csv"
Industry_performance_24_25 = "/tmp/industry_data_24-25.csv"
Months = ['APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JAN', 'FEB', 'MAR']
Company_Mapping = {"OIL INDIA LIMITED": "OIL", "RBML": "RIL", "RSIL": "RIL", "SIMPL": "SHELL",
                   "SEIPL": "SHELL", "SMAFSL": "SMA"}


def filter_data(actual=True, history=True):
    """
    To Get dataframe from actual and history
    :param actual:
    :param history:
    :return:
    """
    df_a = pd.DataFrame()
    df_h = pd.DataFrame()
    if actual:
        df_a = pd.read_csv(Industry_performance_24_25)
        df_a = df_a[df_a['CATEGORY'] != 'O']
        df_a['FIN_YEAR'] = "2024-2025"
    if history:
        df_h = pd.read_csv(Industry_performance_23_24)
        df_h = df_h[df_h['CATEGORY'] != 'O']
        df_h['FIN_YEAR'] = "2023-2024"
    print(len(df_a))
    print(len(df_h))
    df = pd.concat([df_a, df_h], ignore_index=True, sort=False)
    df['COMNAME'] = df['COMNAME'].apply(lambda x: Company_Mapping.get(x, x))
    columns = list(set(list(df.columns)) - set(Months))
    print(len(df))
    df = df.melt(id_vars=columns, value_vars=Months, var_name='MONTH', value_name='VALUE')
    print(len(df))
    df.fillna('', inplace=True)
    df['COMP_TYPE'] = df['PSU/PVT']
    return df


def get_group_by_keys(by_month=False, by_product=False, by_year=True, by_company=True, comp_type=False):
    group_keys = []
    if by_year:
        group_keys.append('FIN_YEAR')
    if by_product:
        group_keys.append('PRODNAME')
    if by_month:
        group_keys.append('MONTH')
    if by_company:
        group_keys.append('COMNAME')
    if comp_type:
        group_keys.append('COMP_TYPE')
    return group_keys


def filter_data_by_month(df, start_month=None, end_month=None):
    # Todo:- write filter
    return df


def get_industry_share(actual=True, history=True, start_month=None, end_month=None, by_month=False, by_product=False,
                       comp_type=False):
    df = filter_data_by_month(filter_data(actual, history), start_month, end_month)
    # industry_share = df.groupby(get_group_by_keys(by_month, by_product,
    #                                               comp_type=comp_type))['VALUE'].sum().reset_index()
    # Todo:- Need to calculate by input values
    unique_companies = df['COMNAME'].unique().tolist()
    unique_years = df['FIN_YEAR'].unique().tolist()
    overall_share = df.groupby(['FIN_YEAR'])['VALUE'].sum().reset_index()
    overall_share['VALUE'] = overall_share['VALUE'].apply(lambda x: round(x/1000, 2))
    overall_share = {rec['FIN_YEAR']: {"share": rec['VALUE'], "avg_share": rec["VALUE"]/len(unique_years)}
                     for rec in overall_share.to_dict(orient='records')}
    company_share = []
    for year in unique_years:
        for company in unique_companies:
            share = round((df[(df['COMNAME'] == company) & (df['FIN_YEAR'] == year)]['VALUE'].sum())/1000, 2)
            share_per = 100 * (share / overall_share[year]['share'])
            company_share.append({"COMNAME": company, "FIN_YEAR": year, "CompanySize": share,
                                  "OverAllMarketSize": overall_share[year]['share'],
                                  "OverAllMarketSizeAvg": overall_share[year]['avg_share'],
                                  "MarketSharePer": round(share_per, 2)})
    return company_share


def get_performance_metrics(actual=True, history=True, start_month=None, end_month=None, sbu=None):
    df = filter_data_by_month(filter_data(actual, history), start_month, end_month)
    if sbu:
        if not isinstance(sbu, list):
            sbu = [sbu]
        df = df[df['SBU'] in sbu]
    company_wise = df.groupby(['FIN_YEAR', 'COMNAME', 'COMP_TYPE'])['VALUE'].sum().reset_index()
    company_wise = company_wise.sort_values(by=["COMNAME", "FIN_YEAR"])
    company_wise['VALUE_DIFF'] = company_wise.groupby('COMNAME')['VALUE'].diff()

    # Calculate percentage growth/dip
    company_wise['PERCENT_DIFF'] = (company_wise['VALUE_DIFF'] / company_wise['VALUE'].shift(1)) * 100


    
    
    



