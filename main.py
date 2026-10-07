import os
from datetime import datetime, timezone
from typing import Optional
import MetaTrader5 as mt5
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app=FastAPI(title='NeonTrade Real Trading API', version='1.1')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

LIVE_TRADING=os.getenv('LIVE_TRADING','false').lower()=='true'
# Optional environment defaults. UI connections are kept in process memory only.
MT5_LOGIN=os.getenv('MT5_LOGIN')
MT5_PASSWORD=os.getenv('MT5_PASSWORD')
MT5_SERVER=os.getenv('MT5_SERVER')
connection={'login': int(MT5_LOGIN) if MT5_LOGIN else None, 'password': MT5_PASSWORD, 'server': MT5_SERVER}

class BrokerConnectRequest(BaseModel):
    login: int
    password: str
    server: str
    path: Optional[str]=None

class OrderRequest(BaseModel):
    symbol:str
    side:str
    volume:float
    sl:Optional[float]=None
    tp:Optional[float]=None
    confirm_live: bool = False


def connect():
    kwargs={}
    if connection['login'] and connection['password'] and connection['server']:
        kwargs={'login':int(connection['login']),'password':connection['password'],'server':connection['server']}
    if not mt5.initialize(path=connection.get('path')) if connection.get('path') else not mt5.initialize():
        raise HTTPException(503, f'MT5 connection failed: {mt5.last_error()}')
    if kwargs and not mt5.login(**kwargs):
        raise HTTPException(401, f'MT5 login failed: {mt5.last_error()}')


def rsi(closes, period=14):
    if len(closes)<=period: return None
    gains=[]; losses=[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[-period:])/period; al=sum(losses[-period:])/period
    if al==0: return 100.0
    return 100-(100/(1+ag/al))

def ema(values, period):
    k=2/(period+1); e=values[0]
    for v in values[1:]: e=v*k+e*(1-k)
    return e

def analyze(symbol, timeframe=mt5.TIMEFRAME_M15, bars=250):
    connect()
    if not mt5.symbol_select(symbol, True): raise HTTPException(404, f'Symbol unavailable: {symbol}')
    rates=mt5.copy_rates_from_pos(symbol,timeframe,0,bars)
    if rates is None or len(rates)<60: raise HTTPException(502, f'Not enough market data for {symbol}')
    closes=[float(x['close']) for x in rates]
    e20=ema(closes[-100:],20); e50=ema(closes[-100:],50); rv=rsi(closes)
    macd=ema(closes[-100:],12)-ema(closes[-100:],26)
    signal=ema([ema(closes[:i+1][-100:],12)-ema(closes[:i+1][-100:],26) for i in range(25,len(closes))][-20:],9)
    score=50; reasons=[]
    if e20>e50: score+=15; reasons.append('EMA20 above EMA50')
    else: score-=15; reasons.append('EMA20 below EMA50')
    if rv is not None:
        if 50<rv<70: score+=12; reasons.append('RSI bullish zone')
        elif rv>75: score-=8; reasons.append('RSI overbought')
        elif rv<30: score+=8; reasons.append('RSI oversold')
        else: score-=5
    if macd>signal: score+=13; reasons.append('MACD bullish')
    else: score-=13; reasons.append('MACD bearish')
    score=max(0,min(100,round(score)))
    side='BUY' if score>=65 else 'SELL' if score<=35 else 'NEUTRAL'
    tick=mt5.symbol_info_tick(symbol); price=float(tick.ask if side=='BUY' else tick.bid)
    info=mt5.symbol_info(symbol)
    atr=sum(float(x['high']-x['low']) for x in rates[-14:])/14
    if side=='BUY': sl=price-1.5*atr; tp=price+3*atr
    elif side=='SELL': sl=price+1.5*atr; tp=price-3*atr
    else: sl=tp=None
    return {'symbol':symbol,'side':side,'score':score,'price':price,'rsi':round(rv,2) if rv else None,'ema20':e20,'ema50':e50,'macd':macd,'reasons':reasons,'sl':sl,'tp':tp,'timeframe':'M15','timestamp':datetime.now(timezone.utc).isoformat()}

