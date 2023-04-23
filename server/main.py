from threading import Thread
from aiohttp import web
import socketio
import asyncio
import xv11_parse

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app, "/api")

async def index(request):
    """Serve the client-side application."""
    with open('index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

class LidarNamespace(socketio.AsyncNamespace):

    def __init__(self, namespace):
        super().__init__(namespace)
        el = asyncio.get_event_loop()
        self.t = Thread(target=self.read_lidar_thread, daemon=True, args=[el]).start()

    def read_lidar_thread(self, el):
        print("Starting lidar thread")
        l = xv11_parse.Lidar("COM7")

        scan = {
            "rpm": 0,
            "points": [{
                "distance": 0,
                "strength": 0,
                "invalid": False,
                "warn": False,
            } for _ in range(360)]
        }

        for (ang, rpm, meas) in l.iter_measurements():
            p = scan["points"][ang]
            p["distance"] = meas.distance
            p["strength"] = meas.strength
            p["invalid"] = meas.invalid
            p["warn"] = meas.strength_warn

            if ang == 359:
                scan["rpm"] = rpm
                asyncio.run_coroutine_threadsafe(self.emit("scan", scan, namespace="/lidar"), el)

    def on_connect(self, sid, environ):
        print("lidar connect")

    def on_disconnect(self, sid):
        print("lidar disconnect")


# app.router.add_static('/static', 'static')
app.router.add_get('/', index)
sio.register_namespace(LidarNamespace("/lidar"))

if __name__ == '__main__':
    web.run_app(app, port=80)