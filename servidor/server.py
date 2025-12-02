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
import time
from typing import Dict, Any
from collections import defaultdict


# Radio de impacto para detectar colisiones bala-jugador
RADIO_IMPACTO = 25  # "hitbox" de impacto

# Tamaño del barril (debe coincidir con el cliente)
BARRIL_ANCHO = 55
BARRIL_ALTO = 85

# Tamaño del cactus (debe coincidir con el cliente)
CACTUS_ANCHO = 50
CACTUS_ALTO = 80

# Tamaño del jugador (para colisiones)
TAMAÑO_JUGADOR = 60

# Lista de obstáculos fijos del mapa (debe coincidir con el cliente)
OBSTACULOS = [
    {"tipo": "barril_marron", "x": 400, "y": 300},
    {"tipo": "barril_naranja", "x": 260, "y": 210},
    {"tipo": "barril_marron", "x": 540, "y": 210},
    {"tipo": "cactus", "x": 150, "y": 150},
    {"tipo": "cactus", "x": 650, "y": 450},
    {"tipo": "cactus", "x": 400, "y": 100},
]

# Tamaño de la estrella (debe coincidir con el cliente)
ESTRELLA_TAMAÑO = 40

# Tiempo entre apariciones de estrellas (en segundos)
TIEMPO_ENTRE_ESTRELLAS = 10.0  # 10 segundos

# Duración de la invencibilidad (en segundos)
DURACION_INVENCIBILIDAD = 5.0  # 5 segundos

# Mapeo de websocket a código de sala (para encontrar rápidamente la sala de un jugador)
websocket_a_sala: Dict[Any, str] = {}

# Sistema de salas: código_sala -> {
#   "host_id": int,
#   "jugadores": [websocket, ...],  # Lista de websockets
#   "jugadores_info": Dict[websocket, {"id": player_id, "nombre": nombre, "es_host": bool}],
#   "estado": Dict[player_id, {"x": x, "y": y}],  # Posiciones de jugadores
#   "balas": Dict[bala_id, {"x": x, "y": y, "vx": vx, "vy": vy, "player_id": player_id}],
#   "puntuacion": Dict[player_id, int],
#   "estado_partida": str,  # "lobby", "jugando", "game_over"
#   "jugadores_listos": Dict[player_id, bool],
#   "estrella_actual": Dict[str, Any] | None,
#   "jugadores_invencibles": Dict[player_id, float],
#   "siguiente_bala_id": int
# }
salas: Dict[str, Dict[str, Any]] = {}

# Contador global para asignar player_id únicos (único en todo el servidor)
siguiente_player_id = 1


def generar_codigo_sala() -> str:
    """Genera un código único de 6 caracteres para una sala."""
    while True:
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if codigo not in salas:
            return codigo


def obtener_sala_de_websocket(websocket: Any) -> str | None:
    """Obtiene el código de sala de un websocket."""
    return websocket_a_sala.get(websocket)
    return websocket_a_sala.get(websocket)


def obtener_info_sala(codigo_sala: str) -> Dict[str, Any] | None:
    """Obtiene la información de una sala."""
    return salas.get(codigo_sala)


def crear_estructura_sala(host_id: int) -> Dict[str, Any]:
    """Crea una nueva estructura de sala con estado inicial."""
    return {
        "host_id": host_id,
        "jugadores": [],
        "jugadores_info": {},
        "estado": {},  # Posiciones de jugadores
        "balas": {},
        "puntuacion": {},
        "estado_partida": "lobby",
        "jugadores_listos": {},
        "estrella_actual": None,
        "jugadores_invencibles": {},
        "siguiente_bala_id": 1,
        "ultima_estrella_tiempo": 0.0
    }


