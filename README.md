# NeonTrade Real v1.1

Real MT5-connected dashboard foundation. **Live order execution remains disabled unless `LIVE_TRADING=true` is explicitly set.**

## Broker connection
1. Run MetaTrader 5 on the same machine as the backend (or use a terminal path accepted by your environment).
2. Start the backend.
3. Open the frontend and choose **CONNECT BROKER**.
4. Enter MT5 login, password, and exact broker server name.
5. NeonTrade verifies the account and then reads live equity/market data.

Credentials supplied through the UI are kept only in backend process memory and are not written to a database by this version. Do not send broker credentials through chat.

## Backend
```bash
cd neontrade_real_v1/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Frontend
Open `frontend/index.html` after the backend is running. For production, serve it from your secured domain and put the API behind HTTPS/authentication.

## Safety
`LIVE_TRADING=false` is the default. The `/api/order` endpoint refuses orders while live trading is disabled. Test the strategy on demo first.


## Live execution
The API includes a manual `/api/order` endpoint. It is disabled unless `LIVE_TRADING=true` is set on the server, and every order request must include `confirm_live=true`. Use a demo account first. The web UI includes a manual order ticket; it does not autonomously place trades.
