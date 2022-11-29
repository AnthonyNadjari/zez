import requests
import pandas as pd
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta


def get_price_table(tickers, start_date, end_date, maturity):
    BASE = "http://127.0.0.1:5000/"
    price_table = None
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()+ relativedelta(months=maturity)
    if datetime.today().date() < end_date:
        end_date = datetime.today().date()
        end_date = datetime.strftime(end_date, "%Y-%m-%d")
    for idx,ticker in enumerate(tickers):
        response = requests.get(BASE+"prices/" + ticker + "/" + start_date + "/" + end_date)
        dict = response.json()

        df = pd.DataFrame(columns=['Date','Price'])
        for i in range(0, len(dict)):
            ad = json.loads(dict[i])
            df.loc[i] = [ad['Date'], ad['Price']]
        #Convert date format

        df['Date'] = pd.to_datetime(df['Date'],unit='ms')

        #convert string to float for prices
        df.iloc[:,1] = df.iloc[:,1].astype(float)
        # set the date column as index
        df.set_index("Date", inplace=True, drop=True)
        # delete duplicate prices
        df = df.loc[~df.index.duplicated(keep='first')]
        # renaming column by ticker
        df = df.rename({'Price': ticker}, axis=1)
        if idx == 0:
            price_table = df
        else:
            price_table = pd.concat([price_table, df], axis=1, join="inner")
        response.close()

    return price_table


tickers = ['AAPL', 'MSFT', 'TSLA', 'AMZN', 'NFLX','GOOGL','GOOG','UNH','NVDA', 'JPM','PFE','NKE','GS','AMD','MS','SBUX','GM','AC','BNP','EN','ACA','BN','ENGI','OR','MC','GLE','SAF','ORA', 'BMW', 'SIE']

#print(get_price_table(['ORA'], '2019-11-01', '2022-11-29', 6))
