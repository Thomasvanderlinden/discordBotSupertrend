from discord_webhook import DiscordWebhook
import datetime
import ccxt
import pandas as pd
import numpy as np
import time
from dotenv import load_dotenv
import os



load_dotenv()

pd.set_option('display.max_columns', 20)
print("\nRun Started.......... : ", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      )

supertrend_period = 10
supertrend_multiplier = 2
candlesize = '5m'
fetch_time = 10  # sec

exchange = ccxt.binance(
    {"api_key": os.getenv('key'),
     "secret": os.getenv('skey')})
# list all tickers you want to trade
tickerlist = ["BTC/USDT"]


def verstuurBericht(bericht):
    webhook = DiscordWebhook(
        url='https://discord.com/api/webhooks/1039610545109749780/E7oUziqXZqqkjuI6_S-2GGL9N5QqxmYN7zoDZaJQ5i0aEVm7vw3FNet90qkxBaNRDMsU',
        content='new ' + bericht + ' signal at: ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    webhook.execute()


def verstuurBerichtTest(trend):
    webhook = DiscordWebhook(
        url='https://discord.com/api/webhooks/1041771982225678406/KcyCpwg_AZJW7uggVxG15z5nbN7vZ9NAclDH_PQMPHs3tpTmSIquxaXJkLXL25g3CkA7',
        content=" " + trend + " " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    webhook.execute()


# Source for tech indicator : https://github.com/arkochhar/Technical-Indicators/blob/master/indicator/indicators.py
def EMA(df, base, target, period, alpha=False):
    con = pd.concat([df[:period][base].rolling(window=period).mean(), df[period:][base]])

    if (alpha == True):
        # (1 - alpha) * previous_val + alpha * current_val where alpha = 1 / period
        df[target] = con.ewm(alpha=1 / period, adjust=False).mean()
    else:
        # ((current_val - previous_val) * coeff) + previous_val where coeff = 2 / (period + 1)
        df[target] = con.ewm(span=period, adjust=False).mean()

    df[target].fillna(0, inplace=True)
    return df


def ATR(df, period, ohlc=['open', 'high', 'low', 'close']):
    atr = 'ATR_' + str(period)

    # Compute true range only if it is not computed and stored earlier in the df
    if not 'TR' in df.columns:
        df['h-l'] = df[ohlc[1]] - df[ohlc[2]]
        df['h-yc'] = abs(df[ohlc[1]] - df[ohlc[3]].shift())
        df['l-yc'] = abs(df[ohlc[2]] - df[ohlc[3]].shift())

        df['TR'] = df[['h-l', 'h-yc', 'l-yc']].max(axis=1)

        df.drop(['h-l', 'h-yc', 'l-yc'], inplace=True, axis=1)

    # Compute EMA of true range using ATR formula after ignoring first row
    EMA(df, 'TR', atr, period, alpha=True)

    return df


def SuperTrend(df, period=supertrend_period, multiplier=supertrend_multiplier, ohlc=['open', 'high', 'low', 'close']):
    ATR(df, period, ohlc=ohlc)
    atr = 'ATR_' + str(period)
    st = 'ST'
    stx = 'STX'

    # Compute basic upper and lower bands
    df['basic_ub'] = (df[ohlc[1]] + df[ohlc[2]]) / 2 + multiplier * df[atr]
    df['basic_lb'] = (df[ohlc[1]] + df[ohlc[2]]) / 2 - multiplier * df[atr]

    # Compute final upper and lower bands
    df['final_ub'] = 0.00
    df['final_lb'] = 0.00
    for i in range(period, len(df)):
        df['final_ub'].iat[i] = df['basic_ub'].iat[i] if df['basic_ub'].iat[i] < df['final_ub'].iat[i - 1] or \
                                                         df[ohlc[3]].iat[i - 1] > df['final_ub'].iat[i - 1] else \
            df['final_ub'].iat[i - 1]
        df['final_lb'].iat[i] = df['basic_lb'].iat[i] if df['basic_lb'].iat[i] > df['final_lb'].iat[i - 1] or \
                                                         df[ohlc[3]].iat[i - 1] < df['final_lb'].iat[i - 1] else \
            df['final_lb'].iat[i - 1]

    # Set the Supertrend value
    df[st] = 0.00
    for i in range(period, len(df)):
        df[st].iat[i] = df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df[ohlc[3]].iat[
            i] <= df['final_ub'].iat[i] else \
            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df[ohlc[3]].iat[i] > \
                                     df['final_ub'].iat[i] else \
                df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df[ohlc[3]].iat[i] >= \
                                         df['final_lb'].iat[i] else \
                    df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df[ohlc[3]].iat[i] < \
                                             df['final_lb'].iat[i] else 0.00

        # Mark the trend direction up/down
    df[stx] = np.where((df[st] > 0.00), np.where((df[ohlc[3]] < df[st]), 'down', 'up'), np.NaN)

    # Remove basic and final bands from the columns
    df.drop(['basic_ub', 'basic_lb', 'final_ub', 'final_lb'], inplace=True, axis=1)

    df.fillna(0, inplace=True)
    return df


def gethistoricaldata(token):
    df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    try:
        data = exchange.fetch_ohlcv(token, timeframe=candlesize, limit=50)

        df = pd.DataFrame(data[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # print(df)
        if not df.empty:
            df = df[['open', 'high', 'low', 'close', 'volume']]
            df = SuperTrend(df)
    except Exception as e:
        print("         error in gethistoricaldata", token, e)
    return df


orderslist = []

al_verstuurd = 0





def run_trategy():
    for pair in tickerlist:
        try:
            histdata = gethistoricaldata(pair)
            # print(histdata)
            super_trend = histdata.STX.values
            global al_verstuurd


            if super_trend[-1] == 'up' and super_trend[-3] == 'down' and super_trend[-4] == 'down' and super_trend[
                -5] == 'down' and super_trend[-6] == 'down':
                if al_verstuurd == 0 or al_versuurd == 1:
                    verstuurBericht(' buy')
                    al_verstuurd = 2

            if super_trend[-1] == 'down' and super_trend[-3] == 'up' and super_trend[-4] == 'up' and super_trend[
                -5] == 'up' and super_trend[-6] == 'up':
                if al_verstuurd == 0 or al_verstuurd == 2:
                    verstuurBericht(' sell')
                    al_verstuurd = 1

        except Exception as e:
            print(e)


def run():
    global runcount

    schedule_interval = 30  # run at every 3 min # deze doet het volgensmij niet
    # runcount = 0
    while True:
        run_trategy()
        runcount = runcount + 1
        time.sleep(fetch_time)
    # hier kan je nog if runcount = deelbaar door bepaald getal, stuur bericht evt


runcount = 0
run()
