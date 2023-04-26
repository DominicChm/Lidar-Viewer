from threading import Thread
from typing import Sequence
from aiohttp import web
import socketio
import asyncio
import rplidar_parse
import queue
import copy
from web import sio, app
from src.main import main
from api import api
from aio import el

if __name__ == '__main__':
    api.run_main(main)
    web.run_app(app, host="localhost", port=4000, loop=el)
