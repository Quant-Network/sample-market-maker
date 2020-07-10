import datetime as dt
from statistics import mean

import quant_trading
from quant_trading import PositionState
from market_maker.quant_base_strategy import QuantBaseManager
from market_maker.settings import settings

class QuantPositionSwinger(QuantBaseManager):
    """The Quant-trading.Network position manager strategy"""

    ###
    # utility methods to get current state
    ###
    def get_position_state(self):
        """Get the long, short & position states."""
        long_state = PositionState.CLOSED
        short_state = PositionState.CLOSED

        if self.open_long:
            long_state = PositionState.OPENING
        elif len(self.open_longs_list) > 0:
            long_state = PositionState.OPEN

        if self.open_short:
            short_state = PositionState.OPENING
        elif len(self.open_shorts_list) > 0:
            short_state = PositionState.OPEN
        
        return long_state, short_state

    def get_position_hours(self):
        """
        It returns the avg open hours for an open position and the last open position hours.

        """
        current_ts = dt.datetime.now()
        open_position_hours = 0.0
        hours_closed_position = 0.0 if self.closed_position_ts is None else (current_ts - self.closed_position_ts).total_seconds() / 3600.0

        if len(self.open_longs_list) > 0:
            open_position_hours = (current_ts - self.open_longs_list[0]["ts"]).total_seconds() / 3600.0
        elif len(self.open_shorts_list) > 0:
            open_position_hours = (current_ts - self.open_shorts_list[0]["ts"]).total_seconds() / 3600.0

        return open_position_hours, hours_closed_position
    
    ###
    # Quant-trading.Network algorithm
    ###

    def get_algorithm_decision_request_body(self):
        """Returns the appropriate request body to get the algorithm decision"""
        long_state, short_state = self.get_position_state()
        current_unrealised_pct = self.get_current_unrealised_pct()
        open_position_hours, hours_closed_position = self.get_position_hours()

        body = quant_trading.ExecPositionSwingerAlgoRequest(long_state, short_state, current_unrealised_pct, 
            open_position_hours, hours_closed_position)

        return body