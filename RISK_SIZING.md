# Risk-based position sizing

The application can now calculate a suggested lot size before an order is submitted.

Formula:

`risk money = equity × risk %`

`loss per lot = |entry − stop| / tick size × tick value`

`lots = risk money / loss per lot`

The result is then constrained to the broker's minimum, maximum and volume-step.

**Safety:** this calculation is advisory. The server should re-read the live MT5 symbol specification and account equity immediately before submitting any order, and reject an order if the requested risk exceeds configured limits.

Recommended defaults:
- Demo trading first
- Maximum risk per trade: 1%
- Maximum daily loss: 3%
- Maximum account drawdown: 10%
- Require an SL for every automated/manual order
- Require explicit confirmation before live execution
