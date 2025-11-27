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

    # Nombre del jugador (puedes cambiarlo)
    nombre_jugador = "Fabi"

    # Variable para almacenar el player_id asignado
    player_id = None

    # Estados del juego
    en_lobby = True
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

    # Control de disparo: solo permitir un disparo a la vez
    puede_disparar = True  # Flag para controlar si puede disparar
    ultima_direccion_movimiento = "up"  # Dirección del último movimiento

    # Throttling de actualizaciones de posición (solo enviar cada X ms)
    INTERVALO_ACTUALIZACION_POS = 0.05  # 50ms = 20 actualizaciones por segundo (mejor para VPN)
    ultimo_envio_posicion = 0

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

    try:
        print(f"Conectando a {uri}...")

        # Conectarse al servidor WebSocket
        async with websockets.connect(uri) as websocket:
            print("Conectado al servidor")

            # Enviar mensaje de tipo "join" para registrarse como jugador
            mensaje_join = {
                "tipo": "join",
                "nombre": nombre_jugador
            }
            await websocket.send(json.dumps(mensaje_join))
            print(f"Mensaje enviado: {mensaje_join}")

            # Loop principal: combina Pygame y WebSocket
            corriendo = True
            disparo_solicitado = False
            direccion_disparo = ultima_direccion_movimiento

            while corriendo:
                # Procesar eventos de Pygame (una sola vez)
                for evento in pygame.event.get():
                    if evento.type == pygame.QUIT:
                        corriendo = False
                    # Detectar disparo usando eventos KEYDOWN (más confiable)
                    elif evento.type == pygame.KEYDOWN:
                        # Disparo solo si estamos en juego
                        if (
                            (evento.key == pygame.K_SPACE or evento.key == pygame.K_j)
                            and puede_disparar
                            and player_id is not None
                            and en_juego
                            and not game_over
                        ):
                            disparo_solicitado = True
                            puede_disparar = False  # Bloquear nuevos disparos hasta que la bala desaparezca
                            # Usar la última dirección de movimiento
                            direccion_disparo = ultima_direccion_movimiento

                        # Marcar listo / no listo en la sala (tecla L)
                        if evento.key == pygame.K_l and player_id is not None and en_lobby:
                            yo_listo = not yo_listo
                            mensaje_ready = {
                                "tipo": "ready",
                                "player_id": player_id,
                                "listo": yo_listo
                            }
                            try:
                                await websocket.send(json.dumps(mensaje_ready))
                                print(f"📥 Enviado estado listo: {yo_listo}")
                            except Exception as e:
                                print(f"Error al enviar ready: {e}")

                # Obtener teclas presionadas para movimiento continuo
                teclas = pygame.key.get_pressed()

                movimiento_x = 0
                movimiento_y = 0

                # Solo permitir movimiento si estamos en juego
                if en_juego and not game_over:
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

                    # Actualizar posición
                    x += movimiento_x
                    y += movimiento_y

                    # Mantener el jugador dentro de los límites de la ventana
                    x = max(theme.TAMAÑO_CUADRADO // 2, min(ANCHO_VENTANA - theme.TAMAÑO_CUADRADO // 2, x))
                    y = max(theme.TAMAÑO_CUADRADO // 2, min(ALTO_VENTANA - theme.TAMAÑO_CUADRADO // 2, y))

                # Enviar mensaje de disparo al servidor
                if disparo_solicitado and player_id is not None:
                    mensaje_shoot = {
                        "tipo": "shoot",
                        "player_id": player_id,
                        "direccion": direccion_disparo
                    }
                    try:
                        await websocket.send(json.dumps(mensaje_shoot))
                        print(f"💥 Disparo enviado: {direccion_disparo}")
                        disparo_solicitado = False  # Resetear flag
                    except Exception as e:
                        print(f"Error al enviar disparo: {e}")
                        disparo_solicitado = False  # Resetear flag incluso si falla

                # Verificar si el jugador ya no tiene balas activas (puede volver a disparar)
                if not puede_disparar and player_id is not None:
                    # Verificar si hay balas del jugador en el estado
                    tiene_bala_activa = any(
                        int(bala_info.get("player_id", -1)) == player_id
                        for bala_info in estado_balas.values()
                    )

                    # Si no hay balas activas del jugador, permitir disparar de nuevo
                    if not tiene_bala_activa:
                        puede_disparar = True

                # Throttling: Solo enviar actualización de posición cada X ms (reduce tráfico de red)
                # Solo si estamos en juego
                if en_juego and not game_over:
                    tiempo_actual = time.time()
                    if (x, y) != posicion_anterior and player_id is not None:
                        if tiempo_actual - ultimo_envio_posicion >= INTERVALO_ACTUALIZACION_POS:
                            mensaje_posicion = {
                                "tipo": "update_pos",
                                "player_id": player_id,
                                "x": x,
                                "y": y
                            }
                            try:
                                await websocket.send(json.dumps(mensaje_posicion))
                                posicion_anterior = (x, y)
                                ultimo_envio_posicion = tiempo_actual
                            except Exception as e:
                                print(f"Error al enviar posición: {e}")

                # Revisar si hay mensajes del servidor (timeout corto para no bloquear el loop)
                try:
                    mensaje = await asyncio.wait_for(websocket.recv(), timeout=0.005)
                    try:
                        datos = json.loads(mensaje)
                        print(f"Mensaje recibido del servidor: {datos}")

                        # Procesar mensaje de asignación de ID
                        if datos.get("tipo") == "asignacion_id":
                            player_id = datos.get("player_id")
                            print(f"✅ Player ID asignado: {player_id}")

                            # Leer posición inicial enviada por el servidor
                            x = datos.get("x", x)
                            y = datos.get("y", y)
                            posicion_anterior = (x, y)
                            print(f"📍 Posición inicial asignada: ({x}, {y})")

                        # Procesar mensaje de estado del juego
                        elif datos.get("tipo") == "estado":
                            jugadores_recibidos_raw = datos.get("jugadores", {})

                            # Convertimos las llaves a int para que coincidan con player_id
                            jugadores_recibidos = {int(pid): pos for pid, pos in jugadores_recibidos_raw.items()}

                            # SOLO usar la posición del servidor para detectar respawn (diferencia grande)
                            # NO sobrescribir la posición local en cada tick - esto causa lag/rubber-banding
                            if player_id is not None and player_id in jugadores_recibidos:
                                pos_servidor = jugadores_recibidos[player_id]
                                servidor_x = pos_servidor["x"]
                                servidor_y = pos_servidor["y"]

                                # Calcular distancia entre posición local y servidor
                                dist_respawn = math.sqrt((x - servidor_x) ** 2 + (y - servidor_y) ** 2)

                                # Solo sincronizar si hay una diferencia grande (respawn o corrección del servidor)
                                if dist_respawn > 50:
                                    print(
                                        f"🔄 Respawn/corrección detectado! "
                                        f"Sincronizando posición: ({x}, {y}) -> ({servidor_x}, {servidor_y})"
                                    )
                                    x = servidor_x
                                    y = servidor_y
                                    posicion_anterior = (x, y)
                                    ultimo_envio_posicion = time.time()  # Resetear para evitar envío inmediato

                            # Otros jugadores: se dibujan con POSICIÓN DEL SERVER
                            # Remover explícitamente el jugador local del estado de otros jugadores
                            estado_jugadores = {}
                            for pid, pos in jugadores_recibidos.items():
                                # pid ya es int, así que la comparación es directa
                                if player_id is None or pid != player_id:
                                    estado_jugadores[pid] = pos

                            # Actualizar estado de balas (siempre, para que se vean incluso en lobby/game_over)
                            balas_recibidas = datos.get("balas", {})

                            # Detectar balas que desaparecieron (impacto)
                            balas_que_desaparecieron = []
                            for bala_id_ant in estado_balas_anterior.keys():
                                if bala_id_ant not in balas_recibidas:
                                    balas_que_desaparecieron.append(bala_id_ant)

                            estado_balas = balas_recibidas

                            # Actualizar puntuación (siempre, para mostrar en cualquier estado)
                            puntuacion_recibida = datos.get("puntuacion", {})
                            puntuacion_nueva = {
                                int(pid): score for pid, score in puntuacion_recibida.items()
                            }

                            # Detectar jugadores que fueron golpeados
                            tiempo_actual_impacto = time.time()
                            hubo_impacto = False

                            for pid, score_nuevo in puntuacion_nueva.items():
                                score_anterior = puntuacion_anterior.get(pid, 0)
                                if score_nuevo > score_anterior:
                                    hubo_impacto = True

                            # Si hubo un impacto y balas desaparecieron, activar efecto de daño
                            if hubo_impacto and balas_que_desaparecieron:
                                # Encontrar la posición de la última bala que desapareció
                                for bala_id_des in balas_que_desaparecieron:
                                    if bala_id_des in estado_balas_anterior:
                                        bala_pos = estado_balas_anterior[bala_id_des]
                                        bx = bala_pos.get("x", 0)
                                        by = bala_pos.get("y", 0)

                                        # Encontrar el jugador más cercano a donde estaba la bala
                                        jugador_mas_cercano = None
                                        distancia_minima = float("inf")

                                        # Revisar jugadores remotos
                                        for otro_pid, pos in estado_jugadores.items():
                                            jx = pos.get("x", 0)
                                            jy = pos.get("y", 0)
                                            dist = math.sqrt((bx - jx) ** 2 + (by - jy) ** 2)
                                            if dist < distancia_minima and dist < 50:  # Radio de impacto
                                                distancia_minima = dist
                                                jugador_mas_cercano = otro_pid

                                        # Revisar jugador local
                                        if player_id is not None:
                                            dist_local = math.sqrt((bx - x) ** 2 + (by - y) ** 2)
                                            if dist_local < distancia_minima and dist_local < 50:
                                                jugador_mas_cercano = player_id

                                        # Activar efecto de daño en el jugador golpeado
                                        if jugador_mas_cercano is not None:
                                            jugadores_danados[jugador_mas_cercano] = tiempo_actual_impacto
                                            print(
                                                f"💥 Jugador {jugador_mas_cercano} fue golpeado! "
                                                f"Mostrando imagen de daño"
                                            )

                            puntuacion = puntuacion_nueva
                            puntuacion_anterior = puntuacion_nueva.copy()

                            # Guardar estado anterior de balas para la próxima comparación
                            estado_balas_anterior = estado_balas.copy()

                            # Limpiar jugadores que ya no están en estado de daño (cada frame)
                            tiempo_limpieza = time.time()
                            jugadores_a_remover = [
                                pid for pid, tiempo_dano in list(jugadores_danados.items())
                                if tiempo_limpieza - tiempo_dano >= DURACION_DANO
                            ]
                            for pid in jugadores_a_remover:
                                del jugadores_danados[pid]

                        # Procesar mensaje de estado de sala
                        elif datos.get("tipo") == "estado_sala":
                            estado_sala = datos
                            # Actualizar estado de "listo" del jugador local
                            if player_id is not None:
                                jugadores_sala = datos.get("jugadores", {})
                                if str(player_id) in jugadores_sala:
                                    yo_listo = jugadores_sala[str(player_id)].get("listo", False)

                        # Procesar mensaje de inicio de partida
                        elif datos.get("tipo") == "start_game":
                            en_lobby = False
                            en_juego = True
                            game_over = False
                            print("🎮 ¡Comienza la partida!")

                            # Resetear flag de disparo
                            puede_disparar = True

                        # Procesar mensaje de game over
                        elif datos.get("tipo") == "game_over":
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
                    corriendo = False

                # DIBUJO – delegamos todo al módulo cowboy_theme
                if en_lobby:
                    theme.draw_lobby_screen(
                        pantalla,
                        ANCHO_VENTANA,
                        ALTO_VENTANA,
                        player_id,
                        yo_listo,
                        estado_sala
                    )

                elif game_over:
                    theme.draw_game_over_screen(
                        pantalla,
                        ANCHO_VENTANA,
                        ALTO_VENTANA,
                        ganador_id,
                        puntuacion
                    )

                else:
                    # Asegurarse de que el jugador local NO esté en estado_jugadores (limpieza final)
                    if player_id is not None and player_id in estado_jugadores:
                        del estado_jugadores[player_id]

                    # OJO: aquí asumo que tu theme.draw_game_screen acepta jugadores_danados.
                    # Si no, quita el último argumento.
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
                        jugadores_danados
                    )

                pygame.display.flip()
                reloj.tick(60)  # 60 FPS

    except websockets.exceptions.ConnectionClosed:
        print("Conexión cerrada por el servidor")
    except ConnectionRefusedError:
        print("Error: No se pudo conectar al servidor. ¿Está el servidor corriendo?")
    except Exception as e:
        print(f"Error en la conexión: {e}")
    finally:
        # Cerrar Pygame
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    try:
        asyncio.run(cliente())
    except KeyboardInterrupt:
        print("\nCliente detenido por el usuario")
        pygame.quit()
        sys.exit()
