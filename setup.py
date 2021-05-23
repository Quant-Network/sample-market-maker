#!/usr/bin/env python
from setuptools import setup
from os.path import dirname, join

import market_maker


here = dirname(__file__)


setup(name='quant-trading-bitmex-market-maker',
      version=market_maker.__version__,
      description='Market making bot for BitMEX API',
      url='https://github.com/Quant-Network/sample-market-maker',
      long_description=open(join(here, 'README.md')).read(),
      long_description_content_type='text/markdown',
      author = "Quant-trading.Network",
      author_email="support@quant-trading.network",
      download_url = "https://github.com/Quant-Network/sample-market-maker/archive/v2.6.tar.gz",
      keywords=["Market making bot", "BitMEX Market making bot", "algorithmic trading", "trading", "bitcoin"],
      install_requires=[
          'requests',
          'websocket-client',
          'future',
          'quant-trading-api'
      ],
      packages=['market_maker', 'market_maker.auth', 'market_maker.utils', 'market_maker.ws'],
      entry_points={
          'console_scripts': ['marketmaker = market_maker:run']
      }
      )
