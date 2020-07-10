import logging
from logging.handlers import TimedRotatingFileHandler
from market_maker.settings import settings


def setup_custom_logger(name, log_level=settings.LOG_LEVEL):
    console_handler = logging.StreamHandler()
    handlers = [console_handler]

    if settings.USE_LOG_FILE:
        file_name = "quant_bitmex_bot.log"
        file_handler = TimedRotatingFileHandler(file_name, when="midnight", interval=1)
        file_handler.prefix = "%Y%m%d"
        handlers.append(file_handler)

    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(module)s - %(message)s", handlers=handlers)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    return logger
