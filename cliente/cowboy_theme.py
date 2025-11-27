# cowboy_theme.py
import pygame
import os
from typing import Dict, Any

# Tamaños compartidos con el cliente
TAMAÑO_CUADRADO = 60  # Tamaño de los jugadores (aumentado de 40 a 60)
TAMAÑO_BALA = 8

# Colores base
COLOR_JUGADOR_LOCAL = (0, 140, 255)   # Azul intenso
COLOR_JUGADOR_OTRO = (255, 140, 0)    # Naranja
COLOR_BALA = (255, 255, 0)            # Amarillo

# Diccionario para almacenar las imágenes de los jugadores (una sola vez)
# Clave: (imagen_num, tamaño) para permitir diferentes tamaños
_JUGADOR_IMAGES = {}
_JUGADOR_DANO_IMAGE = None  # Imagen de daño (compartida para todos)


def _load_jugador_image(player_id: int):
    """
    Carga la imagen del jugador según su ID.
    Jugador 1 -> jugador1.png, Jugador 2 -> jugador2.png, Jugador 3 -> jugador3.png
    Si hay más de 3 jugadores, rota entre las 3 imágenes.
    """
    global _JUGADOR_IMAGES
    
    # Determinar qué imagen usar (1, 2 o 3)
    imagen_num = ((player_id - 1) % 3) + 1
    
    # Clave que incluye el tamaño para permitir recargar si cambia
    clave = (imagen_num, TAMAÑO_CUADRADO)
    
    # Si ya está cargada con el tamaño correcto, devolverla
    if clave in _JUGADOR_IMAGES:
        return _JUGADOR_IMAGES[clave]
    
    # Cargar la imagen
    ruta_jugador = os.path.join(
        os.path.dirname(__file__), 
        "..", 
        "assets", 
        f"jugador{imagen_num}.png"
    )
    
    try:
        imagen = pygame.image.load(ruta_jugador).convert_alpha()
        # Escalar al tamaño del jugador
        imagen_escalada = pygame.transform.scale(
            imagen,
            (TAMAÑO_CUADRADO, TAMAÑO_CUADRADO)
        )
        # Guardar en el diccionario con la clave que incluye el tamaño
        _JUGADOR_IMAGES[clave] = imagen_escalada
        return imagen_escalada
    except Exception as e:
        print(f"Error al cargar imagen del jugador {imagen_num}: {e}")
        # Si falla, devolver None para usar fallback
        return None


def _load_jugador_dano_image():
    """Carga la imagen de daño (jugadorDaño.png)."""
    global _JUGADOR_DANO_IMAGE
    
    if _JUGADOR_DANO_IMAGE is None:
        ruta_dano = os.path.join(
            os.path.dirname(__file__),
            "..",
            "assets",
            "jugadorDaño.png"
        )
        try:
            imagen = pygame.image.load(ruta_dano).convert_alpha()
            _JUGADOR_DANO_IMAGE = pygame.transform.scale(
                imagen,
                (TAMAÑO_CUADRADO, TAMAÑO_CUADRADO)
            )
        except Exception as e:
            print(f"Error al cargar imagen de daño: {e}")
            _JUGADOR_DANO_IMAGE = None
    
    return _JUGADOR_DANO_IMAGE

# Paleta "Far West"
CIELO_SUPERIOR = (15, 10, 40)         # Azul oscuro
CIELO_INFERIOR = (255, 160, 90)       # Atardecer
COLOR_SUELO = (190, 140, 70)          # Arena
COLOR_MONTAÑA = (120, 80, 60)         # Montañas lejos
COLOR_CACTUS = (20, 120, 60)          # Verde cactus

# Inicializar fuentes
pygame.font.init()
FONT_TITULO = pygame.font.SysFont("bahnschrift", 42, bold=True)
FONT_SUBTITULO = pygame.font.SysFont("bahnschrift", 26, bold=True)
FONT_TEXTO = pygame.font.SysFont("bahnschrift", 22)
FONT_PEQUE = pygame.font.SysFont("bahnschrift", 18)


def _draw_vertical_gradient(surface, color_top, color_bottom):
    """Dibuja un gradiente vertical simple en toda la superficie."""
    width, height = surface.get_size()
    for y in range(height):
        t = y / height
        r = int(color_top[0] * (1 - t) + color_bottom[0] * t)
        g = int(color_top[1] * (1 - t) + color_bottom[1] * t)
        b = int(color_top[2] * (1 - t) + color_bottom[2] * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (width, y))


