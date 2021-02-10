import websocket
import threading
import traceback
import ssl
import datetime as dt
from time import sleep
import json
import decimal
import logging
from market_maker.settings import settings
from market_maker.auth.APIKeyAuth import generate_expires, generate_signature
from market_maker.utils.log import setup_custom_logger
from market_maker.utils.math import toNearest
from future.utils import iteritems
from future.standard_library import hooks
with hooks():  # Python 2/3 compat
    from urllib.parse import urlparse, urlunparse


# Connects to BitMEX websocket for streaming realtime data.
# The Marketmaker still interacts with this as if it were a REST Endpoint, but now it can get
# much more realtime data without heavily polling the API.
#
# The Websocket offers a bunch of data as raw properties right on the object.
# On connect, it synchronously asks for a push of all this data then returns.
# Right after, the MM can start using its data. It will be updated in realtime, so the MM can
# poll as often as it wants.
class BitMEXWebsocket():

    # Don't grow a table larger than this amount. Helps cap memory usage.
    MAX_TABLE_LEN = 200

    def __init__(self):
        self.logger = logging.getLogger('root')
        self.__reset()
        # key = orderID, value = datetime of last update
        self.unprocessed_orders = {} # This dict will be used to track any unprocessed orders (open or not yet processed by the Quant-trading.Netowork bot)

    def __del__(self):
        self.exit()

    def connect(self, endpoint="", symbol="XBTN15", shouldAuth=True):
        '''Connect to the websocket and initialize data stores.'''

        self.logger.debug("Connecting WebSocket.")
        self.symbol = symbol
        self.shouldAuth = shouldAuth

        # We can subscribe right in the connection querystring, so let's build that.
        # Subscribe to all pertinent endpoints
        subscriptions = [sub + ':' + symbol for sub in ["quote", "trade"]]
        subscriptions += ["instrument"]  # We want all of them
        if self.shouldAuth:
            subscriptions += [sub + ':' + symbol for sub in ["order", "execution"]]
            subscriptions += ["margin", "position"]

        # Get WS URL and connect.
        urlParts = list(urlparse(endpoint))
        urlParts[0] = urlParts[0].replace('http', 'ws')
        urlParts[2] = "/realtime?subscribe=" + ",".join(subscriptions)
        wsURL = urlunparse(urlParts)
        self.logger.info("Connecting to %s" % wsURL)
        self.__connect(wsURL)
        if not self.exited:
            self.logger.info('Connected to WS. Waiting for data images, this may take a moment...')            

        # Connected. Wait for partials
        self.__wait_for_symbol(symbol)
        if self.shouldAuth:
            self.__wait_for_account()
        
        if not self.exited:
            self.logger.info('Got all market data. Starting.')
        else:
            raise Exception("Unable to connect/initialize the websocket client.") # This will interrupt the initialization process

    #
    # Data methods
    #
    def add_new_unprocessed_order(self, order_data):
        """This method adds a new order id to the data struct to be watched for updates."""
        self.unprocessed_orders[order_data["orderID"]] = {
            "last_refresh_ts": dt.datetime.now(),
            "latest_order_data": order_data            
        }

    def delete_unprocessed_order(self, orderID):
        """This method deletes an order from the data struct."""
        if orderID in self.unprocessed_orders:
            del self.unprocessed_orders[orderID]
    
    def get_unprocessed_orders(self):
        """This method returns the unprocessed orders data struct."""
        return self.unprocessed_orders

    def update_unprocessed_order(self, order_data):
        """This method updates an order from the data struct."""
        if "orderID" in order_data and order_data["orderID"] in self.unprocessed_orders:
            unprocessed_order = self.unprocessed_orders[order_data["orderID"]]
            unprocessed_order["last_refresh_ts"] = dt.datetime.now()
            unprocessed_order["latest_order_data"].update(order_data)

    def get_instrument(self, symbol):
        instruments = self.data['instrument']
        matchingInstruments = [i for i in instruments if i['symbol'] == symbol]
        if len(matchingInstruments) == 0:
            raise Exception("Unable to find instrument or index with symbol: " + symbol)
        instrument = matchingInstruments[0]
        # Turn the 'tickSize' into 'tickLog' for use in rounding
        # http://stackoverflow.com/a/6190291/832202
        instrument['tickLog'] = decimal.Decimal(str(instrument['tickSize'])).as_tuple().exponent * -1
        return instrument

    def get_ticker(self, symbol):
        '''Return a ticker object. Generated from instrument.'''

        instrument = self.get_instrument(symbol)

        # If this is an index, we have to get the data from the last trade.
        if instrument['symbol'][0] == '.':
            ticker = {}
            ticker['mid'] = ticker['buy'] = ticker['sell'] = ticker['last'] = instrument['markPrice']
        # Normal instrument
        else:
            bid = instrument['bidPrice'] or instrument['lastPrice']
            ask = instrument['askPrice'] or instrument['lastPrice']
            ticker = {
                "last": instrument['lastPrice'],
                "buy": bid,
                "sell": ask,
                "mid": (bid + ask) / 2
            }

        # The instrument has a tickSize. Use it to round values.
        return {k: toNearest(float(v or 0), instrument['tickSize']) for k, v in iteritems(ticker)}

    def funds(self):
        return self.data['margin'][0]

    def market_depth(self, symbol):
        raise NotImplementedError('orderBook is not subscribed; use askPrice and bidPrice on instrument')
        # return self.data['orderBook25'][0]

    def open_orders(self):
        orders = self.data['order']
        # Filter to only open orders (leavesQty > 0)
        return [o for o in orders if order_leaves_quantity(o)]

    def our_open_orders(self):
        """Filter to only open orders (leavesQty > 0) and those that we actually placed"""
        orders = [o["latest_order_data"] for o in self.unprocessed_orders.values() if order_leaves_quantity(o["latest_order_data"])]        
        return orders

    def position(self, symbol):
        positions = self.data['position']
        pos = [p for p in positions if p['symbol'] == symbol]
        if len(pos) == 0:
            # No position found; stub it
            return {'avgCostPrice': 0, 'avgEntryPrice': 0, 'currentQty': 0, 'symbol': symbol}
        return pos[0]

    def recent_trades(self):
        return self.data['trade']

    #
    # Lifecycle methods
    #
    def error(self, err):
        self._error = err
        self.logger.error(err)
        self.exit()

    def exit(self):
        self.exited = True
        try:
            self.ws.close()
        except:
            pass
        self.logger.info('Exiting ws client.')

    def is_client_stable(self):
        '''Checks if the ws client is up and running as expected.'''
        is_stable = True
        
        if self.__are_best_quotes_synced():
            self.last_sync_ts = dt.datetime.now()
    
        if (self.last_message_received_ts + dt.timedelta(seconds=settings.WS_SEND_PING_TIMEOUT)) < dt.datetime.now() and not self.is_ping_sent:
            self.logger.debug("Sending a ws ping after %d secs of inactivity.", settings.WS_SEND_PING_TIMEOUT)
            self.__send_raw_command('ping')
            self.is_ping_sent = True
            self.last_ping_ts = dt.datetime.now()
    
        if (self.last_sync_ts + dt.timedelta(seconds=settings.WS_NOT_SYNCED_TIMEOUT)) < dt.datetime.now():
            self.logger.error("The ws client does not have the best quotes in sync for more than %d seconds.", settings.WS_NOT_SYNCED_TIMEOUT)
            is_stable = False
    
        if (self.is_ping_sent and (self.last_ping_ts + dt.timedelta(seconds=5)) < dt.datetime.now()):
            self.logger.error("The ws client did not received the expected ping reply after 5 seconds.")
            is_stable = False
        
        return is_stable

    #
    # Private methods
    #

    def __are_best_quotes_synced(self):
        '''Checks if the best quotes are in sync between the quotes and the instrument ticker.'''
        ticker = self.get_ticker(self.symbol)
        lastQuotes = self.data['quote'][-1]
        return lastQuotes['bidPrice'] == ticker['buy'] and lastQuotes['askPrice'] == ticker['sell']

    def __connect(self, wsURL):
        '''Connect to the websocket in a thread.'''
        self.logger.debug("Starting thread")

        ssl_defaults = ssl.get_default_verify_paths()
        sslopt_ca_certs = {'ca_certs': ssl_defaults.cafile}
        self.ws = websocket.WebSocketApp(wsURL,
                                         on_message=self.__on_message,
                                         on_close=self.__on_close,
                                         on_open=self.__on_open,
                                         on_error=self.__on_error,
                                         header=self.__get_auth()
                                         )

        setup_custom_logger('websocket', log_level=settings.LOG_LEVEL)
        self.wst = threading.Thread(target=lambda: self.ws.run_forever(sslopt=sslopt_ca_certs))
        self.wst.daemon = True
        self.wst.start()
        self.logger.info("Started thread")

        # Wait for connect before continuing
        conn_timeout = 5
        while (not self.ws.sock or not self.ws.sock.connected) and conn_timeout and not self._error:
            sleep(1)
            conn_timeout -= 1

        if not conn_timeout or self._error:
            self.logger.error("Couldn't connect to WS! Exiting.")
            self.exit()

    def __get_auth(self):
        '''Return auth headers. Will use API Keys if present in settings.'''

        if self.shouldAuth is False:
            return []

        self.logger.info("Authenticating with API Key.")
        # To auth to the WS using an API key, we generate a signature of a nonce and
        # the WS API endpoint.
        nonce = generate_expires()
        return [
            "api-expires: " + str(nonce),
            "api-signature: " + generate_signature(settings.BITMEX_API_SECRET, 'GET', '/realtime', nonce, ''),
            "api-key:" + settings.BITMEX_API_KEY
        ]

    def __wait_for_account(self):
        '''On subscribe, this data will come down. Wait for it.'''
        # Wait for the keys to show up from the ws
        while (not {'margin', 'position', 'order'} <= set(self.data)
                and not self.exited):
            sleep(0.1)

    def __wait_for_symbol(self, symbol):
        '''On subscribe, this data will come down. Wait for it.'''
        while (not {'instrument', 'trade', 'quote'} <= set(self.data)
                and not self.exited):
            sleep(0.1)

    def __send_command(self, command, args):
        '''Send a command.'''
        self.__send_raw_command({"op": command, "args": args or []})

    def __send_raw_command(self, command):
        '''Send a raw command.'''
        self.ws.send(json.dumps(command))	

    def __on_message(self, message):
        '''Handler for parsing WS messages.'''
        if message == 'pong':
            #We just received a pong caused by a ping we are recording this and returning
            self.last_message_received_ts = dt.datetime.now()
            self.is_ping_sent = False
            return	

        message = json.loads(message)
        self.logger.debug(json.dumps(message))

        table = message['table'] if 'table' in message else None
        action = message['action'] if 'action' in message else None
        try:
            if 'subscribe' in message:
                if message['success']:
                    self.logger.debug("Subscribed to %s." % message['subscribe'])
                else:
                    self.error("Unable to subscribe to %s. Error: \"%s\" Please check and restart." %
                               (message['request']['args'][0], message['error']))
            elif 'status' in message:
                if message['status'] == 400:
                    self.error(message['error'])
                if message['status'] == 401:
                    self.error("API Key incorrect, please check and restart.")
            elif action:
                self.last_message_received_ts = dt.datetime.now()

                if table not in self.data:
                    self.data[table] = []

                if table not in self.keys:
                    self.keys[table] = []

                # There are four possible actions from the WS:
                # 'partial' - full table image
                # 'insert'  - new row
                # 'update'  - update row
                # 'delete'  - delete row
                if action == 'partial':
                    self.logger.debug("%s: partial" % table)
                    self.data[table] = message['data']
                    # Keys are communicated on partials to let you know how to uniquely identify
                    # an item. We use it for updates.
                    self.keys[table] = message['keys']
                elif action == 'insert':
                    self.logger.debug('%s: inserting %s' % (table, message['data']))
                    self.data[table] += message['data']

                    # Limit the max length of the table to avoid excessive memory usage.
                    # Don't trim orders because we'll lose valuable state if we do.
                    if table not in ['order', 'orderBookL2'] and len(self.data[table]) > BitMEXWebsocket.MAX_TABLE_LEN:
                        self.data[table] = self.data[table][(BitMEXWebsocket.MAX_TABLE_LEN // 2):]

                    for insertData in message['data']:
                        if table == 'order':
                            # update the latest unprocessed orders data
                            self.update_unprocessed_order(insertData)

                elif action == 'update':
                    self.logger.debug('%s: updating %s' % (table, message['data']))
                    # Locate the item in the collection and update it.
                    for updateData in message['data']:
                        item = find_by_keys(self.keys[table], self.data[table], updateData)
                        if not item:
                            continue  # No item found to update. Could happen before push

                        # Log executions
                        if table == 'order':
                            is_canceled = 'ordStatus' in updateData and updateData['ordStatus'] == 'Canceled'
                            if 'cumQty' in updateData and not is_canceled:
                                contExecuted = updateData['cumQty'] - item['cumQty']
                                if contExecuted > 0:
                                    instrument = self.get_instrument(item['symbol'])
                                    self.logger.info("Execution: %s %d Contracts of %s at %.*f" %
                                             (item['side'], contExecuted, item['symbol'],
                                              instrument['tickLog'], item['price']))
                        
                            # update the latest unprocessed orders data
                            self.update_unprocessed_order(updateData)

                        # Update this item.
                        item.update(updateData)

                        # Remove canceled / filled orders
                        if table == 'order' and not order_leaves_quantity(item):
                            self.data[table].remove(item)

                elif action == 'delete':
                    self.logger.debug('%s: deleting %s' % (table, message['data']))
                    # Locate the item in the collection and remove it.
                    for deleteData in message['data']:
                        item = find_by_keys(self.keys[table], self.data[table], deleteData)
                        self.data[table].remove(item)
                else:
                    raise Exception("Unknown action: %s" % action)
        except:
            self.logger.error(traceback.format_exc())

    def __on_open(self):
        self.logger.debug("Websocket Opened.")

    def __on_close(self):
        self.logger.info('Websocket Closed')
        self.exit()

    def __on_error(self, error):
        if not self.exited:
            self.error(error)

    def __reset(self):
        # check if a ping was sent out and we are still wating for a pong
        self.is_ping_sent = False
        # the TS of the last message received
        self.last_message_received_ts = dt.datetime.now()
        # the TS of the last time we have sent a ping
        self.last_ping_ts = dt.datetime.now()
        # the TS of the last time we had the ticket and the orderbook synced
        self.last_sync_ts = dt.datetime.now()
        self.data = {}
        self.keys = {}
        self.exited = False
        self._error = None


def find_by_keys(keys, table, matchData):
    for item in table:
        if all(item[k] == matchData[k] for k in keys):
            return item

def order_leaves_quantity(o):
    if o['leavesQty'] is None:
        return True
    return o['leavesQty'] > 0

if __name__ == "__main__":
    # create console handler and set level to debug
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # add formatter to ch
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ws = BitMEXWebsocket()
    ws.logger = logger
    ws.connect("https://testnet.bitmex.com/api/v1")
    while(ws.ws.sock.connected):
        sleep(1)

