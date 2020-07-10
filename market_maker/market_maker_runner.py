from __future__ import absolute_import
import sys

import quant_trading
from market_maker.settings import settings
from market_maker.utils import log, constants
from market_maker.quant_position_manager_strategy import QuantPositionManager
from market_maker.quant_position_swinger_strategy import QuantPositionSwinger

#
# Helpers
#
logger = log.setup_custom_logger('root')

def run():
    logger.info('BitMEX Quant-trading.Network Market Maker Version: %s\n' % constants.VERSION)

    # Configure API key authorization: ApiKeyAuth
    configuration = quant_trading.Configuration()
    configuration.api_key['X-API-KEY'] = settings.QUANT_API_KEY        

    if settings.QUANT_ALGO == "BitcoinFuturesSwinger":
        # create an instance of the API class
        api_instance = quant_trading.BitcoinFuturesSwingerApi(quant_trading.ApiClient(configuration))
        om = QuantPositionSwinger(api_instance)
    elif settings.QUANT_ALGO == "BitcoinFuturesManager":
        # create an instance of the API class
        api_instance = quant_trading.BitcoinFuturesManagerApi(quant_trading.ApiClient(configuration))
        om = QuantPositionManager(api_instance)
    elif settings.QUANT_ALGO == "BitcoinFuturesMarketMaker":
        # create an instance of the API class
        api_instance = quant_trading.BitcoinFuturesMarketMakerApi(quant_trading.ApiClient(configuration))
        om = QuantPositionManager(api_instance)
    else:
        raise NotImplementedError("The settings.QUANT_ALGO is not valid.")

    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        om.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