def _draw_background_cowboy(surface):
    """Fondo principal: cielo degradado, sol, montañas, desierto y cactus."""
    ancho, alto = surface.get_size()

    # Cielo degradado
    _draw_vertical_gradient(surface, CIELO_SUPERIOR, CIELO_INFERIOR)

    # Sol
    sol_x = int(ancho * 0.8)
    sol_y = int(alto * 0.25)
    pygame.draw.circle(surface, (255, 230, 150), (sol_x, sol_y), 45)

    # Montañas lejanas
    suelo_y = int(alto * 0.65)
    pygame.draw.polygon(surface, COLOR_MONTAÑA, [
        (int(ancho * 0.05), suelo_y),
        (int(ancho * 0.25), int(alto * 0.40)),
        (int(ancho * 0.45), suelo_y)
    ])
    pygame.draw.polygon(surface, COLOR_MONTAÑA, [
        (int(ancho * 0.35), suelo_y),
        (int(ancho * 0.6), int(alto * 0.35)),
        (int(ancho * 0.9), suelo_y)
    ])

    # Suelo del desierto
    pygame.draw.rect(surface, COLOR_SUELO, pygame.Rect(0, suelo_y, ancho, alto - suelo_y))

    # Tablas de madera (suelo tipo salón/camino)
    for i in range(0, ancho, 40):
        pygame.draw.rect(surface, (160, 110, 60),
                         pygame.Rect(i, suelo_y, 35, alto - suelo_y), width=0)

    # Cactus
    _draw_cactus(surface, int(ancho * 0.15), suelo_y)
    _draw_cactus(surface, int(ancho * 0.70), suelo_y)
    _draw_cactus(surface, int(ancho * 0.50), suelo_y + 20, scale=0.8)


