import asyncio
import json
import websockets
import pygame
import sys
import math
from typing import Dict

# Configuración de Pygame
ANCHO_VENTANA = 800
ALTO_VENTANA = 600
VELOCIDAD_MOVIMIENTO = 5
COLOR_JUGADOR_LOCAL = (0, 100, 255)
COLOR_JUGADOR_OTRO = (255, 100, 0)
COLOR_FONDO = (50, 50, 50)
COLOR_BALA = (255, 255, 0)
TAMAÑO_CUADRADO = 40
TAMAÑO_BALA = 8

async def cliente():
    uri = "ws://localhost:9000"
    nombre_jugador = "Fabi"
    player_id = None

    estado_jugadores: Dict[int, Dict[str, float]] = {}
    estado_balas: Dict[str, Dict[str, float]] = {}
    puntuacion: Dict[int, int] = {}

    puede_disparar = True
    tecla_disparo_presionada_anterior = False

    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO_VENTANA, ALTO_VENTANA))
    pygame.display.set_caption("Cowboy Battle - Cliente")
    reloj = pygame.time.Clock()

    x = ANCHO_VENTANA // 2
    y = ALTO_VENTANA // 2
    posicion_anterior = (x, y)

    try:
        print(f"Conectando a {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Conectado al servidor")

            mensaje_join = {"tipo": "join", "nombre": nombre_jugador}
            await websocket.send(json.dumps(mensaje_join))
            print(f"Mensaje enviado: {mensaje_join}")

            corriendo = True
            while corriendo:
                for evento in pygame.event.get():
                    if evento.type == pygame.QUIT:
                        corriendo = False

                teclas = pygame.key.get_pressed()
                movimiento_x = 0
                movimiento_y = 0

                if teclas[pygame.K_w] or teclas[pygame.K_UP]:
                    movimiento_y = -VELOCIDAD_MOVIMIENTO
                if teclas[pygame.K_s] or teclas[pygame.K_DOWN]:
                    movimiento_y = VELOCIDAD_MOVIMIENTO
                if teclas[pygame.K_a] or teclas[pygame.K_LEFT]:
                    movimiento_x = -VELOCIDAD_MOVIMIENTO
                if teclas[pygame.K_d] or teclas[pygame.K_RIGHT]:
                    movimiento_x = VELOCIDAD_MOVIMIENTO

                x += movimiento_x
                y += movimiento_y

                x = max(TAMAÑO_CUADRADO // 2, min(ANCHO_VENTANA - TAMAÑO_CUADRADO // 2, x))
                y = max(TAMAÑO_CUADRADO // 2, min(ALTO_VENTANA - TAMAÑO_CUADRADO // 2, y))

                tecla_disparo_actual = teclas[pygame.K_SPACE] or teclas[pygame.K_j]
                disparo_solicitado = False
                direccion_disparo = "up"

                if tecla_disparo_actual and not tecla_disparo_presionada_anterior and puede_disparar and player_id is not None:
                    disparo_solicitado = True
                    puede_disparar = False

                    if teclas[pygame.K_w] or teclas[pygame.K_UP]:
                        direccion_disparo = "up"
                    elif teclas[pygame.K_s] or teclas[pygame.K_DOWN]:
                        direccion_disparo = "down"
                    elif teclas[pygame.K_a] or teclas[pygame.K_LEFT]:
                        direccion_disparo = "left"
                    elif teclas[pygame.K_d] or teclas[pygame.K_RIGHT]:
                        direccion_disparo = "right"

                tecla_disparo_presionada_anterior = tecla_disparo_actual

                if disparo_solicitado and player_id is not None:
                    mensaje_shoot = {"tipo": "shoot", "player_id": player_id, "direccion": direccion_disparo}
                    try:
                        await websocket.send(json.dumps(mensaje_shoot))
                    except Exception as e:
                        print(f"Error al enviar disparo: {e}")

                if not puede_disparar and player_id is not None:
                    tiene_bala_activa = any(
                        int(bala_info.get("player_id", -1)) == player_id
                        for bala_info in estado_balas.values()
                    )
                    if not tiene_bala_activa:
                        puede_disparar = True

                if (x, y) != posicion_anterior and player_id is not None:
                    mensaje_posicion = {"tipo": "update_pos", "player_id": player_id, "x": x, "y": y}
                    try:
                        await websocket.send(json.dumps(mensaje_posicion))
                        posicion_anterior = (x, y)
                    except Exception as e:
                        print(f"Error al enviar posición: {e}")

                try:
                    mensaje = await asyncio.wait_for(websocket.recv(), timeout=0.001)
                    try:
                        datos = json.loads(mensaje)
                        print(f"Mensaje recibido: {datos}")

                        if datos.get("tipo") == "asignacion_id":
                            player_id = datos.get("player_id")
                            print(f"Player ID asignado: {player_id}")

                            x = datos.get("x", x)
                            y = datos.get("y", y)
                            posicion_anterior = (x, y)

                        elif datos.get("tipo") == "estado":
                            jugadores_recibidos = datos.get("jugadores", {})

                            if player_id is not None and player_id in jugadores_recibidos:
                                servidor_x = jugadores_recibidos[player_id]["x"]
                                servidor_y = jugadores_recibidos[player_id]["y"]
                                dist = math.hypot(x - servidor_x, y - servidor_y)

                                if dist > 50:
                                    x = servidor_x
                                    y = servidor_y
                                    posicion_anterior = (x, y)

                            estado_jugadores = {}
                            for pid, pos in jugadores_recibidos.items():
                                if player_id is None or int(pid) != int(player_id):
                                    estado_jugadores[pid] = pos

                            estado_balas = datos.get("balas", {})
                            puntuacion = {int(pid): score for pid, score in datos.get("puntuacion", {}).items()}

                    except json.JSONDecodeError:
                        print("Mensaje no JSON")
                    except Exception as e:
                        print(f"Error procesando mensaje: {e}")

                except asyncio.TimeoutError:
                    pass
                except websockets.exceptions.ConnectionClosed:
                    print("Conexión cerrada")
                    corriendo = False

                pantalla.fill(COLOR_FONDO)

                if player_id in estado_jugadores:
                    del estado_jugadores[player_id]

                for otro_id, pos in estado_jugadores.items():
                    if int(otro_id) != int(player_id):
                        pygame.draw.rect(pantalla, COLOR_JUGADOR_OTRO,
                            pygame.Rect(pos["x"] - TAMAÑO_CUADRADO // 2,
                                        pos["y"] - TAMAÑO_CUADRADO // 2,
                                        TAMAÑO_CUADRADO, TAMAÑO_CUADRADO))

                if player_id is not None:
                    pygame.draw.rect(pantalla, COLOR_JUGADOR_LOCAL,
                        pygame.Rect(x - TAMAÑO_CUADRADO // 2,
                                    y - TAMAÑO_CUADRADO // 2,
                                    TAMAÑO_CUADRADO, TAMAÑO_CUADRADO))

                for bala_id, bala_pos in estado_balas.items():
                    pygame.draw.circle(pantalla, COLOR_BALA,
                        (int(bala_pos["x"]), int(bala_pos["y"])),
                        TAMAÑO_BALA // 2)

                fuente = pygame.font.Font(None, 24)
                if player_id:
                    pantalla.blit(fuente.render(f"Player ID: {player_id}", True, (255,255,255)), (10,10))
                pantalla.blit(fuente.render(f"Posición: ({x}, {y})", True, (255,255,255)), (10,40))

                total_jugadores = len(estado_jugadores) + 1
                pantalla.blit(fuente.render(f"Jugadores conectados: {total_jugadores}", True, (255,255,255)), (10,70))

                y_offset = 100
                for pid, score in sorted(puntuacion.items()):
                    pantalla.blit(fuente.render(f"Jugador {pid}: {score} impactos", True, (255,255,0)), (10, y_offset))
                    y_offset += 25

                pygame.display.flip()
                reloj.tick(60)

    except ConnectionRefusedError:
        print("No se pudo conectar al servidor.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    try:
        asyncio.run(cliente())
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit()
