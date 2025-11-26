"""
Servidor autoritativo para Cowboy Battle
Maneja las conexiones WebSocket de los clientes y gestiona jugadores con IDs únicos.
"""

import asyncio
import json
import websockets
import math
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

# Contador para asignar player_id únicos
siguiente_player_id = 1

# Contador para asignar IDs únicos a las balas
siguiente_bala_id = 1


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


async def actualizar_balas():
    """
    Actualiza la posición de todas las balas, detecta impactos y
    elimina las que salen de la pantalla o golpean a un jugador.
    """
    global balas, estado, puntuacion
    
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
    global siguiente_player_id, siguiente_bala_id, estado, balas
    
    print("Cliente conectado (esperando mensaje 'join')")
    
    try:
        # Escuchar mensajes del cliente en un loop
        async for mensaje in websocket:
            try:
                # Intentar interpretar el mensaje como JSON
                datos = json.loads(mensaje)
                print(f"Mensaje recibido: {datos}")
                
                # Procesar mensaje de tipo "join" para registrar al jugador
                if datos.get("tipo") == "join":
                    nombre = datos.get("nombre", "Jugador")
                    
                    # Asignar un player_id único
                    player_id = siguiente_player_id
                    siguiente_player_id += 1
                    
                    # Guardar información del jugador
                    jugadores[websocket] = {
                        "id": player_id,
                        "nombre": nombre
                    }
                    
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
                    
                    # Enviar el estado actual a todos los jugadores (incluido el nuevo)
                    await enviar_estado_a_todos()
                
                # Procesar mensaje de disparo
                elif datos.get("tipo") == "shoot":
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
                
                # Procesar mensaje de actualización de posición
                elif datos.get("tipo") == "update_pos":
                    player_id = datos.get("player_id")
                    x = datos.get("x")
                    y = datos.get("y")
                    
                    # Verificar si el jugador está registrado
                    if websocket in jugadores and jugadores[websocket]["id"] == player_id:
                        # Actualizar el estado del jugador (sin enviar estado inmediatamente)
                        # El loop de actualización de balas se encargará de enviar el estado periódicamente
                        estado[player_id] = {"x": x, "y": y}
                        
                        # Solo imprimir ocasionalmente para no saturar la consola
                        # (comentado para reducir overhead)
                        # jugador_info = jugadores[websocket]
                        # print(f"Posición actualizada - Jugador {jugador_info['nombre']} (ID: {player_id}): ({x}, {y})")
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
            
            # Remover del diccionario de jugadores
            del jugadores[websocket]
            
            # Remover del estado
            if player_id in estado:
                del estado[player_id]
            
            # Notificar a los demás jugadores del cambio de estado
            await enviar_estado_a_todos()
        else:
            print("Cliente desconectado (no estaba registrado como jugador)")


async def loop_actualizacion_balas():
    """
    Loop que actualiza las balas periódicamente y envía el estado a todos los clientes.
    Optimizado para VPN: envía estado a ~30 FPS (cada 33ms) en lugar de 60 FPS.
    """
    while True:
        await asyncio.sleep(0.033)  # ~30 FPS (mejor para VPN con latencia)
        # Actualizar balas si existen
        if balas:
            await actualizar_balas()
        # Enviar estado periódicamente (incluso si no hay balas, para sincronizar posiciones)
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

