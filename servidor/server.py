import asyncio
import json
import websockets
import math
from typing import Dict, Any
from collections import defaultdict

jugadores: Dict[Any, Dict[str, Any]] = {}
estado: Dict[int, Dict[str, float]] = {}
balas: Dict[int, Dict[str, Any]] = {}

RADIO_IMPACTO = 25
puntuacion = defaultdict(int)
siguiente_player_id = 1
siguiente_bala_id = 1

async def enviar_estado_a_todos():
    if jugadores:
        balas_estado = {
            str(bid): {"x": b["x"], "y": b["y"], "player_id": b["player_id"]}
            for bid, b in balas.items()
        }

        mensaje = {
            "tipo": "estado",
            "jugadores": estado,
            "balas": balas_estado,
            "puntuacion": dict(puntuacion)
        }

        mensaje_json = json.dumps(mensaje)
        tareas = [ws.send(mensaje_json) for ws in jugadores]
        await asyncio.gather(*tareas, return_exceptions=True)

async def actualizar_balas():
    global balas, estado, puntuacion

    ANCHO, ALTO = 800, 600
    eliminar = []

    for bid, b in list(balas.items()):
        b["x"] += b["vx"]
        b["y"] += b["vy"]

        bx, by = b["x"], b["y"]
        owner = b["player_id"]

        if bx < 0 or bx > ANCHO or by < 0 or by > ALTO:
            eliminar.append(bid)
            continue

        for pid, pos in estado.items():
            if pid == owner:
                continue

            if math.hypot(pos["x"] - bx, pos["y"] - by) <= RADIO_IMPACTO:
                print(f"Impacto! {owner} golpea a {pid}")
                puntuacion[owner] += 1
                eliminar.append(bid)

                if pid == 1:
                    pos["x"], pos["y"] = 200, 300
                elif pid == 2:
                    pos["x"], pos["y"] = 600, 300
                else:
                    pos["x"], pos["y"] = 400, 300
                break

    for bid in eliminar:
        balas.pop(bid, None)

async def manejar_cliente(ws):
    global siguiente_player_id, siguiente_bala_id

    print("Cliente conectado")

    try:
        async for mensaje in ws:
            try:
                datos = json.loads(mensaje)
                print("Mensaje:", datos)

                if datos["tipo"] == "join":
                    nombre = datos.get("nombre", "Jugador")
                    player_id = siguiente_player_id
                    siguiente_player_id += 1

                    jugadores[ws] = {"id": player_id, "nombre": nombre}

                    if player_id == 1:
                        x, y = 200, 300
                    elif player_id == 2:
                        x, y = 600, 300
                    else:
                        x, y = 400, 300

                    estado[player_id] = {"x": x, "y": y}

                    await ws.send(json.dumps({
                        "tipo": "asignacion_id",
                        "player_id": player_id,
                        "x": x,
                        "y": y
                    }))

                    await enviar_estado_a_todos()

                elif datos["tipo"] == "shoot":
                    pid = datos["player_id"]
                    if ws not in jugadores or jugadores[ws]["id"] != pid:
                        continue

                    direccion = datos["direccion"]
                    tiene_bala = any(b["player_id"] == pid for b in balas.values())

                    if tiene_bala:
                        print("Jugador ya tiene bala activa")
                        continue

                    px, py = estado[pid]["x"], estado[pid]["y"]
                    vel = 10

                    if direccion == "up": vx, vy = 0, -vel
                    elif direccion == "down": vx, vy = 0, vel
                    elif direccion == "left": vx, vy = -vel, 0
                    else: vx, vy = vel, 0

                    bala_id = siguiente_bala_id
                    siguiente_bala_id += 1

                    balas[bala_id] = {"x": px, "y": py, "vx": vx, "vy": vy, "player_id": pid}

                    await actualizar_balas()
                    await enviar_estado_a_todos()

                elif datos["tipo"] == "update_pos":
                    pid = datos["player_id"]
                    if ws in jugadores and jugadores[ws]["id"] == pid:
                        estado[pid] = {"x": datos["x"], "y": datos["y"]}
                        await actualizar_balas()
                        await enviar_estado_a_todos()

            except Exception as e:
                print("Error procesando:", e)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if ws in jugadores:
            pid = jugadores[ws]["id"]
            print(f"Jugador {pid} desconectado")
            jugadores.pop(ws)
            estado.pop(pid, None)

            await enviar_estado_a_todos()

async def loop_balas():
    while True:
        await asyncio.sleep(0.016)
        if balas:
            await actualizar_balas()
            await enviar_estado_a_todos()

async def main():
    print("Servidor en 0.0.0.0:9000")
    async with websockets.serve(manejar_cliente, "0.0.0.0", 9000):
        asyncio.create_task(loop_balas())
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Servidor detenido")