@app.get('/api/health')
def health(): return {'ok':True,'live_trading':LIVE_TRADING,'connected':bool(connection['login'])}

@app.post('/api/broker/connect')
def broker_connect(req:BrokerConnectRequest):
    global connection
    old=connection.copy()
    connection={'login':req.login,'password':req.password,'server':req.server,'path':req.path}
    try:
        connect(); a=mt5.account_info()
        if a is None: raise HTTPException(502,'MT5 connected but no account information was returned')
        return {'connected':True,'login':a.login,'server':a.server,'balance':a.balance,'equity':a.equity,'currency':a.currency,'trade_allowed':a.trade_allowed,'live_trading':LIVE_TRADING}
    except Exception:
        connection=old
        raise

@app.post('/api/broker/disconnect')
def broker_disconnect():
    global connection
    mt5.shutdown(); connection={'login':None,'password':None,'server':None,'path':None}
    return {'connected':False}

@app.get('/api/broker/status')
def broker_status():
    try:
        a=mt5.account_info()
        return {'connected':a is not None,'login':a.login if a else None,'server':a.server if a else None,'balance':a.balance if a else None,'equity':a.equity if a else None,'currency':a.currency if a else None,'trade_allowed':a.trade_allowed if a else False,'live_trading':LIVE_TRADING}
    except Exception:
        return {'connected':False,'live_trading':LIVE_TRADING}

@app.get('/api/account')
def account():
    connect(); a=mt5.account_info()
    if a is None: raise HTTPException(502,'No MT5 account')
    return {'login':a.login,'server':a.server,'balance':a.balance,'equity':a.equity,'profit':a.profit,'margin':a.margin,'currency':a.currency,'trade_allowed':a.trade_allowed}

@app.get('/api/opportunities')
def opportunities(symbols:str='BTCUSD,XAUUSD,EURUSD,GBPUSD'):
    out=[]
    for s in [x.strip() for x in symbols.split(',') if x.strip()]:
        try: out.append(analyze(s))
        except HTTPException as e: out.append({'symbol':s,'error':e.detail})
    return out

@app.get('/api/positions')
def positions():
    connect(); p=mt5.positions_get()
    return [] if p is None else [{'ticket':x.ticket,'symbol':x.symbol,'type':x.type,'volume':x.volume,'price_open':x.price_open,'price_current':x.price_current,'profit':x.profit,'sl':x.sl,'tp':x.tp} for x in p]

@app.post('/api/order')
def order(req:OrderRequest):
    if not LIVE_TRADING: raise HTTPException(403,'Live trading is disabled. Enable LIVE_TRADING=true on the server after demo testing.')
    if not req.confirm_live: raise HTTPException(400,'Explicit live-order confirmation is required.')
    if req.volume <= 0: raise HTTPException(400,'volume must be greater than zero')
    connect(); symbol=req.symbol; side=req.side.upper()
    if side not in ('BUY','SELL'): raise HTTPException(400,'side must be BUY or SELL')
    info=mt5.symbol_info(symbol); tick=mt5.symbol_info_tick(symbol)
    if not info or not tick: raise HTTPException(404,'Symbol unavailable')
    price=tick.ask if side=='BUY' else tick.bid
    request={'action':mt5.TRADE_ACTION_DEAL,'symbol':symbol,'volume':req.volume,'type':mt5.ORDER_TYPE_BUY if side=='BUY' else mt5.ORDER_TYPE_SELL,'price':price,'sl':req.sl or 0.0,'tp':req.tp or 0.0,'deviation':20,'magic':26061007,'comment':'NeonTrade'}
    result=mt5.order_send(request)
    if result is None: raise HTTPException(502,f'order_send failed: {mt5.last_error()}')
    return {'retcode':result.retcode,'order':result.order,'deal':result.deal,'comment':result.comment}
