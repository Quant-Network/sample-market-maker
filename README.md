# Quant-trading.network BitMEX Market Maker

This is a fully working sample market making bot for use with [BitMEX](https://www.bitmex.com).

It is free to use and modify for your own development.

**Test on [Testnet](https://testnet.bitmex.com) first!** Testnet trading is completely free and is identical to the live market.

## Getting Started

1. Create a [Quant-trading.network Account](https://www.quant-trading.network/) and checkout an algorihtm subscription.
2. Create a [Testnet BitMEX Account](https://testnet.bitmex.com) and [deposit some TBTC](https://testnet.bitmex.com/app/deposit).
3. Install: `pip install quant-trading-bitmex-market-maker`. It is strongly recommeded to use a virtualenv.
4. Create a marketmaker project: run `marketmaker setup`
    * This will create `settings.py` and `market_maker/` in the working directory.
    * Modify `settings.py` to configure the parameters.
5. Edit settings.py to add your [BitMEX API Key and Secret](https://testnet.bitmex.com/app/apiKeys) and your [Quant-trading.network API Key](https://www.quant-trading.network/app/account#api-key), chose the quant-trading algorigthm to use and change bot parameters to fit your risk profile.
    * Note that user/password authentication is not supported.
6. Run it: `marketmaker`
7. Satisfied with your bot's performance? Create a [live API Key](https://www.bitmex.com/app/apiKeys) for your BitMEX account, [`clear the bot internal state`](#clearing-the-bot-internal-state) and then set the `BASE_URL` and start trading!

## Configure your bot (`settings.py`)

A brief explanation of parameters that you will have to configure before using this bot. You can find these parameters in the settings file `settings.py`.

* `BASE_URL` - The URL of the BitMEX exchange api (either the testnet one or the live market).
* `BITMEX_API_KEY` - The BitMEX API key associated with your account (make sure that this key will have the right permissions to place trading orders).
* `BITMEX_API_SECRET` - The BitMEX API key secret associated with your account.
* `QUANT_API_KEY` - The quant-trading.network API key associated with your account.
* `QUANT_ALGO` - The quant-trading.network algorithm you want to use (make sure that you have an active subscription for the chosen algorithm).
* `TRADING_BALANCE_SIZE` - The maximum trading position size in terms of percentage of your BitMEX account margin balance. The bigger the trading position the bigger will the rewards be, but also the risk of getting your BitMEX account liquidated. Therefore we have capped this parameter with reasonable limits for safety. This setting has the following limits `Min=10% & Max=100%`.

## Warning

Please make sure to not use the associated BitMEX account other than by this bot. When you start trading with this bot make sure that you do not have any open position on BitMEX, otherwise, this may lead to unpredictable consequences including your BitMEX account liquidation!!!

## Clearing the bot internal state

This is an action that you will have to take every time when you need to change some of the bot parameters as well as one of the [`troubleshooting measure`](#troubleshooting). When you execute this bot it will create two important files `open_longs.py` & `open_shorts.py` where it will save its internal state periodically so that it can recover its state after a restart. Therefore if you have to change certain bot parameters such as `BASE_URL`, `QUANT_ALGO` and `TRADING_BALANCE_SIZE`, this change will invalidate the current state saved in these files and hence you will have to execute the actions below:

* Close the market maker bot.
* Make sure that you close any open position that may have in your BitMEX account before starting the market maker bot.
* If the files `open_longs.py` & `open_shorts.py` exist in the bot working directory delete them.
* If you need to change your bot configuration go over the file `settings.py` and make the necessary changes.
* Now you can start up the bot and make sure that it starts [`correctly`](#simplified-output).

## Operation Overview

This market maker works on the following principles:

* The market maker bot during its execution will create two important files `open_longs.py` & `open_shorts.py` where it will save its internal state periodically so that it can recover its state after a restart.
* The market maker tracks the last `bidPrice` and `askPrice` of the quoted instrument to determine where to start quoting.
* Based on quant-trading algorithm parameters, the bot creates a descriptions of orders it would like to place.
  - This will be done when the bot gets the quant-trading algorithm real-time decision for the given current position in BitMEX.
  - That personalized decision will either wait or it will increase\decrease the current long or short position. 
	By repeating this process the quant-trading algorithm will totally manage your current position in BitMEX over time without any human intervention.
* These order descriptors are compared with what the bot has currently placed in the market.
  - If an existing order can be amended to the desired value, it is amended.
  - Otherwise, a new order is created.
  - Extra orders are canceled.
* The bot then prints details of contracts traded, current balance, and current position size in percentage of the balance and in contracts amount.

## Simplified Output

The following is some of what you can expect when running this bot:

```
2020-07-10 08:41:49,680 - INFO - market_maker_runner - BitMEX Quant-trading.Network Market Maker Version: v1.0

2020-07-10 08:41:51,253 - INFO - ws_thread - Connecting to wss://testnet.bitmex.com/realtime?subscribe=quote:XBTUSD,trade:XBTUSD,instrument,order:XBTUSD,execution:XBTUSD,margin,position
2020-07-10 08:41:51,254 - INFO - ws_thread - Authenticating with API Key.
2020-07-10 08:41:51,255 - INFO - ws_thread - Started thread
2020-07-10 08:41:52,255 - INFO - ws_thread - Connected to WS. Waiting for data images, this may take a moment...
2020-07-10 08:41:53,066 - INFO - ws_thread - Got all market data. Starting.
2020-07-10 08:41:53,066 - INFO - market_maker - Using symbol XBTUSD.
2020-07-10 08:41:53,066 - INFO - market_maker - Order Manager initializing, connecting to BitMEX. Live run: executing real trades.
2020-07-10 08:41:53,067 - INFO - market_maker - Resetting current position. Canceling all existing orders.
2020-07-10 08:41:53,067 - INFO - bitmex - sending req to https://testnet.bitmex.com/api/v1/order: {"filter": "{\"ordStatus.isTerminated\": false, \"symbol\": \"XBTUSD\"}", "count": 500}
2020-07-10 08:41:54,323 - INFO - quant_base_strategy - print_status - Current XBT Balance: 0.962841
2020-07-10 08:41:54,323 - INFO - quant_base_strategy - print_status - Current Contract Position: 0
2020-07-10 08:41:54,323 - INFO - quant_base_strategy - print_status - Current Internal Position Percentage Size: 0.00
2020-07-10 08:41:54,324 - INFO - quant_base_strategy - print_status - Current Internal Contract Position: 0
2020-07-10 08:42:02,592 - INFO - quant_base_strategy - print_status - Current XBT Balance: 0.962841
2020-07-10 08:42:02,593 - INFO - quant_base_strategy - print_status - Current Contract Position: 0
2020-07-10 08:42:02,593 - INFO - quant_base_strategy - print_status - Current Internal Position Percentage Size: 0.00
2020-07-10 08:42:02,593 - INFO - quant_base_strategy - print_status - Current Internal Contract Position: 0
2020-07-10 08:42:02,593 - INFO - quant_base_strategy - handle_new_decision - new decision OPEN_LONG.
2020-07-10 08:42:02,594 - INFO - market_maker - Creating 1 orders:
2020-07-10 08:42:02,594 - INFO - market_maker -  Buy 882 @ 9163.0
2020-07-10 08:42:02,594 - INFO - bitmex - sending req to https://testnet.bitmex.com/api/v1/order/bulk: {"orders": [{"price": 9163.0, "orderQty": 882, "side": "Buy", "clOrdID": "mm_bitmex_*REDACTED*", "symbol": "XBTUSD", "execInst": "ParticipateDoNotInitiate"}]}
2020-07-10 08:43:52,048 - INFO - ws_thread - Execution: Buy 725 Contracts of XBTUSD at 9163.0
2020-07-10 08:44:02,583 - INFO - ws_thread - Execution: Buy 157 Contracts of XBTUSD at 9163.0
2020-07-10 08:44:02,713 - INFO - quant_base_strategy - check_new_trade - We have a completed trade. Order details: {'orderID': '*REDACTED*', 'clOrdID': 'mm_bitmex_*REDACTED*', 'clOrdLinkID': '', 'account': 119731, 'symbol': 'XBTUSD', 'side': 'Buy', 'simpleOrderQty': None, 'orderQty': 882, 'price': 9163, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Limit', 'timeInForce': 'GoodTillCancel', 'execInst': 'ParticipateDoNotInitiate', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'Filled', 'triggered': '', 'workingIndicator': False, 'ordRejReason': '', 'simpleLeavesQty': None, 'leavesQty': 0, 'simpleCumQty': None, 'cumQty': 882, 'avgPx': 9163.5, 'multiLegReportingType': 'SingleSecurity', 'text': 'Submitted via API.', 'transactTime': '2020-07-10T07:42:02.660Z', 'timestamp': '2020-07-10T07:44:02.524Z'}
2020-07-10 08:58:46,989 - INFO - quant_base_strategy - print_status - Current XBT Balance: 0.962433
2020-07-10 08:58:46,990 - INFO - quant_base_strategy - print_status - Current Contract Position: 882
2020-07-10 08:58:46,990 - INFO - quant_base_strategy - print_status - Avg Cost Price: 9163.5
2020-07-10 08:58:46,991 - INFO - quant_base_strategy - print_status - Avg Entry Price: 9163.5
2020-07-10 08:58:46,991 - INFO - quant_base_strategy - print_status - Current Internal Position Percentage Size: 10.00
2020-07-10 08:58:46,991 - INFO - quant_base_strategy - print_status - Current Internal Contract Position: 882
2020-07-10 08:58:46,991 - INFO - quant_base_strategy - handle_new_decision - new decision NONE.


```

## Troubleshooting

This bot during its execution life cycle it will try to keep its internal representation of the current position and the real current position in sync. This is really important so keep an eye on this. Because the algorithms' decisions are based on this internal representation. So during the bot execution, it will periodically print its status just like below:

```
2020-07-10 08:58:46,989 - INFO - quant_base_strategy - print_status - Current XBT Balance: 0.962433
2020-07-10 08:58:46,990 - INFO - quant_base_strategy - print_status - Current Contract Position: 882
2020-07-10 08:58:46,990 - INFO - quant_base_strategy - print_status - Avg Cost Price: 9163.5
2020-07-10 08:58:46,991 - INFO - quant_base_strategy - print_status - Avg Entry Price: 9163.5
2020-07-10 08:58:46,991 - INFO - quant_base_strategy - print_status - Current Internal Position Percentage Size: 10.00
2020-07-10 08:58:46,991 - INFO - quant_base_strategy - print_status - Current Internal Contract Position: 882
```

* `Current Contract Position` should have the exact same value as `Current Internal Contract Position`. If this is not the case then you will have to close the bot, close your current position in your BitMEX account, and then [`clear the bot internal state`](#clearing-the-bot-internal-state).

Common errors we've seen:

* `TypeError: __init__() got an unexpected keyword argument 'json'`
  * This is caused by an outdated version of `requests`. Run `pip install -U requests` to update.

## Compatibility

This module supports Python 3.5 and later.

## See also

Quant-trading.network has a Python [REST client](https://github.com/Quant-Network/python-api-client)

## Author

support@quant-trading.network
