"""
Servidor autoritativo para Cowboy Battle
Maneja las conexiones WebSocket de los clientes y gestiona jugadores con IDs únicos.
"""

import asyncio
import json
import websockets
import math
import random
import string
from typing import Dict, Any
from collections import defaultdict


# Diccionario para mantener registro de todos los jugadores conectados
# Clave: websocket, Valor: {"id": player_id, "nombre": nombre}
jugadores: Dict[Any, Dict[str, Any]] = {}

# Estado del juego: posiciones de todos los jugadores
# Clave: player_id, Valor: {"x": x, "y": y}
estado: Dict[int, Dict[str, float]] = {}

# Estado de las balas en el juego
# Clave: bala_id, Valor: {"x": x, "y": y, "vx": vx, "vy": vy, "player_id": player_id}
balas: Dict[int, Dict[str, Any]] = {}

# Radio de impacto para detectar colisiones bala-jugador
RADIO_IMPACTO = 25  # "hitbox" de impacto

# Puntuación: player_id -> cantidad de impactos a otros jugadores
puntuacion = defaultdict(int)

# Estado de la partida: "lobby", "jugando", "game_over"
estado_partida = "lobby"

# Jugadores listos en la sala: player_id -> bool
jugadores_listos = defaultdict(bool)

# Host de la partida (el jugador que creó la sala)
host_id = None

# Sistema de salas: código_sala -> {"host_id": int, "jugadores": [websocket, ...]}
salas: Dict[str, Dict[str, Any]] = {}

# Contador para asignar player_id únicos
siguiente_player_id = 1

# Contador para asignar IDs únicos a las balas
siguiente_bala_id = 1


def generar_codigo_sala() -> str:
    """Genera un código único de 6 caracteres para una sala."""
    while True:
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if codigo not in salas:
            return codigo


async def enviar_estado_a_todos():
    """
    Envía el estado completo del juego a todos los jugadores conectados.
    """
    if jugadores:
        # Preparar estado de balas simplificado (posición y player_id para verificar disparos)
        balas_estado = {}
        for bala_id, bala_info in balas.items():
            balas_estado[str(bala_id)] = {
                "x": bala_info["x"],
                "y": bala_info["y"],
                "player_id": bala_info["player_id"]  # Incluir player_id para verificar en cliente
            }
        
        mensaje_estado = {
            "tipo": "estado",
            "jugadores": estado,
            "balas": balas_estado,
            "puntuacion": dict(puntuacion)  # convertir defaultdict a dict normal
        }
        mensaje_json = json.dumps(mensaje_estado)
        tareas = [
            ws.send(mensaje_json)
            for ws in jugadores.keys()
        ]
        await asyncio.gather(*tareas, return_exceptions=True)


async def enviar_evento_a_todos(evento: dict):
    """Envía un evento (mensaje corto) a todos los jugadores."""
    if jugadores:
        mensaje = json.dumps(evento)
        tareas = [ws.send(mensaje) for ws in jugadores.keys()]
        await asyncio.gather(*tareas, return_exceptions=True)


