import asyncio
from threading import Thread
from typing import Sequence
from aiohttp import web
from web import sio, app
from src.main import main
from api import api
from aio import el

if __name__ == '__main__':
    asyncio.set_event_loop(el)
    api.run_main(main)
    web.run_app(app, host="localhost", port=4000)