def _draw_cactus(surface, x, suelo_y, scale=1.0):
    alto = int(80 * scale)
    ancho = int(20 * scale)

    # Tronco
    tronco = pygame.Rect(x - ancho // 2, suelo_y - alto, ancho, alto)
    pygame.draw.rect(surface, COLOR_CACTUS, tronco, border_radius=10)

    # Brazos
    brazo_altura = suelo_y - int(alto * 0.6)
    brazo_ancho = int(ancho * 0.7)
    brazo_alto = int(alto * 0.4)

    brazo_izq = pygame.Rect(x - ancho // 2 - brazo_ancho, brazo_altura, brazo_ancho, brazo_alto)
    brazo_der = pygame.Rect(x + ancho // 2, brazo_altura, brazo_ancho, brazo_alto)
    pygame.draw.rect(surface, COLOR_CACTUS, brazo_izq, border_radius=8)
    pygame.draw.rect(surface, COLOR_CACTUS, brazo_der, border_radius=8)


def _draw_panel(surface, x, y, w, h, alpha=190):
    """Panel semi-transparente para texto y marcadores."""
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((0, 0, 0, alpha))
    surface.blit(panel, (x, y))


# ------------------------------------------------------------
# PANTALLA DE LOBBY
# ------------------------------------------------------------
def draw_lobby_screen(
    pantalla,
    ancho: int,
    alto: int,
    player_id: int | None,
    yo_listo: bool,
    estado_sala: Dict[str, Any]
):
    _draw_background_cowboy(pantalla)

    # Panel central
    panel_width = int(ancho * 0.7)
    panel_height = int(alto * 0.6)
    panel_x = (ancho - panel_width) // 2
    panel_y = (alto - panel_height) // 2
    _draw_panel(pantalla, panel_x, panel_y, panel_width, panel_height, alpha=200)

    # Título
    titulo = FONT_TITULO.render("Cowboy Battle - Lobby", True, (255, 230, 180))
    pantalla.blit(titulo, (panel_x + 20, panel_y + 15))

    # Estado de jugadores
    jugadores = estado_sala.get("jugadores", {})
    y_text = panel_y + 70

    if not jugadores:
        texto = FONT_TEXTO.render("Esperando jugadores que se conecten...", True, (255, 255, 255))
        pantalla.blit(texto, (panel_x + 20, y_text))
        y_text += 30
    else:
        encabezado = FONT_SUBTITULO.render("Jugadores en la sala:", True, (255, 255, 255))
        pantalla.blit(encabezado, (panel_x + 20, y_text))
        y_text += 35

        for pid_str, info in jugadores.items():
            nombre = info.get("nombre", f"Jugador {pid_str}")
            listo = info.get("listo", False)

            if player_id is not None and int(pid_str) == player_id:
                color_nombre = (0, 230, 255)  # Resaltar jugador local
                etiqueta = "(Tú)"
            else:
                color_nombre = (255, 255, 255)
                etiqueta = ""

            texto_jugador = FONT_TEXTO.render(
                f"{nombre} {etiqueta} - {'LISTO' if listo else 'No listo'}",
                True,
                color_nombre
            )
            pantalla.blit(texto_jugador, (panel_x + 40, y_text))
            y_text += 28

    # Instrucciones
    y_text = panel_y + panel_height - 90
    instr1 = FONT_TEXTO.render("Pulsa L para cambiar tu estado de listo.", True, (255, 255, 255))
    instr2 = FONT_TEXTO.render("El juego inicia cuando todos estén listos.", True, (255, 255, 255))
    pantalla.blit(instr1, (panel_x + 20, y_text))
    pantalla.blit(instr2, (panel_x + 20, y_text + 28))

    # Indicador de si tú estás listo
    estado_txt = "LISTO" if yo_listo else "No listo"
    color_estado = (0, 255, 120) if yo_listo else (255, 120, 120)
    texto_estado = FONT_SUBTITULO.render(f"Tu estado: {estado_txt}", True, color_estado)
    pantalla.blit(texto_estado, (panel_x + panel_width - 280, panel_y + 20))


# ------------------------------------------------------------
# PANTALLA DE JUEGO
# ------------------------------------------------------------
def draw_game_screen(
    pantalla,
    ancho: int,
    alto: int,
    player_id: int | None,
    estado_jugadores: Dict[int, Dict[str, float]],
    x_local: float,
    y_local: float,
    estado_balas: Dict[str, Dict[str, float]],
    puntuacion: Dict[int, int],
    jugadores_danados: Dict[int, float] = None
):
    _draw_background_cowboy(pantalla)

    # ❌ Sin cuadro/salón central, solo fondo western.

    # Dibujar balas
    for bala_id, info in estado_balas.items():
        bx = int(info.get("x", 0))
        by = int(info.get("y", 0))
        pygame.draw.circle(pantalla, COLOR_BALA, (bx, by), TAMAÑO_BALA // 2)

    # Cargar imagen de daño
    dano_img = _load_jugador_dano_image()
    if jugadores_danados is None:
        jugadores_danados = {}
    
    # Jugadores remotos
    for pid, pos in estado_jugadores.items():
        jx = int(pos.get("x", 0))
        jy = int(pos.get("y", 0))
        
        # Verificar si el jugador está en estado de daño
        esta_danado = pid in jugadores_danados
        
        # Elegir qué imagen mostrar (daño o normal)
        if esta_danado and dano_img:
            imagen_a_dibujar = dano_img
        else:
            imagen_a_dibujar = _load_jugador_image(pid)
        
        # Dibujar imagen del jugador o rectángulo como fallback
        if imagen_a_dibujar:
            rect_jugador = imagen_a_dibujar.get_rect()
            rect_jugador.center = (jx, jy)
            pantalla.blit(imagen_a_dibujar, rect_jugador)
        else:
            # Fallback: rectángulo si no se pudo cargar la imagen
            rect = pygame.Rect(0, 0, TAMAÑO_CUADRADO, TAMAÑO_CUADRADO)
            rect.center = (jx, jy)
            pygame.draw.rect(pantalla, COLOR_JUGADOR_OTRO, rect, border_radius=5)

        # Label encima
        nick = f"P{pid}"
        label = FONT_PEQUE.render(nick, True, (255, 255, 255))
        pantalla.blit(label, (jx - label.get_width() // 2, jy - TAMAÑO_CUADRADO // 2 - 18))

    # Jugador local
    if player_id is not None:
        x_local_int = int(x_local)
        y_local_int = int(y_local)
        
        # Verificar si el jugador local está en estado de daño
        esta_danado_local = player_id in jugadores_danados
        
        # Elegir qué imagen mostrar (daño o normal)
        if esta_danado_local and dano_img:
            imagen_a_dibujar_local = dano_img
        else:
            imagen_a_dibujar_local = _load_jugador_image(player_id)
        
        # Dibujar imagen del jugador o rectángulo como fallback
        if imagen_a_dibujar_local:
            rect_jugador_local = imagen_a_dibujar_local.get_rect()
            rect_jugador_local.center = (x_local_int, y_local_int)
            pantalla.blit(imagen_a_dibujar_local, rect_jugador_local)
        else:
            # Fallback: rectángulo si no se pudo cargar la imagen
            rect_local = pygame.Rect(0, 0, TAMAÑO_CUADRADO, TAMAÑO_CUADRADO)
            rect_local.center = (x_local_int, y_local_int)
            pygame.draw.rect(pantalla, COLOR_JUGADOR_LOCAL, rect_local, border_radius=8)
        
        label_local = FONT_PEQUE.render("Tú", True, (255, 255, 255))
        pantalla.blit(label_local, (x_local_int - label_local.get_width() // 2,
                                    y_local_int - TAMAÑO_CUADRADO // 2 - 18))

    # Marcador
    _draw_scoreboard(pantalla, ancho, puntuacion, player_id)


def _draw_scoreboard(pantalla, ancho: int, puntuacion: Dict[int, int], player_id: int | None):
    if not puntuacion:
        return

    panel_width = 240
    panel_height = 20 + 28 * (len(puntuacion) + 1)
    panel_x = 15
    panel_y = 15

    _draw_panel(pantalla, panel_x, panel_y, panel_width, panel_height, alpha=180)

    titulo = FONT_SUBTITULO.render("Marcador", True, (255, 230, 180))
    pantalla.blit(titulo, (panel_x + 10, panel_y + 5))

    y = panel_y + 35
    for pid, score in sorted(puntuacion.items(), key=lambda kv: kv[1], reverse=True):
        es_local = (player_id is not None and pid == player_id)
        color = (0, 255, 140) if es_local else (255, 255, 255)
        texto = FONT_TEXTO.render(f"P{pid}: {score}", True, color)
        pantalla.blit(texto, (panel_x + 15, y))
        y += 25


# ------------------------------------------------------------
# PANTALLA DE GAME OVER
# ------------------------------------------------------------
def draw_game_over_screen(
    pantalla,
    ancho: int,
    alto: int,
    ganador_id: int | None,
    puntuacion: Dict[int, int]
):
    _draw_background_cowboy(pantalla)

    panel_width = int(ancho * 0.6)
    panel_height = int(alto * 0.5)
    panel_x = (ancho - panel_width) // 2
    panel_y = (alto - panel_height) // 2
    _draw_panel(pantalla, panel_x, panel_y, panel_width, panel_height, alpha=220)

    # Título
    titulo = FONT_TITULO.render("¡Duelo finalizado!", True, (255, 230, 180))
    pantalla.blit(titulo, (panel_x + (panel_width - titulo.get_width()) // 2, panel_y + 20))

    # Ganador
    if ganador_id is not None:
        texto_ganador = FONT_SUBTITULO.render(
            f"Ganador: P{ganador_id}",
            True,
            (0, 255, 140)
        )
    else:
        texto_ganador = FONT_SUBTITULO.render(
            "Empate o sin ganador",
            True,
            (255, 255, 255)
        )

    pantalla.blit(
        texto_ganador,
        (panel_x + (panel_width - texto_ganador.get_width()) // 2, panel_y + 80)
    )

    # Marcador final
    y = panel_y + 130
    encabezado = FONT_SUBTITULO.render("Marcador final:", True, (255, 255, 255))
    pantalla.blit(encabezado, (panel_x + 30, y))
    y += 35

    for pid, score in sorted(puntuacion.items(), key=lambda kv: kv[1], reverse=True):
        linea = FONT_TEXTO.render(f"P{pid}: {score}", True, (255, 255, 255))
        pantalla.blit(linea, (panel_x + 40, y))
        y += 26

    # Instrucciones
    texto_instr = FONT_TEXTO.render("Cierra la ventana para salir.", True, (255, 255, 255))
    pantalla.blit(
        texto_instr,
        (panel_x + (panel_width - texto_instr.get_width()) // 2,
         panel_y + panel_height - 50)
    )