async def actualizar_balas():
    """
    Actualiza la posición de todas las balas, detecta impactos y
    elimina las que salen de la pantalla o golpean a un jugador.
    """
    global balas, estado, puntuacion, estado_partida
    
    # Dimensiones de la pantalla (deben coincidir con el cliente)
    ANCHO_PANTALLA = 800
    ALTO_PANTALLA = 600
    
    balas_a_eliminar = []
    
    for bala_id, bala_info in list(balas.items()):
        # Actualizar posición
        bala_info["x"] += bala_info["vx"]
        bala_info["y"] += bala_info["vy"]
        
        bx, by = bala_info["x"], bala_info["y"]
        owner_id = bala_info["player_id"]
        
        # 1) Si sale de la pantalla, marcar para eliminar
        if bx < 0 or bx > ANCHO_PANTALLA or by < 0 or by > ALTO_PANTALLA:
            balas_a_eliminar.append(bala_id)
            continue
        
        # 2) Revisar impacto contra todos los jugadores
        for pid, pos in estado.items():
            if pid == owner_id:
                continue  # No se auto-pega
            
            dist = math.hypot(pos["x"] - bx, pos["y"] - by)
            if dist <= RADIO_IMPACTO:
                print(f"💥 Impacto! Jugador {owner_id} golpea a {pid}")
                puntuacion[owner_id] += 1
                balas_a_eliminar.append(bala_id)
                
                # Verificar si owner_id ya ganó (3 impactos)
                if puntuacion[owner_id] >= 3 and estado_partida == "jugando":
                    estado_partida = "game_over"
                    
                    await enviar_evento_a_todos({
                        "tipo": "game_over",
                        "ganador": owner_id,
                        "puntuacion": dict(puntuacion)
                    })
                
                break  # Ya no seguimos revisando esta bala
    
    # Eliminar balas marcadas
    for bala_id in balas_a_eliminar:
        balas.pop(bala_id, None)


