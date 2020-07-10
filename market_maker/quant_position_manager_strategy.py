import datetime as dt
from statistics import mean

import quant_trading
from quant_trading import StakeState
from market_maker.quant_base_strategy import QuantBaseManager
from market_maker.settings import settings

class QuantPositionManager(QuantBaseManager):
    """The Quant-trading.Network position manager strategy"""

    ###
    # utility methods to get current state
    ###
    def get_position_state(self):
        """Get the long, short & position states."""
        long_state = StakeState.CLOSED
        short_state = StakeState.CLOSED
        current_position_pct = self.get_internal_position_size_pct() * 100.0

        # current_position_pct needs to be contraint between -100.0 & 100.0 
        # as Quant-trading.Network algorithms do not handle values out of these constraints
        current_position_pct = max(-100.0, current_position_pct)
        current_position_pct = min(100.0, current_position_pct)

        if self.open_long:
            long_state = StakeState.OPENING

        if self.open_short:
            short_state = StakeState.OPENING
        
        return long_state, short_state, current_position_pct

    def get_position_hours(self):
        """
        It returns the avg open hours for an open position and the last open position hours.

        """
        current_ts = dt.datetime.now()
        open_trades_hours = []
        avg_open_position_hours = 0.0
        last_open_position_hours = 0.0
        relevant_trades_ts_list = [l['ts'] for l in self.open_longs_list] if len(self.open_longs_list) > 0 else [s['ts'] for s in self.open_shorts_list]
        hours_closed_position = 0.0 if self.closed_position_ts is None else (current_ts - self.closed_position_ts).total_seconds() / 3600.0

        for trade_ts in relevant_trades_ts_list:
            hours_open_trade = (current_ts - trade_ts).total_seconds() / 3600.0

            open_trades_hours.append(hours_open_trade)
            last_open_position_hours = hours_open_trade

        if len(open_trades_hours) > 0:
            avg_open_position_hours = mean(open_trades_hours)

        return avg_open_position_hours, last_open_position_hours, hours_closed_position
    
    ###
    # Quant-trading.Network algorithm
    ###

    def get_algorithm_decision_request_body(self):
        """Returns the appropriate request body to get the algorithm decision"""
        long_state, short_state, current_position_pct = self.get_position_state()
        current_unrealised_pct = self.get_current_unrealised_pct()
        avg_open_position_hours, last_open_position_hours, hours_closed_position = self.get_position_hours()

        body = quant_trading.ExecPositionManagerAlgoRequest(long_state, short_state, current_position_pct, current_unrealised_pct, 
            avg_open_position_hours, last_open_position_hours, hours_closed_position)

        return body