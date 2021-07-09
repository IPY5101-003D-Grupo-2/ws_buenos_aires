import os
from sanic import Sanic
from sanic.response import json
import cx_Oracle
from sanic.log import logger
import datetime
import aiohttp


def init_session(connection, requestedTag_ignored):
    cursor = connection.cursor()
    cursor.execute("""
        ALTER SESSION SET
          TIME_ZONE = 'America/Santiago'
          NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI'""")


def start_pool():
    pool_min = 6
    pool_max = 6
    pool_inc = 0
    pool_gmd = cx_Oracle.SPOOL_ATTRVAL_WAIT

    print("Connecting to", "oracle-35200-0.cloudclusters.net:35200/XE")

    pool = cx_Oracle.SessionPool(user="buenos_aires",
                                 password="buenos_aires",
                                 dsn="oracle-35200-0.cloudclusters.net:35200/XE",
                                 min=pool_min,
                                 max=pool_max,
                                 increment=pool_inc,
                                 threaded=True,
                                 getmode=pool_gmd,
                                 sessionCallback=init_session)
    return pool


# convert a Python Building object to the Oracle user defined type
# UDT_BUILDING

producto_object = None


def producto_object_adapter(sku=None, cantidad=None, precio=None):
    obj = producto_object.newobject()
    obj.SKU = sku
    obj.CANTIDAD = cantidad
    obj.PRECIO = precio
    return obj


app = Sanic("My Hello, world app")


@app.before_server_start
async def setup_db(app, loop):
    global producto_object
    app.ctx.db = start_pool()
    connection = app.ctx.db.acquire()
    producto_object = connection.gettype("producto_object")


@app.listener('before_server_start')
async def init(app, loop):
    app.ctx.aiohttp_session = aiohttp.ClientSession(loop=loop)


@app.listener('after_server_stop')
async def finish(app, loop):
    loop.run_until_complete(app.ctx.aiohttp_session.close())
    loop.close()

# def myconverter(o):
#     if isinstance(o, datetime.datetime):
#         return o.__str__()


@app.route('/inventario/')
async def inventario(request):
    connection = app.ctx.db.acquire()
    cursor = connection.cursor()
    cursor.execute("select * from producto")
    columns = [col[0] for col in cursor.description]
    cursor.rowfactory = lambda *args: dict(zip(columns, args))
    r = cursor.fetchall()
    for dato in r:
        if dato.get("FECHA"):
            dato["FECHA"] = str(dato.get("FECHA"))
    logger.info(r)
    return json(r)


@app.post('/inventario/modificar-cantidad/')
async def inventario(request):
    data = request.json
    sku = data.get("SKU")
    cantidad = int(data.get("CANTIDAD"))
    connection = app.ctx.db.acquire()
    cursor = connection.cursor()
    realizado = cursor.var(int)
    cursor.callproc('MODIFICAR_CANTIDAD_PRODUCTO_SP',
                    [sku, cantidad, realizado])
    if realizado.getvalue() == 1:
        return json({}, status=200)
    else:
        return json({}, status=404)


@app.route('/inventario-proveedor/')
async def inventario_proveedor(request):
    url = "https://anwo-web-service.herokuapp.com/api/productos/all"

    async with app.ctx.aiohttp_session.get(url) as response:
        productos_proveedor = await response.json()
        productos_proveedor = productos_proveedor.get("productos")

    connection = app.ctx.db.acquire()
    cursor = connection.cursor()
    if request.args.get("sku", None) is not None:
        logger.info(request.args.get("sku"))
        cursor.execute("select * from producto where SKU = :sku_a_buscar",
                       sku_a_buscar=request.args.get("sku"))
    else:
        cursor.execute("select * from producto")
    columns = [col[0] for col in cursor.description]
    cursor.rowfactory = lambda *args: dict(zip(columns, args))
    productos_inventario = cursor.fetchall()
    for dato in productos_inventario:
        if dato.get("FECHA"):
            dato["FECHA"] = str(dato.get("FECHA"))
        producto_encontrado = next((producto for producto in productos_proveedor if producto.get(
            "sku") == dato.get("SKU")), None)
        dato["CANTIDADPROVEEDOR"] = 0
        if producto_encontrado:
            dato["CANTIDADPROVEEDOR"] = producto_encontrado.get("stock")
    return json(productos_inventario)


if __name__ == '__main__':
    port = os.environ.get('PORT') or 8085
    app.run(host="0.0.0.0", port=int(port))