def colisiona_con_obstaculo(x: float, y: float, radio: float) -> bool:
    """Verifica si una posición colisiona con algún obstáculo."""
    for obs in OBSTACULOS:
        obs_x = obs["x"]
        obs_y = obs["y"]
        tipo_obs = obs["tipo"]
        
        if tipo_obs == "cactus":
            obs_ancho = CACTUS_ANCHO
            obs_alto = CACTUS_ALTO
        else:
            obs_ancho = BARRIL_ANCHO
            obs_alto = BARRIL_ALTO
        
        # Verificar colisión rectangular
        obs_left = obs_x - obs_ancho // 2 - radio
        obs_right = obs_x + obs_ancho // 2 + radio
        obs_top = obs_y - obs_alto // 2 - radio
        obs_bottom = obs_y + obs_alto // 2 + radio
        
        if obs_left <= x <= obs_right and obs_top <= y <= obs_bottom:
            return True
    
    return False


def generar_posicion_estrella() -> tuple[float, float] | None:
    """Genera una posición aleatoria para la estrella que no colisione con obstáculos."""
    ANCHO_PANTALLA = 800
    ALTO_PANTALLA = 600
    MARGEN = 50  # Margen desde los bordes
    
    intentos = 0
    max_intentos = 50
    
    while intentos < max_intentos:
        x = random.uniform(MARGEN, ANCHO_PANTALLA - MARGEN)
        y = random.uniform(MARGEN, ALTO_PANTALLA - MARGEN)
        
        # Verificar que no colisione con obstáculos
        if not colisiona_con_obstaculo(x, y, ESTRELLA_TAMAÑO // 2):
            return (x, y)
        
        intentos += 1
    
    return None  # No se pudo encontrar una posición válida


async def enviar_estado_a_sala(codigo_sala: str):
    """Envía el estado completo del juego a todos los jugadores de una sala específica."""
    sala = obtener_info_sala(codigo_sala)
    if not sala or not sala["jugadores"]:
        return
    
    # Preparar estado de balas simplificado
    balas_estado = {}
    for bala_id, bala_info in sala["balas"].items():
        balas_estado[str(bala_id)] = {
            "x": bala_info["x"],
            "y": bala_info["y"],
            "player_id": bala_info["player_id"]
        }
    
    # Preparar estado de la estrella
    estrella_estado = None
    if sala["estrella_actual"] is not None:
        estrella_estado = {
            "x": sala["estrella_actual"]["x"],
            "y": sala["estrella_actual"]["y"]
        }
    
    # Preparar estado de invencibilidad
    invencibles_estado = {}
    tiempo_actual = time.time()
    for pid, tiempo_fin in list(sala["jugadores_invencibles"].items()):
        if tiempo_actual < tiempo_fin:
            invencibles_estado[pid] = tiempo_fin - tiempo_actual
        else:
            del sala["jugadores_invencibles"][pid]
    
    mensaje_estado = {
        "tipo": "estado",
        "jugadores": sala["estado"],
        "balas": balas_estado,
        "puntuacion": sala["puntuacion"],
        "estrella": estrella_estado,
        "jugadores_invencibles": invencibles_estado
    }
    mensaje_json = json.dumps(mensaje_estado)
    tareas = [
        ws.send(mensaje_json)
        for ws in sala["jugadores"]
    ]
    await asyncio.gather(*tareas, return_exceptions=True)


async def enviar_evento_a_sala(codigo_sala: str, evento: dict):
    """Envía un evento (mensaje corto) a todos los jugadores de una sala específica."""
    sala = obtener_info_sala(codigo_sala)
    if not sala or not sala["jugadores"]:
        return
    mensaje = json.dumps(evento)
    tareas = [ws.send(mensaje) for ws in sala["jugadores"]]
    await asyncio.gather(*tareas, return_exceptions=True)


async def enviar_estado_sala_a_sala(codigo_sala: str):
    """Envía el estado de la sala (lobby) a todos los jugadores de una sala específica."""
    sala = obtener_info_sala(codigo_sala)
    if not sala or not sala["jugadores"]:
        return
    
    jugadores_info = {}
    for ws in sala["jugadores"]:
        if ws in sala["jugadores_info"]:
            info = sala["jugadores_info"][ws]
            pid = info["id"]
            jugadores_info[str(pid)] = {
                "nombre": info["nombre"],
                "listo": sala["jugadores_listos"].get(pid, False),
                "es_host": info.get("es_host", False),
                "sprite_index": info.get("sprite_index", ((pid - 1) % 3) + 1)  # Fallback si no existe
            }
    
    evento = {
        "tipo": "estado_sala",
        "estado_partida": sala["estado_partida"],
        "host_id": sala["host_id"],
        "codigo_sala": codigo_sala,
        "jugadores": jugadores_info
    }
    await enviar_evento_a_sala(codigo_sala, evento)


async def actualizar_balas_sala(codigo_sala: str):
    """
    Actualiza la posición de todas las balas de una sala, detecta impactos y
    elimina las que salen de la pantalla o golpean a un jugador.
    """
    sala = obtener_info_sala(codigo_sala)
    if not sala or sala["estado_partida"] != "jugando":
        return
    
    # Dimensiones de la pantalla (deben coincidir con el cliente)
    ANCHO_PANTALLA = 800
    ALTO_PANTALLA = 600
    
    balas_a_eliminar = []
    
    for bala_id, bala_info in list(sala["balas"].items()):
        # Actualizar posición
        bala_info["x"] += bala_info["vx"]
        bala_info["y"] += bala_info["vy"]
        
        bx, by = bala_info["x"], bala_info["y"]
        owner_id = bala_info["player_id"]
        
        # 1) Si sale de la pantalla, marcar para eliminar
        if bx < 0 or bx > ANCHO_PANTALLA or by < 0 or by > ALTO_PANTALLA:
            balas_a_eliminar.append(bala_id)
            continue
        
        # 2) Revisar colisión con obstáculos (barriles y cactus)
        for obs in OBSTACULOS:
            obs_x = obs["x"]
            obs_y = obs["y"]
            tipo_obs = obs["tipo"]
            
            # Determinar tamaño según el tipo de obstáculo
            if tipo_obs == "cactus":
                obs_ancho = CACTUS_ANCHO
                obs_alto = CACTUS_ALTO
                nombre_obs = "cactus"
            else:
                # Es un barril
                obs_ancho = BARRIL_ANCHO
                obs_alto = BARRIL_ALTO
                nombre_obs = "barril"
            
            # Crear rectángulo del obstáculo (centrado en obs_x, obs_y)
            obs_rect_left = obs_x - obs_ancho // 2
            obs_rect_top = obs_y - obs_alto // 2
            obs_rect_right = obs_x + obs_ancho // 2
            obs_rect_bottom = obs_y + obs_alto // 2
            
            # Verificar si la bala está dentro del rectángulo del obstáculo
            if (obs_rect_left <= bx <= obs_rect_right and 
                obs_rect_top <= by <= obs_rect_bottom):
                # La bala chocó con un obstáculo, eliminarla
                print(f"💥 Bala {bala_id} chocó con {nombre_obs} en ({obs_x}, {obs_y})")
                balas_a_eliminar.append(bala_id)
                break  # Ya no seguimos revisando esta bala
        
        # Si la bala ya fue marcada para eliminar (por chocar con obstáculo), continuar
        if bala_id in balas_a_eliminar:
            continue
        
        # 3) Revisar impacto contra todos los jugadores de esta sala
        for pid, pos in sala["estado"].items():
            if pid == owner_id:
                continue  # No se auto-pega
            
            # Verificar si el jugador objetivo es invencible
            tiempo_actual = time.time()
            if pid in sala["jugadores_invencibles"] and tiempo_actual < sala["jugadores_invencibles"][pid]:
                continue  # El jugador es invencible, no puede ser golpeado
            
            dist = math.hypot(pos["x"] - bx, pos["y"] - by)
            if dist <= RADIO_IMPACTO:
                print(f"💥 Impacto! Jugador {owner_id} golpea a {pid} en sala {codigo_sala}")
                sala["puntuacion"][owner_id] = sala["puntuacion"].get(owner_id, 0) + 1
                balas_a_eliminar.append(bala_id)
                
                # Verificar si owner_id ya ganó (3 impactos)
                if sala["puntuacion"][owner_id] >= 3 and sala["estado_partida"] == "jugando":
                    sala["estado_partida"] = "game_over"
                    
                    await enviar_evento_a_sala(codigo_sala, {
                        "tipo": "game_over",
                        "ganador": owner_id,
                        "puntuacion": sala["puntuacion"]
                    })
                
                break  # Ya no seguimos revisando esta bala
    
    # Eliminar balas marcadas de esta sala
    for bala_id in balas_a_eliminar:
        sala["balas"].pop(bala_id, None)


async def actualizar_estrellas_sala(codigo_sala: str):
    """Actualiza el sistema de estrellas de una sala: detecta recogida."""
    sala = obtener_info_sala(codigo_sala)
    if not sala or sala["estado_partida"] != "jugando":
        return
    
    tiempo_actual = time.time()
    
    if sala["estrella_actual"] is not None:
        # Verificar si algún jugador de esta sala recogió la estrella
        for pid, pos in sala["estado"].items():
            dist = math.hypot(pos["x"] - sala["estrella_actual"]["x"], pos["y"] - sala["estrella_actual"]["y"])
            radio_recogida = (TAMAÑO_JUGADOR + ESTRELLA_TAMAÑO) // 2
            
            if dist <= radio_recogida:
                # El jugador recogió la estrella
                print(f"⭐ Jugador {pid} recogió la estrella en sala {codigo_sala}! Invencible por {DURACION_INVENCIBILIDAD}s")
                sala["jugadores_invencibles"][pid] = tiempo_actual + DURACION_INVENCIBILIDAD
                sala["estrella_actual"] = None  # La estrella desaparece
                break


async def manejar_cliente(websocket: Any):
    """
    Maneja la conexión de un cliente individual.
    
    Args:
        websocket: Objeto WebSocket del cliente conectado
    """
    global siguiente_player_id
    
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
                    
                    # Generar código único para la sala
                    codigo_sala = generar_codigo_sala()
                    codigo_sala_actual = codigo_sala
                    
                    # Asignar un player_id único
                    player_id = siguiente_player_id
                    siguiente_player_id += 1
                    
                    # Crear la estructura de la sala
                    nueva_sala = crear_estructura_sala(player_id)
                    nueva_sala["jugadores"] = [websocket]
                    # Calcular índice de sprite basado en el orden dentro de la sala (1er jugador = 1, 2do = 2, etc.)
                    sprite_index = 1  # El primer jugador (host) usa sprite 1
                    
                    nueva_sala["jugadores_info"][websocket] = {
                        "id": player_id,
                        "nombre": nombre,
                        "es_host": True,
                        "sprite_index": sprite_index
                    }
                    nueva_sala["jugadores_listos"][player_id] = False
                    
                    # Asignar posición inicial
                    spawn_x, spawn_y = 200, 300
                    nueva_sala["estado"][player_id] = {"x": spawn_x, "y": spawn_y}
                    
                    # Guardar la sala
                    salas[codigo_sala] = nueva_sala
                    
                    # Mapear websocket a sala
                    websocket_a_sala[websocket] = codigo_sala
                    
                    print(f"Partida creada - Código: {codigo_sala} por: {nombre} (ID: {player_id}, HOST, Sprite: {sprite_index})")
                    
                    # Enviar respuesta con el player_id asignado, posición inicial y código de sala
                    mensaje_respuesta = {
                        "tipo": "asignacion_id",
                        "player_id": player_id,
                        "x": spawn_x,
                        "y": spawn_y,
                        "es_host": True,
                        "codigo_sala": codigo_sala,
                        "sprite_index": sprite_index
                    }
                    await websocket.send(json.dumps(mensaje_respuesta))
                    
                    # Enviar estado de la sala a todos los jugadores de esta sala
                    await enviar_estado_sala_a_sala(codigo_sala)
                    
                    # Enviar el estado actual del juego a todos los jugadores de esta sala
                    await enviar_estado_a_sala(codigo_sala)
                
                # Procesar mensaje de tipo "unirse_partida"
                elif datos.get("tipo") == "unirse_partida":
                    nombre = datos.get("nombre", "Jugador")
                    codigo_ingresado = datos.get("codigo_sala", "").upper().strip()
                    
                    # Validar código
                    sala = obtener_info_sala(codigo_ingresado)
                    if not sala:
                        await websocket.send(json.dumps({
                            "tipo": "error",
                            "mensaje": "Código de sala inválido"
                        }))
                        continue
                    
                    codigo_sala_actual = codigo_ingresado
                    
                    # Si la partida ya está en curso, rechazar
                    if sala["estado_partida"] == "jugando":
                        await websocket.send(json.dumps({
                            "tipo": "error",
                            "mensaje": "La partida ya está en curso"
                        }))
                        continue
                    
                    # Asignar un player_id único
                    player_id = siguiente_player_id
                    siguiente_player_id += 1
                    
                    # Calcular índice de sprite basado en el orden dentro de la sala
                    # El sprite_index será 1, 2, 3, etc. según el orden de entrada en la sala
                    num_jugadores_antes = len(sala["jugadores"])  # Número de jugadores ANTES de agregar este
                    sprite_index = ((num_jugadores_antes) % 3) + 1  # Rota entre 1, 2, 3 (1er=1, 2do=2, 3ro=3, 4to=1, etc.)
                    
                    # Agregar jugador a la sala
                    sala["jugadores"].append(websocket)
                    
                    sala["jugadores_info"][websocket] = {
                        "id": player_id,
                        "nombre": nombre,
                        "es_host": False,
                        "sprite_index": sprite_index
                    }
                    sala["jugadores_listos"][player_id] = False
                    
                    # Mapear websocket a sala
                    websocket_a_sala[websocket] = codigo_ingresado
                    
                    print(f"Jugador se unió - Código: {codigo_ingresado}, Nombre: {nombre} (ID: {player_id}, Sprite: {sprite_index})")
                    
                    # Asignar posición inicial diferente según el número de jugadores en esta sala
                    num_jugadores = len(sala["jugadores"])
                    if num_jugadores == 2:
                        spawn_x, spawn_y = 600, 300
                    else:
                        spawn_x, spawn_y = 400, 300
                    
                    sala["estado"][player_id] = {"x": spawn_x, "y": spawn_y}
                    
                    # Enviar respuesta con el player_id asignado y posición inicial
                    mensaje_respuesta = {
                        "tipo": "asignacion_id",
                        "player_id": player_id,
                        "x": spawn_x,
                        "y": spawn_y,
                        "es_host": False,
                        "codigo_sala": codigo_ingresado,
                        "sprite_index": sprite_index
                    }
                    await websocket.send(json.dumps(mensaje_respuesta))
                    
                    # Enviar estado de la sala a todos los jugadores de esta sala
                    await enviar_estado_sala_a_sala(codigo_ingresado)
                    
                    # Enviar el estado actual del juego a todos los jugadores de esta sala
                    await enviar_estado_a_sala(codigo_ingresado)
                
                # Procesar mensaje de "ready"
                elif datos.get("tipo") == "ready":
                    codigo_sala = obtener_sala_de_websocket(websocket)
                    if not codigo_sala:
                        continue
                    
                    sala = obtener_info_sala(codigo_sala)
                    if not sala or websocket not in sala["jugadores_info"]:
                        continue
                    
                    player_id_ready = datos.get("player_id")
                    listo = datos.get("listo", False)
                    
                    info_jugador = sala["jugadores_info"][websocket]
                    if info_jugador["id"] == player_id_ready:
                        sala["jugadores_listos"][player_id_ready] = bool(listo)
                        print(f"Jugador {player_id_ready} cambió estado listo a {listo}")
                        
                        # Avisar a todos los jugadores de esta sala cómo está
                        await enviar_estado_sala_a_sala(codigo_sala)
                
                # Procesar mensaje de "iniciar_partida" (solo el host puede hacerlo)
                elif datos.get("tipo") == "iniciar_partida":
                    codigo_sala = obtener_sala_de_websocket(websocket)
                    if not codigo_sala:
                        continue
                    
                    sala = obtener_info_sala(codigo_sala)
                    if not sala or websocket not in sala["jugadores_info"]:
                        continue
                    
                    player_id_iniciar = datos.get("player_id")
                    info_jugador = sala["jugadores_info"][websocket]
                    
                    # Verificar que el jugador es el host
                    if info_jugador["id"] == player_id_iniciar:
                        if player_id_iniciar != sala["host_id"]:
                            await websocket.send(json.dumps({
                                "tipo": "error",
                                "mensaje": "Solo el host puede iniciar la partida"
                            }))
                            continue
                        
                        if sala["estado_partida"] != "lobby":
                            await websocket.send(json.dumps({
                                "tipo": "error",
                                "mensaje": "La partida ya está en curso o terminada"
                            }))
                            continue
                        
                        # Verificar que hay al menos 2 jugadores en esta sala
                        ids_actuales = [info["id"] for info in sala["jugadores_info"].values()]
                        if len(ids_actuales) < 2:
                            await websocket.send(json.dumps({
                                "tipo": "error",
                                "mensaje": "Se necesitan al menos 2 jugadores para iniciar"
                            }))
                            continue
                        
                        # Verificar que todos los jugadores estén listos
                        todos_listos = True
                        jugadores_no_listos = []
                        for pid in ids_actuales:
                            if pid not in sala["jugadores_listos"] or not sala["jugadores_listos"][pid]:
                                todos_listos = False
                                # Buscar el nombre correcto del jugador
                                nombre = f"Jugador {pid}"
                                for ws, info in sala["jugadores_info"].items():
                                    if info["id"] == pid:
                                        nombre = info.get("nombre", f"Jugador {pid}")
                                        break
                                jugadores_no_listos.append(nombre)
                        
                        if not todos_listos:
                            mensaje_error = "Todos los jugadores deben estar listos para iniciar"
                            if jugadores_no_listos:
                                mensaje_error += f". No listos: {', '.join(jugadores_no_listos)}"
                            await websocket.send(json.dumps({
                                "tipo": "error",
                                "mensaje": mensaje_error
                            }))
                            continue
                        
                        # Resetear puntuación y posiciones en esta sala
                        for idx, pid in enumerate(ids_actuales):
                            sala["puntuacion"][pid] = 0
                            if idx == 0:
                                sala["estado"][pid] = {"x": 200, "y": 300}
                            elif idx == 1:
                                sala["estado"][pid] = {"x": 600, "y": 300}
                            else:
                                sala["estado"][pid] = {"x": 400, "y": 300}
                        
                        # Limpiar balas y estrellas de esta sala
                        sala["balas"].clear()
                        sala["estrella_actual"] = None
                        sala["jugadores_invencibles"].clear()
                        sala["ultima_estrella_tiempo"] = 0.0
                        
                        # Cambiar estado de partida de esta sala
                        sala["estado_partida"] = "jugando"
                        
                        print(f"Partida iniciada por el host (ID: {sala['host_id']}) en sala {codigo_sala}")
                        
                        # Avisar a todos los jugadores de esta sala que empieza la partida
                        await enviar_evento_a_sala(codigo_sala, {
                            "tipo": "start_game",
                            "estado_partida": sala["estado_partida"],
                            "puntuacion": sala["puntuacion"]
                        })
                        # Y mandar un estado inicial
                        await enviar_estado_a_sala(codigo_sala)
                
                # Procesar mensaje de disparo (solo en estado "jugando")
                elif datos.get("tipo") == "shoot":
                    codigo_sala = obtener_sala_de_websocket(websocket)
                    if not codigo_sala:
                        continue
                    
                    sala = obtener_info_sala(codigo_sala)
                    if not sala or websocket not in sala["jugadores_info"]:
                        continue
                    
                    # Solo permitir disparos si la sala está jugando
                    if sala["estado_partida"] != "jugando":
                        continue
                    
                    player_id_shoot = datos.get("player_id")
                    direccion = datos.get("direccion", "up")
                    info_jugador = sala["jugadores_info"][websocket]
                    
                    # Verificar si el jugador está registrado
                    if info_jugador["id"] == player_id_shoot:
                        # Verificar si el jugador ya tiene una bala activa en esta sala
                        tiene_bala_activa = any(
                            bala_info["player_id"] == player_id_shoot
                            for bala_info in sala["balas"].values()
                        )
                        
                        if tiene_bala_activa:
                            print(f"Disparo ignorado - Jugador {player_id_shoot} ya tiene una bala activa")
                        elif player_id_shoot in sala["estado"]:
                            # Obtener posición actual del jugador
                            jugador_pos = sala["estado"][player_id_shoot]
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
                            
                            # Crear nueva bala en esta sala
                            bala_id = sala["siguiente_bala_id"]
                            sala["siguiente_bala_id"] += 1
                            
                            sala["balas"][bala_id] = {
                                "x": bala_x,
                                "y": bala_y,
                                "vx": vx,
                                "vy": vy,
                                "player_id": player_id_shoot
                            }
                            
                            print(f"Bala creada - Jugador {info_jugador['nombre']} (ID: {player_id_shoot}) disparó hacia {direccion} en sala {codigo_sala}")
                            
                            # Actualizar estado de balas de esta sala
                            await actualizar_balas_sala(codigo_sala)
                            # Enviar estado inmediatamente para disparos
                            await enviar_estado_a_sala(codigo_sala)
                    else:
                        print(f"Disparo recibido de jugador no registrado o ID incorrecto (ID: {player_id_shoot})")
                
                # Procesar mensaje de actualización de posición (solo en estado "jugando")
                elif datos.get("tipo") == "update_pos":
                    codigo_sala = obtener_sala_de_websocket(websocket)
                    if not codigo_sala:
                        continue
                    
                    sala = obtener_info_sala(codigo_sala)
                    if not sala:
                        continue
                    
                    # Solo permitir actualizaciones de posición si la sala está jugando
                    if sala["estado_partida"] != "jugando":
                        continue
                    
                    player_id = datos.get("player_id")
                    x = datos.get("x")
                    y = datos.get("y")
                    
                    # Verificar si el jugador está registrado en esta sala
                    if websocket in sala["jugadores_info"] and sala["jugadores_info"][websocket]["id"] == player_id:
                        # Actualizar el estado del jugador en esta sala
                        sala["estado"][player_id] = {"x": x, "y": y}
                    else:
                        print(f"Posición recibida de jugador no registrado o ID incorrecto (ID: {player_id}): ({x}, {y})")
                    
                else:
                    # Para otros tipos de mensajes, reenviar a todos los jugadores de la misma sala
                    codigo_sala = obtener_sala_de_websocket(websocket)
                    if codigo_sala:
                        sala = obtener_info_sala(codigo_sala)
                        if sala and sala["jugadores"]:
                            mensaje_reenviar = json.dumps(datos)
                            tareas = [
                                ws.send(mensaje_reenviar)
                                for ws in sala["jugadores"]
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
        # Remover el jugador de la sala cuando se desconecta
        codigo_sala_desconexion = obtener_sala_de_websocket(websocket)
        
        if codigo_sala_desconexion:
            sala = obtener_info_sala(codigo_sala_desconexion)
            if sala and websocket in sala["jugadores_info"]:
                jugador_info = sala["jugadores_info"][websocket]
                player_id = jugador_info["id"]
                nombre = jugador_info.get("nombre", "Desconocido")
                print(f"Jugador desconectado: {nombre} (ID: {player_id}) de sala {codigo_sala_desconexion}")
                
                # Si el host se desconecta, eliminar toda la sala
                if player_id == sala["host_id"]:
                    print(f"El host se desconectó, eliminando sala {codigo_sala_desconexion}")
                    del salas[codigo_sala_desconexion]
                    # Limpiar mapeo de websockets de esta sala
                    for ws in sala["jugadores"]:
                        if ws in websocket_a_sala:
                            del websocket_a_sala[ws]
                else:
                    # Remover el jugador de la sala
                    if websocket in sala["jugadores"]:
                        sala["jugadores"].remove(websocket)
                    if websocket in sala["jugadores_info"]:
                        del sala["jugadores_info"][websocket]
                    if player_id in sala["estado"]:
                        del sala["estado"][player_id]
                    if player_id in sala["jugadores_listos"]:
                        del sala["jugadores_listos"][player_id]
                    if player_id in sala["puntuacion"]:
                        del sala["puntuacion"][player_id]
                    
                    # Remover mapeo de websocket a sala
                    if websocket in websocket_a_sala:
                        del websocket_a_sala[websocket]
                    
                    # Notificar a los demás jugadores de la sala del cambio de estado
                    if sala["jugadores"]:
                        await enviar_estado_sala_a_sala(codigo_sala_desconexion)
                        await enviar_estado_a_sala(codigo_sala_desconexion)
        else:
            print("Cliente desconectado (no estaba en ninguna sala)")


async def loop_generar_estrellas():
    """Loop que genera estrellas periódicamente para todas las salas."""
    while True:
        tiempo_actual = time.time()
        
        # Iterar sobre todas las salas activas
        for codigo_sala, sala in list(salas.items()):
            if sala["estado_partida"] == "jugando":
                # Si no hay estrella y ha pasado suficiente tiempo desde la última
                if sala["estrella_actual"] is None and (tiempo_actual - sala["ultima_estrella_tiempo"]) >= TIEMPO_ENTRE_ESTRELLAS:
                    pos = generar_posicion_estrella()
                    if pos is not None:
                        sala["estrella_actual"] = {
                            "x": pos[0],
                            "y": pos[1],
                            "tiempo_creacion": tiempo_actual
                        }
                        sala["ultima_estrella_tiempo"] = tiempo_actual
                        print(f"⭐ Nueva estrella generada en sala {codigo_sala} en ({pos[0]:.1f}, {pos[1]:.1f})")
                elif sala["estrella_actual"] is not None:
                    # Actualizar detección de recogida para esta sala
                    await actualizar_estrellas_sala(codigo_sala)
        
        await asyncio.sleep(0.1)  # Revisar cada 100ms


async def loop_actualizacion_balas():
    """
    Loop que actualiza las balas periódicamente para todas las salas activas.
    Durante la partida: ~60 FPS para movimiento fluido.
    """
    while True:
        # Iterar sobre todas las salas activas
        for codigo_sala, sala in list(salas.items()):
            if sala["estado_partida"] == "jugando":
                # Actualizar balas de esta sala si existen
                if sala["balas"]:
                    await actualizar_balas_sala(codigo_sala)
                # Enviar estado frecuentemente durante partida
                await enviar_estado_a_sala(codigo_sala)
            elif sala["estado_partida"] in ["lobby", "game_over"]:
                # En lobby/game_over, enviar estado periódicamente
                await enviar_estado_a_sala(codigo_sala)
        
        await asyncio.sleep(0.016)  # ~60 FPS


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
        # Iniciar el loop de generación de estrellas
        asyncio.create_task(loop_generar_estrellas())
        
        # Mantener el servidor corriendo indefinidamente
        await asyncio.Future()  # Ejecutar para siempre


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario")