import socketio
from aiohttp import web
from aio import el

sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()

async def index(request):
    """Serve the client-side application."""
    with open('index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

class LidarNamespace(socketio.AsyncNamespace):
    def on_connect(self, _, _1, _2):
        print("connect")

# app.router.add_static('/static', 'static')

sio.register_namespace(LidarNamespace("/lidar"))
sio.attach(app, "/api")
app.router.add_get('/', index)