async def manejar_cliente(websocket: Any):
    """
    Maneja la conexión de un cliente individual.
    
    Args:
        websocket: Objeto WebSocket del cliente conectado
    """
    global siguiente_player_id, siguiente_bala_id, estado, balas, estado_partida, host_id, salas
    
    print("Cliente conectado (esperando mensaje)")
    
    codigo_sala_actual = None  # Código de la sala a la que pertenece este cliente
    
    try:
        # Escuchar mensajes del cliente en un loop
        async for mensaje in websocket:
            try:
                # Intentar interpretar el mensaje como JSON
                datos = json.loads(mensaje)
                print(f"Mensaje recibido: {datos}")
                
                # Procesar mensaje de tipo "crear_partida"
                if datos.get("tipo") == "crear_partida":
                    nombre = datos.get("nombre", "Jugador")
                    
                    # Si ya hay una partida activa, rechazar
                    if estado_partida == "jugando":
                        await websocket.send(json.dumps({
                            "tipo": "error",
                            "mensaje": "Ya hay una partida en curso"
                        }))
                        continue
                    
                    # Generar código único para la sala
                    codigo_sala = generar_codigo_sala()
                    codigo_sala_actual = codigo_sala
                    
                    # Limpiar estado anterior si había una partida
                    if len(jugadores) == 0:
                        estado.clear()
                        balas.clear()
                        puntuacion.clear()
                        jugadores_listos.clear()
                        siguiente_player_id = 1
                    
                    # Asignar un player_id único
                    player_id = siguiente_player_id
                    siguiente_player_id += 1
                    
                    # Este jugador es el host
                    host_id = player_id
                    
                    # Guardar información del jugador
                    jugadores[websocket] = {
                        "id": player_id,
                        "nombre": nombre,
                        "es_host": True
                    }
                    
                    # Recién entra, aún no está listo
                    jugadores_listos[player_id] = False
                    
                    # Crear la sala
                    salas[codigo_sala] = {
                        "host_id": host_id,
                        "jugadores": [websocket]
                    }
                    
                    print(f"Partida creada - Código: {codigo_sala} por: {nombre} (ID: {player_id}, HOST)")
                    
                    # Asignar posición inicial
                    spawn_x, spawn_y = 200, 300
                    estado[player_id] = {"x": spawn_x, "y": spawn_y}
                    
                    # Enviar respuesta con el player_id asignado, posición inicial y código de sala
                    mensaje_respuesta = {
                        "tipo": "asignacion_id",
                        "player_id": player_id,
                        "x": spawn_x,
                        "y": spawn_y,
                        "es_host": True,
                        "codigo_sala": codigo_sala
                    }
                    await websocket.send(json.dumps(mensaje_respuesta))
                    
                    # Enviar estado de la sala a todos
                    await enviar_evento_a_todos({
                        "tipo": "estado_sala",
                        "estado_partida": estado_partida,
                        "host_id": host_id,
                        "codigo_sala": codigo_sala,
                        "jugadores": {
                            pid: {
                                "nombre": info["nombre"],
                                "listo": jugadores_listos[pid],
                                "es_host": info.get("es_host", False)
                            }
                            for _, info in jugadores.items()
                            for pid in [info["id"]]
                        }
                    })
                    
                    # Enviar el estado actual a todos los jugadores
                    await enviar_estado_a_todos()
                
                # Procesar mensaje de tipo "unirse_partida"
                elif datos.get("tipo") == "unirse_partida":
                    nombre = datos.get("nombre", "Jugador")
                    codigo_ingresado = datos.get("codigo_sala", "").upper().strip()
                    
                    # Validar código
                    if not codigo_ingresado or codigo_ingresado not in salas:
                        await websocket.send(json.dumps({
                            "tipo": "error",
                            "mensaje": "Código de sala inválido"
                        }))
                        continue
                    
                    sala = salas[codigo_ingresado]
                    codigo_sala_actual = codigo_ingresado
                    
                    # Si la partida ya está en curso, rechazar
                    if estado_partida == "jugando":
                        await websocket.send(json.dumps({
                            "tipo": "error",
                            "mensaje": "La partida ya está en curso"
                        }))
                        continue
                    
                    # Asignar un player_id único
                    player_id = siguiente_player_id
                    siguiente_player_id += 1
                    
                    # Guardar información del jugador
                    jugadores[websocket] = {
                        "id": player_id,
                        "nombre": nombre,
                        "es_host": False
                    }
                    
                    # Recién entra, aún no está listo
                    jugadores_listos[player_id] = False
                    
                    # Agregar jugador a la sala
                    sala["jugadores"].append(websocket)
                    
                    print(f"Jugador se unió - Código: {codigo_ingresado}, Nombre: {nombre} (ID: {player_id})")
                    
                    # Asignar posición inicial diferente según el número de jugadores
                    num_jugadores = len(jugadores)
                    if num_jugadores == 2:
                        spawn_x, spawn_y = 600, 300
                    else:
                        spawn_x, spawn_y = 400, 300
                    
                    estado[player_id] = {"x": spawn_x, "y": spawn_y}
                    
                    # Enviar respuesta con el player_id asignado y posición inicial
                    mensaje_respuesta = {
                        "tipo": "asignacion_id",
                        "player_id": player_id,
                        "x": spawn_x,
                        "y": spawn_y,
                        "es_host": False,
                        "codigo_sala": codigo_ingresado
                    }
                    await websocket.send(json.dumps(mensaje_respuesta))
                    
                    # Enviar estado de la sala a todos
                    await enviar_evento_a_todos({
                        "tipo": "estado_sala",
                        "estado_partida": estado_partida,
                        "host_id": host_id,
                        "codigo_sala": codigo_ingresado,
                        "jugadores": {
                            pid: {
                                "nombre": info["nombre"],
                                "listo": jugadores_listos[pid],
                                "es_host": info.get("es_host", False)
                            }
                            for _, info in jugadores.items()
                            for pid in [info["id"]]
                        }
                    })
                    
                    # Enviar el estado actual a todos los jugadores
                    await enviar_estado_a_todos()
                
                # Procesar mensaje de tipo "join" para registrar al jugador (legacy, mantener por compatibilidad)
                elif datos.get("tipo") == "join":
                    nombre = datos.get("nombre", "Jugador")
                    
                    # Asignar un player_id único
                    player_id = siguiente_player_id
                    siguiente_player_id += 1
                    
                    # Guardar información del jugador
                    jugadores[websocket] = {
                        "id": player_id,
                        "nombre": nombre
                    }
                    
                    # Recién entra, aún no está listo
                    jugadores_listos[player_id] = False
                    
                    print(f"Jugador registrado: {nombre} (ID: {player_id})")
                    
                    # Asignar posición inicial diferente según el player_id
                    if player_id == 1:
                        spawn_x, spawn_y = 200, 300
                    elif player_id == 2:
                        spawn_x, spawn_y = 600, 300
                    else:
                        spawn_x, spawn_y = 400, 300  # Por si acaso hay más jugadores
                    
                    # Guardar también esa posición en el estado global
                    estado[player_id] = {"x": spawn_x, "y": spawn_y}
                    
                    # Enviar respuesta con el player_id asignado y posición inicial
                    mensaje_respuesta = {
                        "tipo": "asignacion_id",
                        "player_id": player_id,
                        "x": spawn_x,
                        "y": spawn_y
                    }
                    await websocket.send(json.dumps(mensaje_respuesta))
                    
                    # Enviar estado de la sala al nuevo jugador
                    await enviar_evento_a_todos({
                        "tipo": "estado_sala",
                        "estado_partida": estado_partida,
                        "jugadores": {
                            pid: {
                                "nombre": info["nombre"],
                                "listo": jugadores_listos[pid]
                            }
                            for _, info in jugadores.items()
                            for pid in [info["id"]]
                        }
                    })
                    
                    # Enviar el estado actual a todos los jugadores (incluido el nuevo)
                    await enviar_estado_a_todos()
                
                # Procesar mensaje de "ready"
                elif datos.get("tipo") == "ready":
                    player_id_ready = datos.get("player_id")
                    listo = datos.get("listo", False)
                    
                    if websocket in jugadores and jugadores[websocket]["id"] == player_id_ready:
                        jugadores_listos[player_id_ready] = bool(listo)
                        print(f"Jugador {player_id_ready} cambió estado listo a {listo}")
                        
                        # Avisar a todos cómo está la sala
                        await enviar_evento_a_todos({
                            "tipo": "estado_sala",
                            "estado_partida": estado_partida,
                            "host_id": host_id,
                            "codigo_sala": codigo_sala_actual,
                            "jugadores": {
                                pid: {
                                    "nombre": info["nombre"],
                                    "listo": jugadores_listos[pid],
                                    "es_host": info.get("es_host", False)
                                }
                                for _, info in jugadores.items()
                                for pid in [info["id"]]
                            }
                        })
                
                # Procesar mensaje de "iniciar_partida" (solo el host puede hacerlo)
                elif datos.get("tipo") == "iniciar_partida":
                    player_id_iniciar = datos.get("player_id")
                    
                    # Verificar que el jugador es el host
                    if websocket in jugadores and jugadores[websocket]["id"] == player_id_iniciar:
                        if player_id_iniciar != host_id:
                            await websocket.send(json.dumps({
                                "tipo": "error",
                                "mensaje": "Solo el host puede iniciar la partida"
                            }))
                            continue
                        
                        if estado_partida != "lobby":
                            await websocket.send(json.dumps({
                                "tipo": "error",
                                "mensaje": "La partida ya está en curso o terminada"
                            }))
                            continue
                        
                        # Verificar que hay al menos 2 jugadores
                        ids_actuales = [info["id"] for info in jugadores.values()]
                        if len(ids_actuales) < 2:
                            await websocket.send(json.dumps({
                                "tipo": "error",
                                "mensaje": "Se necesitan al menos 2 jugadores para iniciar"
                            }))
                            continue
                        
                        # Resetear puntuación y posiciones
                        for pid in ids_actuales:
                            puntuacion[pid] = 0
                            if pid == ids_actuales[0]:
                                estado[pid] = {"x": 200, "y": 300}
                            elif pid == ids_actuales[1]:
                                estado[pid] = {"x": 600, "y": 300}
                            else:
                                estado[pid] = {"x": 400, "y": 300}
                        
                        # Limpiar balas
                        balas.clear()
                        
                        # Cambiar estado de partida
                        estado_partida = "jugando"
                        
                        print(f"Partida iniciada por el host (ID: {host_id})")
                        
                        # Avisar a todos que empieza la partida
                        await enviar_evento_a_todos({
                            "tipo": "start_game",
                            "estado_partida": estado_partida,
                            "puntuacion": dict(puntuacion)
                        })
                        # Y mandar un estado inicial
                        await enviar_estado_a_todos()
                
                # Procesar mensaje de disparo (solo en estado "jugando")
                elif datos.get("tipo") == "shoot":
                    # Solo permitir disparos si estamos jugando
                    if estado_partida != "jugando":
                        print(f"Disparo ignorado - El juego no está en estado 'jugando' (estado: {estado_partida})")
                        continue
                    player_id_shoot = datos.get("player_id")
                    direccion = datos.get("direccion", "up")
                    
                    # Verificar si el jugador está registrado
                    if websocket in jugadores and jugadores[websocket]["id"] == player_id_shoot:
                        # Verificar si el jugador ya tiene una bala activa
                        tiene_bala_activa = any(
                            bala_info["player_id"] == player_id_shoot
                            for bala_info in balas.values()
                        )
                        
                        if tiene_bala_activa:
                            # El jugador ya tiene una bala activa, ignorar este disparo
                            print(f"Disparo ignorado - Jugador {player_id_shoot} ya tiene una bala activa")
                        elif player_id_shoot in estado:
                            # Obtener posición actual del jugador
                            jugador_pos = estado[player_id_shoot]
                            bala_x = jugador_pos["x"]
                            bala_y = jugador_pos["y"]
                            
                            # Velocidad de la bala
                            velocidad_bala = 10
                            
                            # Calcular velocidad según dirección
                            if direccion == "up":
                                vx, vy = 0, -velocidad_bala
                            elif direccion == "down":
                                vx, vy = 0, velocidad_bala
                            elif direccion == "left":
                                vx, vy = -velocidad_bala, 0
                            elif direccion == "right":
                                vx, vy = velocidad_bala, 0
                            else:
                                vx, vy = 0, -velocidad_bala  # Por defecto hacia arriba
                            
                            # Crear nueva bala
                            bala_id = siguiente_bala_id
                            siguiente_bala_id += 1
                            
                            balas[bala_id] = {
                                "x": bala_x,
                                "y": bala_y,
                                "vx": vx,
                                "vy": vy,
                                "player_id": player_id_shoot
                            }
                            
                            jugador_info = jugadores[websocket]
                            print(f"Bala creada - Jugador {jugador_info['nombre']} (ID: {player_id_shoot}) disparó hacia {direccion}")
                            
                            # Actualizar estado de balas (el loop periódico enviará el estado)
                            await actualizar_balas()
                            # Enviar estado inmediatamente para disparos (importante para respuesta rápida)
                            await enviar_estado_a_todos()
                    else:
                        print(f"Disparo recibido de jugador no registrado o ID incorrecto (ID: {player_id_shoot})")
                
                # Procesar mensaje de actualización de posición (solo en estado "jugando")
                elif datos.get("tipo") == "update_pos":
                    # Solo permitir actualizaciones de posición si estamos jugando
                    if estado_partida != "jugando":
                        continue
                    
                    player_id = datos.get("player_id")
                    x = datos.get("x")
                    y = datos.get("y")
                    
                    # Verificar si el jugador está registrado
                    if websocket in jugadores and jugadores[websocket]["id"] == player_id:
                        # Actualizar el estado del jugador (sin enviar estado inmediatamente)
                        # El loop de actualización de balas se encargará de enviar el estado periódicamente
                        estado[player_id] = {"x": x, "y": y}
                    else:
                        print(f"Posición recibida de jugador no registrado o ID incorrecto (ID: {player_id}): ({x}, {y})")
                    
                else:
                    # Para otros tipos de mensajes, reenviar a todos los jugadores conectados
                    # (excepto al que lo envió, si está registrado)
                    if jugadores:
                        mensaje_reenviar = json.dumps(datos)
                        tareas = [
                            ws.send(mensaje_reenviar)
                            for ws in jugadores.keys()
                            if ws != websocket  # No reenviar al jugador que envió el mensaje
                        ]
                        await asyncio.gather(*tareas, return_exceptions=True)
                    
            except json.JSONDecodeError:
                # Si el mensaje no es JSON válido, ignorarlo
                print(f"Error: Mensaje no es JSON válido: {mensaje}")
            except Exception as e:
                print(f"Error al procesar mensaje: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        # El cliente se desconectó normalmente
        pass
    except Exception as e:
        print(f"Error en la conexión: {e}")
    finally:
        # Remover el jugador del diccionario y del estado cuando se desconecta
        if websocket in jugadores:
            jugador_info = jugadores[websocket]
            player_id = jugador_info["id"]
            print(f"Jugador desconectado: {jugador_info['nombre']} (ID: {player_id})")
            
            # Si el host se desconecta, limpiar la partida
            if player_id == host_id:
                print("El host se desconectó, limpiando la partida")
                # Limpiar la sala
                if codigo_sala_actual and codigo_sala_actual in salas:
                    del salas[codigo_sala_actual]
                host_id = None
                estado_partida = "lobby"
                estado.clear()
                balas.clear()
                puntuacion.clear()
                jugadores_listos.clear()
                jugadores.clear()
                siguiente_player_id = 1
            else:
                # Remover del diccionario de jugadores
                del jugadores[websocket]
                
                # Remover del estado
                if player_id in estado:
                    del estado[player_id]
                
                # Remover de jugadores listos
                if player_id in jugadores_listos:
                    del jugadores_listos[player_id]
                
                # Remover de la sala
                if codigo_sala_actual and codigo_sala_actual in salas:
                    sala = salas[codigo_sala_actual]
                    if websocket in sala["jugadores"]:
                        sala["jugadores"].remove(websocket)
                
                # Notificar a los demás jugadores del cambio de estado
                if jugadores:
                    await enviar_evento_a_todos({
                        "tipo": "estado_sala",
                        "estado_partida": estado_partida,
                        "host_id": host_id,
                        "codigo_sala": codigo_sala_actual,
                        "jugadores": {
                            pid: {
                                "nombre": info["nombre"],
                                "listo": jugadores_listos[pid],
                                "es_host": info.get("es_host", False)
                            }
                            for _, info in jugadores.items()
                            for pid in [info["id"]]
                        }
                    })
                    await enviar_estado_a_todos()
        else:
            print("Cliente desconectado (no estaba registrado como jugador)")


async def loop_actualizacion_balas():
    """
    Loop que actualiza las balas periódicamente y envía el estado a todos los clientes.
    Optimizado para VPN: envía estado a ~30 FPS (cada 33ms) en lugar de 60 FPS.
    Durante la partida: ~60 FPS para movimiento fluido.
    """
    while True:
        # Durante la partida, actualizar más frecuentemente para movimiento fluido
        if estado_partida == "jugando":
            await asyncio.sleep(0.016)  # ~60 FPS durante partida
            # Actualizar balas si existen
            if balas:
                await actualizar_balas()
            # Enviar estado frecuentemente durante partida
            await enviar_estado_a_todos()
        else:
            # En lobby/game_over, actualizar menos frecuentemente
            await asyncio.sleep(0.033)  # ~30 FPS en otros estados
            # Enviar estado periódicamente (para sincronizar estado del juego)
            await enviar_estado_a_todos()


async def main():
    """
    Función principal que inicia el servidor WebSocket.
    """
    print("Iniciando servidor Cowboy Battle...")
    print("Escuchando en 0.0.0.0:9000")
    
    # Iniciar el servidor WebSocket
    # 0.0.0.0 permite conexiones desde cualquier interfaz de red
    async with websockets.serve(manejar_cliente, "0.0.0.0", 9000):
        # Iniciar el loop de actualización de balas en segundo plano
        asyncio.create_task(loop_actualizacion_balas())
        
        # Mantener el servidor corriendo indefinidamente
        await asyncio.Future()  # Ejecutar para siempre


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario")

