from os.path import join
import logging

########################################################################################################################
# Connection/Auth
########################################################################################################################

# API URL.
BASE_URL = "https://testnet.bitmex.com/api/v1/" # Once you're ready, comment this.
# BASE_URL = "https://www.bitmex.com/api/v1/" # Once you're ready, uncomment this.

# The BitMEX API requires permanent API keys. Go to https://testnet.bitmex.com/app/apiKeys to fill these out.
BITMEX_API_KEY = ""
BITMEX_API_SECRET = ""

# The Quant-trading.Network API requires permanent API keys. Go to https://www.quant-trading.network/app/account#api-key to get it.
QUANT_API_KEY = ""


########################################################################################################################
# Target
########################################################################################################################

# Instrument to market make on BitMEX.
SYMBOL = "XBTUSD"

# The Quant-trading.Network algorithm to use.
# Possible options: BitcoinFuturesSwinger, BitcoinFuturesManager & BitcoinFuturesMarketMaker
QUANT_ALGO = "BitcoinFuturesMarketMaker"


########################################################################################################################
# Order Size
########################################################################################################################

# The maximum trading position size in terms of percentage of your BitMEX account margin balance.
# (1.0 = 100% of the margin balance). This setting has the following limits. Min=0.1 & Max=1.0
TRADING_BALANCE_SIZE = 1.0


########################################################################################################################
# Trading Behavior
########################################################################################################################

# If True, will only send orders that rest in the book (ExecInst: ParticipateDoNotInitiate).
# Use to guarantee a maker rebate. (this is highly recommended to get the fee rebate)
POST_ONLY = True

# If true the internal state current position size will be adjusted to match the current position at startup
# Warning: Please make sure to not use the associated BitMEX account other than by this bot. When you start trading
# with this bot please make sure that you do not have any open position on BitMEX, otherwise, 
# this may lead to unpredictable consequences including your BitMEX account liquidation!!!
ADJUST_POSITION_DATA = True

########################################################################################################################
# Misc Behavior, Technicals
########################################################################################################################

# True if this package was installed and it is being executed through the provided executable.
# Set this to false if you are executing this as a script.
USING_PACKAGE_EXEC = True

# How often to re-check and replace orders.
# Generally, it's safe to make this short because we're fetching from websockets. But if too many
# order amend/replaces are done, you may hit a ratelimit. If so, email BitMEX if you feel you need a higher limit.
LOOP_INTERVAL = 5

# Wait times between orders / errors
API_REST_INTERVAL = 1
API_ERROR_INTERVAL = 10
TIMEOUT = 7

# Available levels: logging.(DEBUG|INFO|WARN|ERROR)
LOG_LEVEL = logging.INFO

# To define if the logging process should also log to a log file
USE_LOG_FILE = True

# To uniquely identify orders placed by this bot, the bot sends a ClOrdID (Client order ID) that is attached
# to each order so its source can be identified. This keeps the market maker from cancelling orders that are
# manually placed, or orders placed by another bot.
#
# If you are running multiple bots on the same symbol, give them unique ORDERID_PREFIXes - otherwise they will
# cancel each others' orders.
# Max length is 13 characters.
ORDERID_PREFIX = "mm_bitmex_"

# Tolerance time (in seconds) for the websocket client to receive a fresh message before sending a ping to check its status
WS_SEND_PING_TIMEOUT = 20

# Tolerance time (in seconds) for the websocket client to have the best quotes synced before considering it unstable for use
WS_NOT_SYNCED_TIMEOUT = LOOP_INTERVAL * 7

# Wait time (in minutes) from last order websocket update to get a fresh http get order request
HTTP_GET_ORDER_REFRESH_TIMEOUT = 5

# If any of these files (and this file) changes, reload the bot.
WATCHED_FILES = [join('market_maker', 'market_maker.py'), join('market_maker', 'bitmex.py'), 
    join('market_maker', 'market_maker_runner.py'), join('market_maker', 'quant_base_strategy.py'), 
    join('market_maker', 'quant_position_manager_strategy.py'), join('market_maker', 'quant_position_swinger_strategy.py'), 
    'settings.py']


########################################################################################################################
# BitMEX Portfolio
########################################################################################################################

# Specify the contracts that you hold. These will be used in portfolio calculations.
CONTRACTS = ['XBTUSD']
