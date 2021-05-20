import sys
import os
from os import path
import traceback
import datetime as dt
from time import sleep
from statistics import mean
import pickle
import logging

import quant_trading
from quant_trading.rest import ApiException
from market_maker.market_maker import OrderManager
from market_maker.settings import settings
from market_maker.utils import log, errors
from market_maker.market_maker import XBt_to_XBT


class QuantBaseManager(OrderManager):
    """The Quant-trading.Network base strategy order manager"""

    def __init__(self, quant_algo_api):
        try:
            self.logger = logging.getLogger('root')
            
            # the specific api for the desired quant algo
            self.quant_algo_api = quant_algo_api

            # getting and set the specific algo params
            api_response = self.quant_algo_api.get_algo_params()
            self.decision_polling_interval_in_seconds = api_response.decision_polling_interval_in_seconds
            self.position_stake_size_percentage = api_response.position_stake_size_percentage

            self.stake_size = self.position_stake_size_percentage / 100.0

            # state vars
            self.last_algo_call_ts = dt.datetime.now() - dt.timedelta(seconds=self.decision_polling_interval_in_seconds)
            self.open_long = False
            self.open_short = False
            self.open_qty = 0

            # The lists below store the various trades that were open and used to deleverage a position
            self.open_longs_list = []
            self.open_shorts_list = []

            self.closed_position_ts = None  # The timestamp when a position was closed

            # loads the internal positions from the previous execution
            self.load_open_trades_data()

            # init base class
            super(QuantBaseManager, self).__init__()

            # check if we need to adjust/harmonize the current position and internal state position
            if settings.ADJUST_POSITION_DATA:
                self.adjust_internal_state_position()

        except (KeyboardInterrupt, SystemExit, errors.AuthenticationError, errors.MarketClosedError, errors.InternalStateBotError) as e:
            raise e # this will interrupt the process as desired
        except Exception as e:
            # The bot should not be interrupted from an unexpected error
            self.logger.error("__init__ - Unhandled error, the process will restart. Exception message: %s", e)
            self.logger.error(traceback.format_exc())
            sleep(settings.API_ERROR_INTERVAL)
            self.__restart() # restart the process and try again

    def print_status(self):
        """Print the current MM status."""
        sys.stdout.write("-----\n")
        sys.stdout.flush()

        margin = self.exchange.get_margin()
        position = self.exchange.get_position()
        self.running_qty = self.exchange.get_delta()
        tickLog = self.exchange.get_instrument()['tickLog']
        self.start_XBt = margin["marginBalance"]

        self.logger.info("print_status - Current XBT Balance: %.6f", XBt_to_XBT(self.start_XBt))
        self.logger.info("print_status - Current Contract Position: %d", self.running_qty)
        if position['currentQty'] != 0:
            self.logger.info("print_status - Avg Cost Price: %.*f" % (tickLog, float(position['avgCostPrice'])))
            self.logger.info("print_status - Avg Entry Price: %.*f" % (tickLog, float(position['avgEntryPrice'])))
        self.logger.info("print_status - Current Internal Position Percentage Size: %.2f", (self.get_internal_position_size_pct() * 100.0))
        self.logger.info("print_status - Current Internal Contract Position: %d", self.get_internal_position_size())

    ###
    # load and save internal state
    ###

    def save_open_trades_data(self):
        """It saves the current state to the disk"""
        with open("open_longs.py", "wb") as fp:   # Pickling
            pickle.dump(self.open_longs_list, fp)
        with open("open_shorts.py", "wb") as fp:   # Pickling
            pickle.dump(self.open_shorts_list, fp)
        with open("last_algo_call_ts.py", "wb") as fp:
            pickle.dump(self.last_algo_call_ts, fp) # Pickling

    def load_open_trades_data(self):
        """In case of restart the bot is able to restore its state"""
        if path.isfile("open_longs.py"):
            with open("open_longs.py", "rb") as fp:   # Unpickling
                self.open_longs_list = pickle.load(fp)
        if path.isfile("open_shorts.py"):
            with open("open_shorts.py", "rb") as fp:   # Unpickling
                self.open_shorts_list = pickle.load(fp)
        if path.isfile("last_algo_call_ts.py"):
            with open("last_algo_call_ts.py", "rb") as fp:   # Unpickling
                self.last_algo_call_ts = pickle.load(fp)
        
        all_open_trades = self.open_longs_list + self.open_shorts_list

        # validate the loaded state with the chosen algo params
        current_pos_size_pct = abs(self.get_internal_position_size_pct())

        if current_pos_size_pct > 1.0:
            # we have configuration error probably we are loading execution data
            # that does not match the right algorithm details.
            # i.e. the user has selected another settings.QUANT_ALGO while
            # not clearing its state
            msg = "The bot internal state is erroneous for the current QUANT_ALGO params. " \
                "Please close your position in your BitMEX account and delete the open_longs.py open_shorts.py files to recover from this error."
            raise errors.InternalStateBotError(msg)

    def proccess_new_trade(self, contracts_size, avg_px, side):
        """In case of a new trade the open trades data is updated"""

        new_trade_info = {
            'price': avg_px,
            'contracts_size': abs(contracts_size),
            'ts': dt.datetime.now()
        }

        if side == "Buy":
            self.open_longs_list.append(new_trade_info)
            self.open_long = False
        elif side == "Sell":
            self.open_shorts_list.append(new_trade_info)
            self.open_short = False
        else:
            self.logger.error("proccess_new_trade - Trade side has an unexpected value... Side =  %s", side)

        while len(self.open_longs_list) > 0 and len(self.open_shorts_list) > 0:
            self.proccess_deleverage_trade()
        
        self.save_open_trades_data()

    def proccess_deleverage_trade(self):
        """In case of a deleverage trade we calculate the trade pnl and adjust the open trades accordingly"""

        long_avg_price = self.open_longs_list[0]['price']
        short_avg_price = self.open_shorts_list[0]['price']
        long_contracts_size = self.open_longs_list[0]['contracts_size']
        short_contracts_size = self.open_shorts_list[0]['contracts_size']
        profit_pct = ((short_avg_price / long_avg_price) - 1) * 100

        self.logger.info("proccess_deleverage_trade - Trade results profit_pct: %f", profit_pct)

        # Adjust open trades structure
        if long_contracts_size == short_contracts_size:
            self.open_longs_list = self.open_longs_list[1:]
            self.open_shorts_list = self.open_shorts_list[1:]
        elif long_contracts_size > short_contracts_size:
            self.open_longs_list[0]['contracts_size'] -= short_contracts_size
            self.open_shorts_list = self.open_shorts_list[1:]
        else:
            self.open_shorts_list[0]['contracts_size'] -= long_contracts_size
            self.open_longs_list = self.open_longs_list[1:]

        # We need to set the closed position ts if it is not set yet
        if len(self.open_longs_list) == 0 and len(self.open_shorts_list) == 0:
            self.closed_position_ts = dt.datetime.now()

    def adjust_internal_state_position(self):
        """It will adjust if needed the current internal position size to match the real position size."""
        # check if we need to adjust/harmonize the current position and internal state position
        if self.running_qty != self.get_internal_position_size():
            contracts_diff = self.running_qty - self.get_internal_position_size()
            position = self.exchange.get_position()
            avg_px = float(position['avgEntryPrice']) if position['currentQty'] != 0 else self.get_internal_position_avg_price()
            side = "Buy" if contracts_diff > 0 else "Sell"

            self.logger.info("adjust_internal_state_position - The current position and internal state position are not in sync, therefore we will adjust the internal state by creating a fake trade adjustment.")
            self.logger.info("adjust_internal_state_position - Adjustment trade details. Side: %s Contract size: %d Average price: %f ", side, contracts_diff, avg_px)

            # Adjusting the internal state position
            self.proccess_new_trade(contracts_diff, avg_px, side)

    ###
    # utility methods to get current state
    ###
    def get_internal_position_avg_price(self):
        """Get the internal position average price based on the open trades list data."""
        if len(self.open_longs_list) > 0:
            return mean([l['price'] for l in self.open_longs_list])
        elif len(self.open_shorts_list) > 0:
            return mean([s['price'] for s in self.open_shorts_list])
        
        return None

    def get_internal_position_size_pct(self):
        """Get the internal position size percentage (from -1.0 to 1.0) based on the open trades list data."""
        longs_size = len(self.open_longs_list) * self.stake_size
        shorts_size = len(self.open_shorts_list) * self.stake_size
        
        return longs_size - shorts_size


    def get_internal_position_size(self):
        """Get the internal position size in contracts based on the open trades list data."""
        longs_size = sum([l['contracts_size'] for l in self.open_longs_list])
        shorts_size = sum([s['contracts_size'] for s in self.open_shorts_list])
        
        return longs_size - shorts_size

    def determine_long_qty(self):
        """This method given the current bot state determines how many contracts should be open in for a long order."""       
        if len(self.open_shorts_list) <= 0:
            margin = self.exchange.get_margin()
            margin_balance_sats = margin["marginBalance"]
            return self.determine_contracts_amt(settings.TRADING_BALANCE_SIZE * margin_balance_sats * self.stake_size, self.start_position_buy)
        
        return self.open_shorts_list[0]["contracts_size"]

    def determine_short_qty(self):
        """This method given the current bot state determines how many contracts should be open in for a short order."""       
        if len(self.open_longs_list) <= 0:
            margin = self.exchange.get_margin()
            margin_balance_sats = margin["marginBalance"]
            return self.determine_contracts_amt(settings.TRADING_BALANCE_SIZE * margin_balance_sats * self.stake_size, self.start_position_sell)
        
        return self.open_longs_list[0]["contracts_size"]

    def get_position_state(self):
        """Get the long, short & position states."""
        raise NotImplementedError("This method has not been implemented.")

    def get_position_hours(self):
        """
        It returns the avg open hours for an open position and the last open position hours.

        """
        raise NotImplementedError("This method has not been implemented.")

    def get_current_unrealised_pct(self):
        """Get the current unrealised percentage if any."""
        current_unrealised_pct = 0.0
        current_position_size = abs(self.get_internal_position_size_pct())

        # NOTE: We only assume a trade at time, this means we cannot have 2 open trades in different sides
        if len(self.open_longs_list):
            current_unrealised_pct = ((self.start_position_sell / self.get_internal_position_avg_price()) - 1) * 100 * current_position_size
        elif len(self.open_shorts_list):
            current_unrealised_pct = ((self.get_internal_position_avg_price() / self.start_position_buy) - 1) * 100 * current_position_size

        return current_unrealised_pct
    
    ###
    # Quant-trading.Network algorithm
    ###

    def handle_new_decision(self, new_decision):
        """Method to handle a new algo decision."""
        current_position_size = self.get_internal_position_size_pct()
        self.logger.info("handle_new_decision - new decision %s.", new_decision)

        # possible decisions are NONE OPEN_LONG OPEN_SHORT CANCEL_LONG CANCEL_SHORT
        if new_decision == "OPEN_LONG" and not self.open_long and not self.open_short and current_position_size < 1.0:
            self.open_long = True
            self.open_qty = self.determine_long_qty()
        elif new_decision == "CANCEL_LONG" and self.open_long:
            self.open_long = False
        elif new_decision == "OPEN_SHORT" and not self.open_short and not self.open_long and current_position_size > -1.0:
            self.open_short = True
            self.open_qty = -self.determine_short_qty()
        elif new_decision == "CANCEL_SHORT" and self.open_short:
            self.open_short = False

    def get_algorithm_decision_request_body(self):
        """Returns the appropriate request body to get the algorithm decision"""
        raise NotImplementedError("This method has not been implemented.")

    def get_quant_decision(self):
        """Returns the appropriate request body to get the algorithm decision"""

        if self.last_algo_call_ts + dt.timedelta(seconds=self.decision_polling_interval_in_seconds) <=  dt.datetime.now():
            # The quant algo polling interval has been respected
            body = self.get_algorithm_decision_request_body()
            try:
                # possible decisions are NONE OPEN_LONG OPEN_SHORT CANCEL_LONG CANCEL_SHORT
                api_response = self.quant_algo_api.post_exec_algo(body)

                self.print_status()       # Print the current bot status
                self.handle_new_decision(api_response.decision)
                self.last_algo_call_ts = dt.datetime.now()
            except ApiException as e:
                self.logger.error("get_quant_decision - Exception when calling Quant-trading.Network Api->post_exec_algo: %s", e)

    ###
    # Trades
    ###

    def check_new_trade(self, get_http=False):
        """Check the exchange data and the bot state to process a new trade"""
        processed_order_keys = []

        # key = orderID, value = {"side", "last_refresh_ts", "latest_order_data"}
        for key, value in self.exchange.bitmex.ws.get_unprocessed_orders().items():
            last_refresh_ts = value["last_refresh_ts"]
            unprocessed_order = value["latest_order_data"]

            if (get_http or ("leavesQty" in unprocessed_order and not unprocessed_order["leavesQty"] > 0.0 and
                    ("cumQty" not in unprocessed_order or "avgPx" not in unprocessed_order or "side" not in unprocessed_order)) or # Just in case the websocket does not have all details needed
                    dt.datetime.now() > last_refresh_ts + dt.timedelta(minutes=settings.HTTP_GET_ORDER_REFRESH_TIMEOUT)):
                orders = self.exchange.bitmex.http_get_order(key)
                if len(orders) > 0:
                    # let's check our latest order status
                    unprocessed_order = orders[0]
                    self.exchange.bitmex.ws.update_unprocessed_order(unprocessed_order)
                else:
                    self.logger.warning("check_new_trade - For some reason we cannot get our order details, orderID: %s", key)
            
            if "leavesQty" in unprocessed_order and not unprocessed_order["leavesQty"] > 0.0:
                if unprocessed_order["cumQty"] > 0.0:
                    self.logger.info("check_new_trade - We have a completed trade. Order details: %s", unprocessed_order)
                    self.proccess_new_trade(unprocessed_order["cumQty"], unprocessed_order["avgPx"], unprocessed_order["side"])                    
                else:
                    self.logger.info("check_new_trade - For some reason our order failed. Order details: %s", unprocessed_order)
                processed_order_keys.append(key)
        
        # deleting processed orders
        for orderID in processed_order_keys:
            self.exchange.bitmex.ws.delete_unprocessed_order(orderID) 
    
    ###
    # Orders
    ###

    def place_orders(self) -> None:
        """Create order items for use in convergence."""

        buy_orders = []
        sell_orders = []

        if self.open_long:
            buy_orders.append(self.prepare_order(-1))
        
        if self.open_short:
            sell_orders.append(self.prepare_order(1))

        self.converge_orders(buy_orders, sell_orders)
    
    def prepare_order(self, index):
        """Create an order object."""

        price = self.get_price_offset(index)

        return {'price': price, 'orderQty': abs(self.open_qty), 'side': "Buy" if index < 0 else "Sell"}

    def __cancel_orders(self):
        """Cancel all open orders and process any potential fills."""

        try:
            self.exchange.cancel_all_orders()
            self.check_new_trade(True)    # Check if previous open orders were executed
        except errors.AuthenticationError as e:
            self.logger.info("Was not authenticated; could not cancel orders.")
        except Exception as e:
            self.logger.info("Unable to cancel orders: %s" % e)

    ###
    # Running
    ###
    
    def run_loop(self):
        last_error_msg = ""

        while True:
            try:
                self.check_file_change()
                sleep(settings.LOOP_INTERVAL)

                # This will restart on very short downtime, but if it's longer,
                # the MM will crash entirely as it is unable to connect to the WS on boot.
                if not self.check_connection():
                    self.logger.error("run_loop - Realtime data connection unexpectedly closed, restarting.")
                    self.restart()

                self.sanity_check()       # Ensures health of mm - several cut-out points here
                self.check_new_trade()    # Check if open orders were executed
                self.get_quant_decision() # Get a fresh new decision from the quant algorithm give the current state
                self.place_orders()       # Creates desired orders and converges to existing orders
                last_error_msg = ""
            except (KeyboardInterrupt, SystemExit, errors.AuthenticationError, errors.MarketClosedError) as e:
                raise e
            except Exception as e:
                # The bot should not be interrupted from an unexpected error
                error_msg = str(e)
                if last_error_msg != error_msg:
                    self.logger.error("run_loop - Unhandled error. Exception message: %s", error_msg)
                    self.logger.error(traceback.format_exc())
                    last_error_msg = error_msg # prevent the log being flooded by the same error between loop iterations

    def restart(self):
        self.logger.info("restart - Restarting the market maker... All open orders will be cancelled.")
        self.__cancel_orders()
        self.__restart()

    def exit(self):
        self.logger.info("exit - Shutting down. All open orders will be cancelled.")
        self.__cancel_orders()
        self.exchange.bitmex.exit()
        sys.exit()
    
    def __restart(self):
        # if package executable is being used then we need to use a different executable (the package executable)
        if settings.USING_PACKAGE_EXEC:
            os.execv(sys.argv[0], sys.argv)
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)