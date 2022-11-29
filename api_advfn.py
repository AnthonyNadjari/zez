from pickle import FALSE
from bs4 import BeautifulSoup as bs
import pandas as pd
from flask import Flask
from flask_restful import Resource, Api
from flask_ngrok import run_with_ngrok
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import time
import numpy as np
import os
from datetime import datetime
from pandas.tseries.offsets import BDay

opts = webdriver.FirefoxOptions()
opts.headless = True


class Prices(Resource):
    def get(self, ticker, start_date, end_date):
        global driver
        global browser_launched

        # initialize variables
        browser_launched = False
        prices_histo = []
        ticker_file = ''
        mat_file = ''
        directory = 'HistoPrices'

        # retrieve prices for a period from browser
        def get_prices(dfrom, dto):
            global driver
            # launch the selenium brower we will work on
            if not browser_launched:
                launch_browser()

            # input dates into browser with selenium
            driver.find_element(By.CSS_SELECTOR, '#Date1').clear()
            driver.find_element(By.CSS_SELECTOR, '#Date1').send_keys(dfrom)
            driver.find_element(By.CSS_SELECTOR, '#Date2').clear()
            driver.find_element(By.CSS_SELECTOR, '#Date2').send_keys(dto)
            driver.find_element(By.CSS_SELECTOR, '#submit-btn').click()

            dates = []
            prices = []
            i = 1
            # get prices with beautiful soup
            while True:
                html = driver.page_source
                # soup = bs(html, 'lxml')
                soup = bs(html, 'lxml')

                elements = soup.find_all('tr', {"class": "result"})
                for element in elements:
                    date = element.find_all('td')[0].text
                    price = element.find_all('td')[1].text
                    dates.append(date)
                    prices.append(price)
                try:
                    # next page
                    driver.find_element(By.CSS_SELECTOR, '#next').click()
                except NoSuchElementException:
                    break
                i += 1

            # create and return dataframe with prices for specific period
            df = pd.DataFrame.from_dict({'Date': dates, 'Price': prices})
            return df

        # if needed, we launch the Firefox driver
        def launch_browser():
            global browser_launched
            global driver
            driver = webdriver.Firefox(executable_path=r'./driver/geckodriver')
            url = "https://www.advfn.com/stock-market/"
            driver.get(url)
            wait = WebDriverWait(driver, 10)
            # Enter ticker in search bar
            driver.find_element(By.CSS_SELECTOR, '#headerQuickQuoteSearch').send_keys(ticker)
            time.sleep(1)
            # focus on search bar to have suggestions
            driver.find_element(By.CSS_SELECTOR, '#headerQuickQuoteSearch').click()
            # wait until the first element in the list is clickable
            el = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '#headerQuickQuoteSearch-menu > table > tbody > tr:nth-child(1)')))
            # the exchange is plugged into the url to retrieve quotes
            # (we use the suggestion box because we assume user might not know the exchange)
            info = driver.find_element(By.CSS_SELECTOR, 'tr.autosuggest-result').text
            exchange_split = info.split(" ")
            exchange = exchange_split[len(exchange_split) - 1]
            if exchange == "EU":
                exchange = "EURONEXT"
            url = "https://www.advfn.com/stock-market/" + exchange + "/" + ticker + "/historical/more-historical-data"
            driver.get(url)
            browser_launched = True

        # because selenium webscraping in our case takes a significant amount of time
        # we decided that the user will store prices in a txt file that he can quickly retrieve next time
        for filename in os.listdir(directory):
            # get filenames in directory (ticker and time horizon)
            filename = filename[:len(filename) - 4]
            file_split = filename.split('_')
            ticker_file = file_split[0]
            # if we get a match then we extract prices
            if ticker == ticker_file:
                text_prices = np.loadtxt('HistoPrices/' + filename + '.txt', delimiter=',', dtype="str")
                # have to pass by a dataframe to have prices in float and not string...
                prices_histo = pd.DataFrame.from_dict({'Date': text_prices[:, 0], 'Price': text_prices[:, 1]})
                prices_histo.head()
                prices_histo['Date'] = pd.to_datetime(prices_histo['Date'])
                mat_file = prices_histo.iloc[len(prices_histo) - 1, 0]
                # we will delete the file because a more complete version will be stored
                os.remove("HistoPrices/" + filename + ".txt")
                break

        start_date_num = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_num = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Date formatting
        if not (bool(len(pd.bdate_range(start_date_num, start_date)))):
            start_date = datetime.strftime(start_date_num + BDay(1), '%Y-%m-%d')
            start_date_num = (start_date_num + BDay(1)).date()
        if not (bool(len(pd.bdate_range(end_date_num, start_date)))):
            end_date = datetime.strftime(end_date_num - BDay(1), '%Y-%m-%d')
            end_date_num = (end_date_num - BDay(1)).date()

        # start date in format mm/dd/yy
        start_date_split = start_date.split("-")
        start_date_format = start_date_split[1] + "/" + start_date_split[2] + "/" + start_date_split[0][2:]
        # end date in format mm/dd/yy
        end_date_split = end_date.split("-")
        end_date_format = end_date_split[1] + "/" + end_date_split[2] + "/" + end_date_split[0][2:]

        if len(prices_histo) < 2:
            # if there is no prior txt file
            df_to_save = df_to_use = get_prices(start_date_format, end_date_format)
        else:
            # 1) check if more recent prices need to be added to the txt prices
            print(prices_histo.iloc[0, 0].date())
            if prices_histo.iloc[0, 0].date() < end_date_num:

                # if the last time we stored AAPL prices was a month ago, then we will add the prices from this month to the list
                latest_prices = get_prices(datetime.strftime(prices_histo.iloc[0, 0], '%m/%d/%y'), end_date_format)
                print(latest_prices)

                # we join the new prices with the txt prices
                frames = [latest_prices, prices_histo]
                df_to_save = df_to_use = pd.concat(frames)
            else:
                # if the txt prices are already up to date
                df_to_save = df_to_use = prices_histo

            df_to_save['Date'] = pd.to_datetime(df_to_save['Date'])

            # 2) check if older prices need to be added to the txt prices (ie if we stored 5 years of prices and need 6)
            if mat_file.date() > start_date_num:
                older_prices = get_prices(start_date_format, datetime.strftime(mat_file.date(), '%m/%d/%y'))
                frames = [df_to_save, older_prices]
                df_to_save = df_to_use = pd.concat(frames)
            else:
                # if we need 2Y of prices but have 5Y stored, we will extract only 2Y
                i = len(df_to_save) - 1
                start_idx = len(df_to_use) - 1
                end_idx = 0
                while i > 0:
                    # we search from bottom so it will take latest date the 2
                    df_date = datetime.strftime(df_to_save.iloc[i, 0], '%Y-%m-%d')
                    if df_date == end_date:
                        end_idx = i + 1
                        break
                    elif df_date == start_date:
                        start_idx = i + 1
                    i -= 1
                df_to_use = df_to_save.iloc[end_idx:start_idx, :]

        # Drop duplicates (one date will be overlapping)
        df_to_use['Date'] = pd.to_datetime(df_to_use['Date'])
        df_to_use = df_to_use.drop_duplicates()
        df_to_save['Date'] = pd.to_datetime(df_to_save['Date'])
        df_to_save = df_to_save.drop_duplicates()

        # save prices to txt file to be used in the future
        prices = np.array(df_to_save)
        np.savetxt('HistoPrices/' + ticker + '_' + str(len(df_to_save)) + '.txt', prices, delimiter=',', fmt="%s")

        # convert to json
        hist_prices = [df_to_use.iloc[i].to_json() for i in range(len(df_to_use))]

        # close browser
        if browser_launched:
            driver.close()
            driver.quit()

        return hist_prices


app2 = Flask("My App")
api = Api(app2)
api.add_resource(Prices, '/prices/<string:ticker>/<string:start_date>/<string:end_date>')


@app2.route("/")
def home():
    return "<h1>Get Prices</h1>"


def main():
    run_with_ngrok(app2)
    app2.run()
    os._exit(0)


if __name__ == '__main__':
    main()