"""
Cliente para Cowboy Battle
Se conecta al servidor WebSocket, se registra como jugador y muestra una ventana Pygame.
"""

import asyncio
import json
import websockets
import pygame
import sys
import math
import time
from typing import Dict
import cowboy_theme as theme

# Configuración de Pygame
ANCHO_VENTANA = 800
ALTO_VENTANA = 600
VELOCIDAD_MOVIMIENTO = 5


async def cliente():
    """
    Función principal del cliente que maneja la conexión WebSocket y el loop de Pygame.
    """
    # URL del servidor (cambiar localhost por la IP del servidor para conexiones remotas)
    uri = "ws://localhost:9000"

    # Nombre del jugador (se ingresará en la pantalla inicial)
    nombre_jugador = ""
    texto_ingresado = ""   # Texto que el usuario está escribiendo (nombre)
    texto_codigo = ""      # Texto para el código de sala (solo al unirse)
    modo_ingreso = "nombre"  # "nombre" o "codigo" - qué campo se está editando
    codigo_sala = None     # Código de la sala actual

    # Variable para almacenar el player_id asignado
    player_id = None
    es_host = False  # Si el jugador es el host de la partida

    # Estados del juego
    en_menu_principal = True  # Pantalla inicial (crear/unirse)
    ingresando_codigo = False  # Pantalla para ingresar código de sala
    en_lobby = False          # En la sala esperando
    en_juego = False
    game_over = False
    yo_listo = False

    # Info básica de la sala (para mostrar nombres/estados)
    estado_sala = {}
    ganador_id = None

    # Estado de todos los jugadores recibido del servidor
    # Clave: player_id, Valor: {"x": x, "y": y}
    estado_jugadores: Dict[int, Dict[str, float]] = {}

    # Estado de las balas recibido del servidor
    # Clave: bala_id (string), Valor: {"x": x, "y": y}
    estado_balas: Dict[str, Dict[str, float]] = {}
    estado_balas_anterior: Dict[str, Dict[str, float]] = {}  # Para detectar balas que desaparecen

    # Puntuación recibida del servidor
    # Clave: player_id, Valor: cantidad de impactos
    puntuacion: Dict[int, int] = {}
    puntuacion_anterior: Dict[int, int] = {}  # Para detectar cambios

    # Jugadores en estado de daño: player_id -> tiempo cuando fueron golpeados
    jugadores_danados: Dict[int, float] = {}
    DURACION_DANO = 0.3  # Duración del efecto de daño en segundos

    # Estado de la estrella (power-up)
    estrella_pos: Dict[str, float] | None = None

    # Jugadores invencibles: player_id -> tiempo_restante
    jugadores_invencibles: Dict[int, float] = {}

    # Control de disparo: solo permitir un disparo a la vez
    puede_disparar = True
    ultima_direccion_movimiento = "up"

    # Throttling de actualizaciones de posición (solo enviar cada X ms)
    INTERVALO_ACTUALIZACION_POS = 0.05  # 50ms = 20 actualizaciones por segundo
    ultimo_envio_posicion = 0.0

    # Inicializar Pygame
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO_VENTANA, ALTO_VENTANA))
    pygame.display.set_caption("Cowboy Battle - Cliente")
    reloj = pygame.time.Clock()

    # Posición inicial del jugador (se actualizará con la del servidor)
    x = ANCHO_VENTANA // 2
    y = ALTO_VENTANA // 2

    # Variable para rastrear si la posición cambió (para enviar actualización)
    posicion_anterior = (x, y)

    # WebSocket
    websocket = None
    mensaje_error = None

    try:
        # Loop principal: combina Pygame y WebSocket
        corriendo = True
        disparo_solicitado = False
        direccion_disparo = ultima_direccion_movimiento

        while corriendo:
            # ------------------------------
            # Manejo de eventos de Pygame
            # ------------------------------
            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    corriendo = False

                elif evento.type == pygame.KEYDOWN:
                    # ---- Entrada de texto en menú principal ----
                    if en_menu_principal:
                        if evento.key == pygame.K_BACKSPACE:
                            texto_ingresado = texto_ingresado[:-1]
                        elif evento.key == pygame.K_RETURN:
                            # Enter para confirmar nombre
                            if texto_ingresado.strip():
                                nombre_jugador = texto_ingresado.strip()
                        else:
                            # Agregar carácter (limitar longitud)
                            if len(texto_ingresado) < 20 and evento.unicode.isprintable():
                                texto_ingresado += evento.unicode
                    
                    # ---- Entrada de texto en pantalla de código ----
                    elif ingresando_codigo:
                        if evento.key == pygame.K_BACKSPACE:
                            texto_codigo = texto_codigo[:-1]
                        elif evento.key == pygame.K_RETURN:
                            # Enter para unirse si hay código
                            if texto_codigo.strip():
                                codigo_ingresado = texto_codigo.strip().upper()
                                nombre_jugador = texto_ingresado.strip()
                                # Conectar y unirse a partida
                                try:
                                    print(f"Conectando a {uri}...")
                                    websocket = await websockets.connect(uri)
                                    print("Conectado al servidor")
                                    
                                    mensaje_unirse = {
                                        "tipo": "unirse_partida",
                                        "nombre": nombre_jugador,
                                        "codigo_sala": codigo_ingresado,
                                    }
                                    await websocket.send(json.dumps(mensaje_unirse))
                                    print(f"Mensaje enviado: {mensaje_unirse}")
                                    ingresando_codigo = False
                                    mensaje_error = None
                                except Exception as e:
                                    mensaje_error = f"Error al conectar: {e}"
                                    print(mensaje_error)
                        else:
                            # Código: solo mayúsculas y números, máximo 6 caracteres
                            if len(texto_codigo) < 6 and evento.unicode.isalnum():
                                texto_codigo += evento.unicode.upper()

                    # ---- Controles cuando NO estamos en el menú principal ----
                    else:
                        # Disparo solo si estamos en juego
                        if (
                            (evento.key == pygame.K_SPACE or evento.key == pygame.K_j)
                            and puede_disparar
                            and player_id is not None
                            and en_juego
                            and not game_over
                            and websocket is not None
                        ):
                            disparo_solicitado = True
                            puede_disparar = False
                            direccion_disparo = ultima_direccion_movimiento

                        # Marcar listo / no listo en la sala (tecla L)
                        if (
                            evento.key == pygame.K_l
                            and player_id is not None
                            and en_lobby
                            and websocket is not None
                        ):
                            yo_listo = not yo_listo
                            mensaje_ready = {
                                "tipo": "ready",
                                "player_id": player_id,
                                "listo": yo_listo,
                            }
                            try:
                                await websocket.send(json.dumps(mensaje_ready))
                                print(f"📥 Enviado estado listo: {yo_listo}")
                            except Exception as e:
                                print(f"Error al enviar ready: {e}")

                        # Iniciar partida (solo host, tecla ESPACIO mientras está en lobby)
                        if (
                            evento.key == pygame.K_SPACE
                            and player_id is not None
                            and en_lobby
                            and es_host
                            and websocket is not None
                        ):
                            mensaje_iniciar = {
                                "tipo": "iniciar_partida",
                                "player_id": player_id,
                            }
                            try:
                                await websocket.send(json.dumps(mensaje_iniciar))
                                print("🎮 Solicitando inicio de partida...")
                            except Exception as e:
                                print(f"Error al enviar iniciar_partida: {e}")

                # ---- Clicks en el menú principal ----
                elif evento.type == pygame.MOUSEBUTTONDOWN and en_menu_principal:
                    mouse_pos = pygame.mouse.get_pos()
                    (
                        boton_crear_rect,
                        boton_unirse_rect,
                        campo_nombre_rect,
                    ) = theme.draw_menu_principal(
                        pantalla,
                        ANCHO_VENTANA,
                        ALTO_VENTANA,
                        texto_ingresado,
                        mensaje_error,
                    )

                    # Detectar click en campo de texto
                    if campo_nombre_rect.collidepoint(mouse_pos):
                        pass  # Ya está activo

                    # Botón "Crear partida"
                    elif boton_crear_rect.collidepoint(mouse_pos):
                        if texto_ingresado.strip():
                            nombre_jugador = texto_ingresado.strip()
                            # Conectar y crear partida
                            try:
                                print(f"Conectando a {uri}...")
                                websocket = await websockets.connect(uri)
                                print("Conectado al servidor")

                                mensaje_crear = {
                                    "tipo": "crear_partida",
                                    "nombre": nombre_jugador,
                                }
                                await websocket.send(json.dumps(mensaje_crear))
                                print(f"Mensaje enviado: {mensaje_crear}")
                                en_menu_principal = False
                                mensaje_error = None
                            except Exception as e:
                                mensaje_error = f"Error al conectar: {e}"
                                print(mensaje_error)
                        else:
                            mensaje_error = "Por favor ingresa un nombre"

                    # Botón "Unirse a partida" - cambiar a pantalla de código
                    elif boton_unirse_rect.collidepoint(mouse_pos):
                        if texto_ingresado.strip():
                            nombre_jugador = texto_ingresado.strip()
                            ingresando_codigo = True
                            en_menu_principal = False
                            texto_codigo = ""  # Limpiar código anterior
                            mensaje_error = None
                        else:
                            mensaje_error = "Por favor ingresa un nombre primero"
                
                # ---- Clicks en pantalla de ingresar código ----
                elif evento.type == pygame.MOUSEBUTTONDOWN and ingresando_codigo:
                    mouse_pos = pygame.mouse.get_pos()
                    (
                        boton_cancelar_rect,
                        boton_unirse_rect,
                        campo_codigo_rect,
                    ) = theme.draw_ingresar_codigo(
                        pantalla,
                        ANCHO_VENTANA,
                        ALTO_VENTANA,
                        nombre_jugador,
                        texto_codigo,
                        mensaje_error,
                    )

                    # Detectar click en campo de código
                    if campo_codigo_rect.collidepoint(mouse_pos):
                        pass  # Ya está activo

                    # Botón "Cancelar" - volver al menú principal
                    elif boton_cancelar_rect.collidepoint(mouse_pos):
                        ingresando_codigo = False
                        en_menu_principal = True
                        texto_codigo = ""
                        mensaje_error = None

                    # Botón "Unirse" - conectar con el código
                    elif boton_unirse_rect.collidepoint(mouse_pos):
                        if texto_codigo.strip():
                            codigo_ingresado = texto_codigo.strip().upper()
                            # Conectar y unirse a partida
                            try:
                                print(f"Conectando a {uri}...")
                                websocket = await websockets.connect(uri)
                                print("Conectado al servidor")

                                mensaje_unirse = {
                                    "tipo": "unirse_partida",
                                    "nombre": nombre_jugador,
                                    "codigo_sala": codigo_ingresado,
                                }
                                await websocket.send(json.dumps(mensaje_unirse))
                                print(f"Mensaje enviado: {mensaje_unirse}")
                                ingresando_codigo = False
                                mensaje_error = None
                            except Exception as e:
                                mensaje_error = f"Error al conectar: {e}"
                                print(mensaje_error)
                        else:
                            mensaje_error = "Por favor ingresa un código"

            # ------------------------------
            # Movimiento del jugador local
            # ------------------------------
            teclas = pygame.key.get_pressed()

            movimiento_x = 0
            movimiento_y = 0

            # Solo permitir movimiento si estamos en juego
            if en_juego and not game_over:
                # DIRECCIÓN según teclas
                if teclas[pygame.K_w] or teclas[pygame.K_UP]:
                    movimiento_y = -VELOCIDAD_MOVIMIENTO
                    ultima_direccion_movimiento = "up"
                if teclas[pygame.K_s] or teclas[pygame.K_DOWN]:
                    movimiento_y = VELOCIDAD_MOVIMIENTO
                    ultima_direccion_movimiento = "down"
                if teclas[pygame.K_a] or teclas[pygame.K_LEFT]:
                    movimiento_x = -VELOCIDAD_MOVIMIENTO
                    ultima_direccion_movimiento = "left"
                if teclas[pygame.K_d] or teclas[pygame.K_RIGHT]:
                    movimiento_x = VELOCIDAD_MOVIMIENTO
                    ultima_direccion_movimiento = "right"

                # Rects de obstáculos (barriles)
                obstaculos_rects = theme.get_obstaculos_rects()

                # --- Movimiento en X con colisión ---
                if movimiento_x != 0:
                    nuevo_x = x + movimiento_x
                    # Limites de ventana
                    nuevo_x = max(theme.TAMAÑO_CUADRADO // 2,
                                  min(ANCHO_VENTANA - theme.TAMAÑO_CUADRADO // 2, nuevo_x))

                    rect_jugador = pygame.Rect(0, 0, theme.TAMAÑO_CUADRADO, theme.TAMAÑO_CUADRADO)
                    rect_jugador.center = (nuevo_x, y)

                    # Solo aplicamos el movimiento si NO chocamos con un obstáculo
                    if not any(rect_jugador.colliderect(o) for o in obstaculos_rects):
                        x = nuevo_x

                # --- Movimiento en Y con colisión ---
                if movimiento_y != 0:
                    nuevo_y = y + movimiento_y
                    nuevo_y = max(theme.TAMAÑO_CUADRADO // 2,
                                  min(ALTO_VENTANA - theme.TAMAÑO_CUADRADO // 2, nuevo_y))

                    rect_jugador = pygame.Rect(0, 0, theme.TAMAÑO_CUADRADO, theme.TAMAÑO_CUADRADO)
                    rect_jugador.center = (x, nuevo_y)

                    if not any(rect_jugador.colliderect(o) for o in obstaculos_rects):
                        y = nuevo_y

            # ------------------------------
            # Enviar disparo
            # ------------------------------
            if disparo_solicitado and player_id is not None and websocket is not None:
                mensaje_shoot = {
                    "tipo": "shoot",
                    "player_id": player_id,
                    "direccion": direccion_disparo,
                }
                try:
                    await websocket.send(json.dumps(mensaje_shoot))
                    print(f"💥 Disparo enviado: {direccion_disparo}")
                    disparo_solicitado = False
                except Exception as e:
                    print(f"Error al enviar disparo: {e}")
                    disparo_solicitado = False

            # Verificar si el jugador ya no tiene balas activas (puede volver a disparar)
            if not puede_disparar and player_id is not None:
                tiene_bala_activa = any(
                    int(bala_info.get("player_id", -1)) == player_id
                    for bala_info in estado_balas.values()
                )
                if not tiene_bala_activa:
                    puede_disparar = True

            # ------------------------------
            # Enviar posición (throttling)
            # ------------------------------
            if en_juego and not game_over and websocket is not None:
                tiempo_actual = time.time()
                if (x, y) != posicion_anterior and player_id is not None:
                    if tiempo_actual - ultimo_envio_posicion >= INTERVALO_ACTUALIZACION_POS:
                        mensaje_posicion = {
                            "tipo": "update_pos",
                            "player_id": player_id,
                            "x": x,
                            "y": y,
                        }
                        try:
                            await websocket.send(json.dumps(mensaje_posicion))
                            posicion_anterior = (x, y)
                            ultimo_envio_posicion = tiempo_actual
                        except Exception as e:
                            print(f"Error al enviar posición: {e}")

            # ------------------------------
            # Recibir mensajes del servidor
            # ------------------------------
            if websocket is not None:
                try:
                    mensaje = await asyncio.wait_for(websocket.recv(), timeout=0.005)
                    try:
                        datos = json.loads(mensaje)
                        print(f"Mensaje recibido del servidor: {datos}")

                        tipo_msg = datos.get("tipo")

                        # --- Asignación de ID al entrar a sala ---
                        if tipo_msg == "asignacion_id":
                            player_id = datos.get("player_id")
                            es_host = datos.get("es_host", False)
                            codigo_sala = datos.get("codigo_sala")
                            print(f"✅ Player ID asignado: {player_id} (Host: {es_host}) - Sala: {codigo_sala}")

                            # Cambiar a estado de lobby
                            en_menu_principal = False
                            ingresando_codigo = False
                            en_lobby = True

                            # Posición inicial
                            x = datos.get("x", x)
                            y = datos.get("y", y)
                            posicion_anterior = (x, y)
                            print(f"📍 Posición inicial asignada: ({x}, {y})")

                        # --- Error del servidor ---
                        elif tipo_msg == "error":
                             mensaje_error = datos.get("mensaje", "Error desconocido")
                             print(f"❌ Error del servidor: {mensaje_error}")
                             # Si estábamos intentando unirnos, volver a la pantalla de código
                             if ingresando_codigo:
                                 # Mantener en pantalla de código para que pueda intentar de nuevo
                                 pass
                             else:
                                 en_menu_principal = True
                                 ingresando_codigo = False
                             en_lobby = False
                             en_juego = False
                             if websocket:
                                 await websocket.close()
                                 websocket = None

                        # --- Estado del juego (jugadores + balas + puntuación) ---
                        elif tipo_msg == "estado":
                            jugadores_recibidos_raw = datos.get("jugadores", {})
                            jugadores_recibidos = {int(pid): pos for pid, pos in jugadores_recibidos_raw.items()}

                            # Sincronizar solo si hay respawn
                            if player_id is not None and player_id in jugadores_recibidos:
                                pos_servidor = jugadores_recibidos[player_id]
                                servidor_x = pos_servidor["x"]
                                servidor_y = pos_servidor["y"]

                                dist_respawn = math.sqrt((x - servidor_x) ** 2 + (y - servidor_y) ** 2)
                                if dist_respawn > 50:
                                    print(
                                        f"🔄 Respawn/corrección detectado! "
                                        f"({x}, {y}) -> ({servidor_x}, {servidor_y})"
                                    )
                                    x = servidor_x
                                    y = servidor_y
                                    posicion_anterior = (x, y)
                                    ultimo_envio_posicion = time.time()

                            # Otros jugadores con posición del servidor
                            estado_jugadores = {}
                            for pid, pos in jugadores_recibidos.items():
                                if player_id is None or pid != player_id:
                                    estado_jugadores[pid] = pos

                            # Balas
                            balas_recibidas = datos.get("balas", {})

                            # Detectar balas que desaparecieron
                            balas_que_desaparecieron = [
                                bala_id_ant
                                for bala_id_ant in estado_balas_anterior.keys()
                                if bala_id_ant not in balas_recibidas
                            ]

                            estado_balas = balas_recibidas

                            # Estrella (power-up)
                            estrella_pos = datos.get("estrella")

                            # Jugadores invencibles
                            invencibles_recibidos = datos.get("jugadores_invencibles", {})
                            jugadores_invencibles = {
                                int(pid): tiempo_restante 
                                for pid, tiempo_restante in invencibles_recibidos.items()
                            }

                            # Puntuación
                            puntuacion_recibida = datos.get("puntuacion", {})
                            puntuacion_nueva = {
                                int(pid): score for pid, score in puntuacion_recibida.items()
                            }

                            # Detectar si hubo impacto (puntuación sube)
                            tiempo_actual_impacto = time.time()
                            hubo_impacto = any(
                                puntuacion_nueva.get(pid, 0) > puntuacion_anterior.get(pid, 0)
                                for pid in puntuacion_nueva.keys()
                            )

                            # Si hubo impacto y balas desaparecieron, activar efecto daño
                            if hubo_impacto and balas_que_desaparecieron:
                                for bala_id_des in balas_que_desaparecieron:
                                    if bala_id_des in estado_balas_anterior:
                                        bala_pos = estado_balas_anterior[bala_id_des]
                                        bx = bala_pos.get("x", 0)
                                        by = bala_pos.get("y", 0)

                                        jugador_mas_cercano = None
                                        distancia_minima = float("inf")

                                        # Jugadores remotos
                                        for otro_pid, pos in estado_jugadores.items():
                                            jx = pos.get("x", 0)
                                            jy = pos.get("y", 0)
                                            dist = math.sqrt((bx - jx) ** 2 + (by - jy) ** 2)
                                            if dist < distancia_minima and dist < 50:
                                                distancia_minima = dist
                                                jugador_mas_cercano = otro_pid

                                        # Jugador local
                                        if player_id is not None:
                                            dist_local = math.sqrt((bx - x) ** 2 + (by - y) ** 2)
                                            if dist_local < distancia_minima and dist_local < 50:
                                                jugador_mas_cercano = player_id

                                        if jugador_mas_cercano is not None:
                                            jugadores_danados[jugador_mas_cercano] = tiempo_actual_impacto
                                            print(
                                                f"💥 Jugador {jugador_mas_cercano} fue golpeado! "
                                                f"Mostrando imagen de daño"
                                            )

                            puntuacion = puntuacion_nueva
                            puntuacion_anterior = puntuacion_nueva.copy()
                            estado_balas_anterior = estado_balas.copy()

                            # Limpiar estados de daño expirados
                            tiempo_limpieza = time.time()
                            jugadores_a_remover = [
                                pid for pid, t_d in list(jugadores_danados.items())
                                if tiempo_limpieza - t_d >= DURACION_DANO
                            ]
                            for pid in jugadores_a_remover:
                                del jugadores_danados[pid]

                        # --- Estado de sala (lobby) ---
                        elif tipo_msg == "estado_sala":
                            estado_sala = datos
                            if "codigo_sala" in datos:
                                codigo_sala = datos.get("codigo_sala")

                            if player_id is not None:
                                jugadores_sala = datos.get("jugadores", {})
                                if str(player_id) in jugadores_sala:
                                    yo_listo = jugadores_sala[str(player_id)].get("listo", False)
                                host_id_sala = datos.get("host_id")
                                es_host = (host_id_sala == player_id)

                        # --- Inicio de partida ---
                        elif tipo_msg == "start_game":
                            en_lobby = False
                            en_juego = True
                            game_over = False
                            print("🎮 ¡Comienza la partida!")
                            puede_disparar = True

                        # --- Game over ---
                        elif tipo_msg == "game_over":
                            game_over = True
                            en_juego = False
                            ganador_id = datos.get("ganador")
                            puntuacion_recibida = datos.get("puntuacion", {})
                            puntuacion = {
                                int(pid): score for pid, score in puntuacion_recibida.items()
                            }
                            print(f"🏁 Game over. Ganador: Jugador {ganador_id}")

                    except json.JSONDecodeError:
                        print(f"Mensaje recibido (texto plano): {mensaje}")
                    except Exception as e:
                        print(f"Error al procesar mensaje: {e}")
                except asyncio.TimeoutError:
                    # No hay mensajes, continuar con el loop
                    pass
                except websockets.exceptions.ConnectionClosed:
                    print("Conexión cerrada por el servidor")
                    if en_lobby:
                        # Volver al menú principal si se desconecta en lobby
                        en_menu_principal = True
                        en_lobby = False
                        en_juego = False
                        websocket = None
                    else:
                        corriendo = False

            # ------------------------------
            # DIBUJO – delegamos a cowboy_theme
            # ------------------------------
            if en_menu_principal:
                theme.draw_menu_principal(
                    pantalla,
                    ANCHO_VENTANA,
                    ALTO_VENTANA,
                    texto_ingresado,
                    mensaje_error,
                )

            elif ingresando_codigo:
                theme.draw_ingresar_codigo(
                    pantalla,
                    ANCHO_VENTANA,
                    ALTO_VENTANA,
                    nombre_jugador,
                    texto_codigo,
                    mensaje_error,
                )

            elif en_lobby:
                theme.draw_lobby_screen(
                    pantalla,
                    ANCHO_VENTANA,
                    ALTO_VENTANA,
                    player_id,
                    yo_listo,
                    estado_sala,
                    es_host,
                    codigo_sala,
                )

            elif game_over:
                # Construir diccionario de nombres desde estado_sala
                nombres_jugadores = {}
                if estado_sala and "jugadores" in estado_sala:
                    for pid_str, info in estado_sala["jugadores"].items():
                        pid = int(pid_str)
                        nombre = info.get("nombre", f"P{pid}")
                        nombres_jugadores[pid] = nombre
                
                theme.draw_game_over_screen(
                    pantalla,
                    ANCHO_VENTANA,
                    ALTO_VENTANA,
                    ganador_id,
                    puntuacion,
                    nombres_jugadores,
                )

            else:
                # Limpiar por si acaso el jugador local quedó dentro de estado_jugadores
                if player_id is not None and player_id in estado_jugadores:
                    del estado_jugadores[player_id]

                # Construir diccionario de nombres desde estado_sala
                nombres_jugadores = {}
                if estado_sala and "jugadores" in estado_sala:
                    for pid_str, info in estado_sala["jugadores"].items():
                        pid = int(pid_str)
                        nombre = info.get("nombre", f"P{pid}")
                        nombres_jugadores[pid] = nombre

                # Dibujar pantalla de juego con todos los estados
                theme.draw_game_screen(
                    pantalla,
                    ANCHO_VENTANA,
                    ALTO_VENTANA,
                    player_id,
                    estado_jugadores,
                    x,
                    y,
                    estado_balas,
                    puntuacion,
                    jugadores_danados,
                    nombres_jugadores,
                    estrella_pos,
                    jugadores_invencibles,
                )

            pygame.display.flip()
            reloj.tick(60)

    except websockets.exceptions.ConnectionClosed:
        print("Conexión cerrada por el servidor")
    except ConnectionRefusedError:
        print("Error: No se pudo conectar al servidor. ¿Está el servidor corriendo?")
    except Exception as e:
        print(f"Error en la conexión: {e}")
    finally:
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    try:
        asyncio.run(cliente())
    except KeyboardInterrupt:
        print("\nCliente detenido por el usuario")
        pygame.quit()
        sys.exit()
