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

# Configuración de Pygame
ANCHO_VENTANA = 800
ALTO_VENTANA = 600
VELOCIDAD_MOVIMIENTO = 5
COLOR_JUGADOR_LOCAL = (0, 100, 255)  # Azul para el jugador local
COLOR_JUGADOR_OTRO = (255, 100, 0)  # Naranja para otros jugadores
COLOR_FONDO = (50, 50, 50)  # Gris oscuro
COLOR_BALA = (255, 255, 0)  # Amarillo para las balas
TAMAÑO_CUADRADO = 40
TAMAÑO_BALA = 8


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
    
    # Puntuación recibida del servidor
    # Clave: player_id, Valor: cantidad de impactos
    puntuacion: Dict[int, int] = {}
    
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
                        if (evento.key == pygame.K_SPACE or evento.key == pygame.K_j) and puede_disparar and player_id is not None and en_juego and not game_over:
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
                    x = max(TAMAÑO_CUADRADO // 2, min(ANCHO_VENTANA - TAMAÑO_CUADRADO // 2, x))
                    y = max(TAMAÑO_CUADRADO // 2, min(ALTO_VENTANA - TAMAÑO_CUADRADO // 2, y))
                
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
                            
                            # 👇 Convertimos las llaves a int para que coincidan con player_id
                            jugadores_recibidos = {int(pid): pos for pid, pos in jugadores_recibidos_raw.items()}
                            
                            # 🔹 SOLO usar la posición del servidor para detectar respawn (diferencia grande)
                            # NO sobrescribir la posición local en cada tick - esto causa lag/rubber-banding
                            if player_id is not None and player_id in jugadores_recibidos:
                                pos_servidor = jugadores_recibidos[player_id]
                                servidor_x = pos_servidor["x"]
                                servidor_y = pos_servidor["y"]
                                
                                # Calcular distancia entre posición local y servidor
                                dist_respawn = math.sqrt((x - servidor_x) ** 2 + (y - servidor_y) ** 2)
                                
                                # Solo sincronizar si hay una diferencia grande (respawn o corrección del servidor)
                                if dist_respawn > 50:
                                    print(f"🔄 Respawn/corrección detectado! Sincronizando posición: ({x}, {y}) -> ({servidor_x}, {servidor_y})")
                                    x = servidor_x
                                    y = servidor_y
                                    posicion_anterior = (x, y)
                                    ultimo_envio_posicion = time.time()  # Resetear para evitar envío inmediato
                            
                            # 🔹 Otros jugadores: se dibujan con POSICIÓN DEL SERVER
                            # Remover explícitamente el jugador local del estado de otros jugadores
                            estado_jugadores = {}
                            for pid, pos in jugadores_recibidos.items():
                                # Comparación estricta para asegurar que nunca incluimos al jugador local
                                # pid ya es int, así que la comparación es directa
                                if player_id is None or pid != player_id:
                                    estado_jugadores[pid] = pos
                            
                            # Actualizar estado de balas (siempre, para que se vean incluso en lobby/game_over)
                            balas_recibidas = datos.get("balas", {})
                            estado_balas = balas_recibidas
                            
                            # Actualizar puntuación (siempre, para mostrar en cualquier estado)
                            puntuacion_recibida = datos.get("puntuacion", {})
                            puntuacion = {int(pid): score for pid, score in puntuacion_recibida.items()}
                        
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
                            
                            # La posición se sincronizará automáticamente cuando llegue el primer mensaje "estado"
                            # con la posición inicial del servidor (si hay diferencia > 50)
                        
                        # Procesar mensaje de game over
                        elif datos.get("tipo") == "game_over":
                            game_over = True
                            en_juego = False
                            ganador_id = datos.get("ganador")
                            puntuacion_recibida = datos.get("puntuacion", {})
                            puntuacion = {int(pid): score for pid, score in puntuacion_recibida.items()}
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
                
                # Dibujar en la pantalla según el estado del juego
                pantalla.fill(COLOR_FONDO)
                fuente = pygame.font.Font(None, 32)
                fuente_pequeña = pygame.font.Font(None, 24)
                
                if en_lobby:
                    # Pantalla de sala
                    texto = fuente.render("Sala de inicio - Presiona L para marcar 'Listo'", True, (255, 255, 255))
                    pantalla.blit(texto, (50, 50))
                    
                    if player_id is not None:
                        texto_id = fuente.render(f"Tu ID: {player_id} - {'LISTO' if yo_listo else 'NO LISTO'}", True, (255, 255, 0))
                        pantalla.blit(texto_id, (50, 100))
                    
                    # Mostrar info de otros jugadores en estado_sala
                    jugadores_sala = estado_sala.get("jugadores", {}) if isinstance(estado_sala, dict) else {}
                    offset_y = 150
                    for pid_str, info in jugadores_sala.items():
                        pid = int(pid_str)
                        if pid != player_id:
                            estado_l = "LISTO" if info.get("listo") else "NO LISTO"
                            color_l = (0, 255, 0) if info.get("listo") else (200, 200, 200)
                            linea = fuente_pequeña.render(f"Jugador {pid} ({info.get('nombre', '')}): {estado_l}", True, color_l)
                            pantalla.blit(linea, (50, offset_y))
                            offset_y += 30
                
                elif game_over:
                    # Pantalla de game over
                    texto = fuente.render(f"Game Over - Ganador: Jugador {ganador_id}", True, (255, 255, 255))
                    pantalla.blit(texto, (50, 50))
                    
                    offset_y = 100
                    for pid, score in sorted(puntuacion.items()):
                        linea = fuente_pequeña.render(f"Jugador {pid}: {score} impactos", True, (255, 255, 0))
                        pantalla.blit(linea, (50, offset_y))
                        offset_y += 30
                
                else:
                    # Pantalla de juego normal
                    # Asegurarse de que el jugador local NO esté en estado_jugadores (limpieza final)
                    if player_id is not None and player_id in estado_jugadores:
                        del estado_jugadores[player_id]
                    
                    # PRIMERO: Dibujar solo los otros jugadores del estado (nunca el jugador local)
                    for otro_player_id, posicion_otro in estado_jugadores.items():
                        otro_x = posicion_otro["x"]
                        otro_y = posicion_otro["y"]
                        
                        rectangulo = pygame.Rect(
                            otro_x - TAMAÑO_CUADRADO // 2,
                            otro_y - TAMAÑO_CUADRADO // 2,
                            TAMAÑO_CUADRADO,
                            TAMAÑO_CUADRADO
                        )
                        pygame.draw.rect(pantalla, COLOR_JUGADOR_OTRO, rectangulo)
                    
                    # SEGUNDO: Dibujar el jugador local ÚNICAMENTE con su posición local (una sola vez)
                    if player_id is not None:
                        rectangulo_local = pygame.Rect(
                            x - TAMAÑO_CUADRADO // 2,
                            y - TAMAÑO_CUADRADO // 2,
                            TAMAÑO_CUADRADO,
                            TAMAÑO_CUADRADO
                        )
                        pygame.draw.rect(pantalla, COLOR_JUGADOR_LOCAL, rectangulo_local)
                    
                    # TERCERO: Dibujar todas las balas
                    for bala_id, bala_pos in estado_balas.items():
                        bala_x = bala_pos["x"]
                        bala_y = bala_pos["y"]
                        
                        # Dibujar bala como un círculo pequeño
                        pygame.draw.circle(
                            pantalla,
                            COLOR_BALA,
                            (int(bala_x), int(bala_y)),
                            TAMAÑO_BALA // 2
                        )
                    
                    # Mostrar información en la pantalla
                    if player_id:
                        texto_id = fuente_pequeña.render(f"Player ID: {player_id}", True, (255, 255, 255))
                        pantalla.blit(texto_id, (10, 10))
                    
                    # Mostrar puntuación
                    offset_y = 40
                    for pid, score in sorted(puntuacion.items()):
                        texto_score = fuente_pequeña.render(f"Jugador {pid}: {score} impactos", True, (255, 255, 0))
                        pantalla.blit(texto_score, (10, offset_y))
                        offset_y += 25
                
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
