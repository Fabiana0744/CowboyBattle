import pygame
import os
import math
from typing import Dict, Any, List

# Tamaños compartidos con el cliente
TAMAÑO_CUADRADO = 60  # Tamaño de los jugadores
TAMAÑO_BALA = 8

# Tamaño del barril (más alto que ancho, como en la imagen)
BARRIL_ANCHO = 55
BARRIL_ALTO = 85

# Tamaño del cactus (más alto que ancho, rectangular)
CACTUS_ANCHO = 50
CACTUS_ALTO = 80

# Colores base
COLOR_JUGADOR_LOCAL = (0, 140, 255)   # Azul intenso
COLOR_JUGADOR_OTRO = (255, 140, 0)    # Naranja
COLOR_BALA = (255, 255, 0)            # Amarillo

# Diccionarios de imágenes en caché
# Clave: (imagen_num, tamaño)
_JUGADOR_IMAGES: Dict[tuple, pygame.Surface] = {}
_JUGADOR_DANO_IMAGE: pygame.Surface | None = None
_BARRIL_IMAGES: Dict[tuple, pygame.Surface] = {}
_CACTUS_IMAGE: pygame.Surface | None = None

# Mapeo tipo -> archivo de sprite del barril
# Asegúrate de tener estos archivos en: proyecto/assets/barril1.png, barril2.png
_BARRIL_SPRITES = {
    "barril_marron": "barril2.png",   # el más oscuro
    "barril_naranja": "barril1.png",  # el más anaranjado
}

# Lista de obstáculos fijos del mapa
# Puedes cambiar posiciones y cantidad a tu gusto
OBSTACULOS = [
    {"tipo": "barril_marron", "x": 400, "y": 300},
    {"tipo": "barril_naranja", "x": 260, "y": 210},
    {"tipo": "barril_marron", "x": 540, "y": 210},
    {"tipo": "cactus", "x": 150, "y": 150},
    {"tipo": "cactus", "x": 650, "y": 450},
    {"tipo": "cactus", "x": 400, "y": 100},
]

# Paleta "Far West"
CIELO_SUPERIOR = (15, 10, 40)         # Azul oscuro
CIELO_INFERIOR = (255, 160, 90)       # Atardecer
COLOR_SUELO = (190, 140, 70)          # Arena
COLOR_MONTAÑA = (120, 80, 60)         # Montañas lejos
COLOR_CACTUS = (20, 120, 60)          # Verde cactus

# Paleta para fondo de arena pixel art (rayas diagonales)
ARENA_CLARA = (255, 240, 180)         # Amarillo claro/sol
ARENA_MEDIA = (240, 200, 120)         # Amarillo dorado
ARENA_OSCURA = (220, 180, 100)        # Dorado oscuro/mostaza

# Tile global para el fondo de arena (se crea una vez)
_ARENA_TILE: pygame.Surface | None = None

# Inicializar fuentes
pygame.font.init()
FONT_TITULO = pygame.font.SysFont("bahnschrift", 42, bold=True)
FONT_SUBTITULO = pygame.font.SysFont("bahnschrift", 26, bold=True)
FONT_TEXTO = pygame.font.SysFont("bahnschrift", 22)
FONT_PEQUE = pygame.font.SysFont("bahnschrift", 18)

# ------------------------------------------------------------
# Carga de sprites
# ------------------------------------------------------------

def _load_jugador_image(player_id: int):
    """
    Carga la imagen del jugador según su ID.
    Jugador 1 -> jugador1.png, Jugador 2 -> jugador2.png, Jugador 3 -> jugador3.png
    Si hay más de 3 jugadores, rota entre las 3 imágenes.
    """
    global _JUGADOR_IMAGES

    imagen_num = ((player_id - 1) % 3) + 1
    clave = (imagen_num, TAMAÑO_CUADRADO)

    if clave in _JUGADOR_IMAGES:
        return _JUGADOR_IMAGES[clave]

    ruta_jugador = os.path.join(
        os.path.dirname(__file__),
        "..",
        "assets",
        f"jugador{imagen_num}.png"
    )

    try:
        imagen = pygame.image.load(ruta_jugador).convert_alpha()
        imagen_escalada = pygame.transform.scale(
            imagen,
            (TAMAÑO_CUADRADO, TAMAÑO_CUADRADO)
        )
        _JUGADOR_IMAGES[clave] = imagen_escalada
        return imagen_escalada
    except Exception as e:
        print(f"Error al cargar imagen del jugador {imagen_num}: {e}")
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


def _load_barrel_image(tipo: str) -> pygame.Surface | None:
    """Carga la imagen del barril y la escala a un rectángulo alto (BARRIL_ANCHO x BARRIL_ALTO)."""
    global _BARRIL_IMAGES

    archivo = _BARRIL_SPRITES.get(tipo, "barril1.png")
    clave = (archivo, BARRIL_ANCHO, BARRIL_ALTO)

    if clave in _BARRIL_IMAGES:
        return _BARRIL_IMAGES[clave]

    ruta_barril = os.path.join(
        os.path.dirname(__file__),
        "..",
        "assets",
        archivo
    )

    try:
        imagen = pygame.image.load(ruta_barril).convert_alpha()
        imagen_escalada = pygame.transform.scale(
            imagen,
            (BARRIL_ANCHO, BARRIL_ALTO)
        )
        _BARRIL_IMAGES[clave] = imagen_escalada
        return imagen_escalada
    except Exception as e:
        print(f"Error al cargar barril '{archivo}': {e}")
        return None


def _load_cactus_image() -> pygame.Surface | None:
    """Carga la imagen del cactus y la escala a un rectángulo alto (CACTUS_ANCHO x CACTUS_ALTO)."""
    global _CACTUS_IMAGE

    if _CACTUS_IMAGE is None:
        ruta_cactus = os.path.join(
            os.path.dirname(__file__),
            "..",
            "assets",
            "cactus.png"
        )
        try:
            imagen = pygame.image.load(ruta_cactus).convert_alpha()
            _CACTUS_IMAGE = pygame.transform.scale(
                imagen,
                (CACTUS_ANCHO, CACTUS_ALTO)
            )
        except Exception as e:
            print(f"Error al cargar cactus: {e}")
            _CACTUS_IMAGE = None

    return _CACTUS_IMAGE

# ------------------------------------------------------------
# Fondo
# ------------------------------------------------------------

def _draw_vertical_gradient(surface, color_top, color_bottom):
    width, height = surface.get_size()
    for y in range(height):
        t = y / height
        r = int(color_top[0] * (1 - t) + color_bottom[0] * t)
        g = int(color_top[1] * (1 - t) + color_bottom[1] * t)
        b = int(color_top[2] * (1 - t) + color_bottom[2] * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (width, y))


def _draw_background_cowboy(surface):
    ancho, alto = surface.get_size()

    _draw_vertical_gradient(surface, CIELO_SUPERIOR, CIELO_INFERIOR)

    sol_x = int(ancho * 0.8)
    sol_y = int(alto * 0.25)
    pygame.draw.circle(surface, (255, 230, 150), (sol_x, sol_y), 45)

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

    pygame.draw.rect(surface, COLOR_SUELO, pygame.Rect(0, suelo_y, ancho, alto - suelo_y))

    for i in range(0, ancho, 40):
        pygame.draw.rect(surface, (160, 110, 60),
                         pygame.Rect(i, suelo_y, 35, alto - suelo_y), width=0)

    _draw_cactus(surface, int(ancho * 0.15), suelo_y)
    _draw_cactus(surface, int(ancho * 0.70), suelo_y)
    _draw_cactus(surface, int(ancho * 0.50), suelo_y + 20, scale=0.8)


def _draw_cactus(surface, x, suelo_y, scale=1.0):
    alto = int(80 * scale)
    ancho = int(20 * scale)

    tronco = pygame.Rect(x - ancho // 2, suelo_y - alto, ancho, alto)
    pygame.draw.rect(surface, COLOR_CACTUS, tronco, border_radius=10)

    brazo_altura = suelo_y - int(alto * 0.6)
    brazo_ancho = int(ancho * 0.7)
    brazo_alto = int(alto * 0.4)

    brazo_izq = pygame.Rect(x - ancho // 2 - brazo_ancho, brazo_altura, brazo_ancho, brazo_alto)
    brazo_der = pygame.Rect(x + ancho // 2, brazo_altura, brazo_ancho, brazo_alto)
    pygame.draw.rect(surface, COLOR_CACTUS, brazo_izq, border_radius=8)
    pygame.draw.rect(surface, COLOR_CACTUS, brazo_der, border_radius=8)


def _draw_panel(surface, x, y, w, h, alpha=190):
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((0, 0, 0, alpha))
    surface.blit(panel, (x, y))


def _crear_tile_arena_pixelart(size: int = 32) -> pygame.Surface:
    tile = pygame.Surface((size, size))

    for y in range(size):
        for x in range(size):
            diagonal = (x + 2 * y) % (size // 2)
            onda = int(2 * math.sin((x + y) * 0.4))
            patron = (diagonal + onda) % 10

            if patron < 3:
                color = ARENA_CLARA
            elif patron < 7:
                color = ARENA_MEDIA
            else:
                color = ARENA_OSCURA

            tile.set_at((x, y), color)

    return tile.convert()


def _draw_arena_background(surface):
    global _ARENA_TILE
    if _ARENA_TILE is None:
        _ARENA_TILE = _crear_tile_arena_pixelart(32)

    ancho, alto = surface.get_size()
    tw, th = _ARENA_TILE.get_size()

    for y in range(0, alto, th):
        for x in range(0, ancho, tw):
            surface.blit(_ARENA_TILE, (x, y))


# ------------------------------------------------------------
# Obstáculos (barriles)
# ------------------------------------------------------------

def _draw_obstaculos(pantalla: pygame.Surface):
    """Dibuja los obstáculos (barriles y cactus) en sus posiciones."""
    for obs in OBSTACULOS:
        tipo = obs["tipo"]
        x, y = obs["x"], obs["y"]
        
        if tipo == "cactus":
            img = _load_cactus_image()
            if img:
                rect = img.get_rect()
                rect.center = (x, y)
                pantalla.blit(img, rect)
            else:
                # Fallback si no se puede cargar la imagen
                rect = pygame.Rect(0, 0, CACTUS_ANCHO, CACTUS_ALTO)
                rect.center = (x, y)
                pygame.draw.rect(pantalla, COLOR_CACTUS, rect, border_radius=6)
        else:
            # Es un barril
            img = _load_barrel_image(tipo)
            if img:
                rect = img.get_rect()
                rect.center = (x, y)
                pantalla.blit(img, rect)
            else:
                # Fallback si no se puede cargar la imagen
                rect = pygame.Rect(0, 0, BARRIL_ANCHO, BARRIL_ALTO)
                rect.center = (x, y)
                pygame.draw.rect(pantalla, (120, 70, 40), rect, border_radius=6)


def get_obstaculos_rects() -> List[pygame.Rect]:
    """
    Devuelve una lista de rects de colisión de todos los obstáculos.
    El cliente la usa para que el jugador no atraviese los obstáculos (barriles y cactus).
    """
    rects: List[pygame.Rect] = []
    for obs in OBSTACULOS:
        tipo = obs["tipo"]
        x, y = obs["x"], obs["y"]
        
        if tipo == "cactus":
            img = _load_cactus_image()
            if img:
                rect = img.get_rect()
            else:
                rect = pygame.Rect(0, 0, CACTUS_ANCHO, CACTUS_ALTO)
        else:
            # Es un barril
            img = _load_barrel_image(tipo)
            if img:
                rect = img.get_rect()
            else:
                rect = pygame.Rect(0, 0, BARRIL_ANCHO, BARRIL_ALTO)
        
        rect.center = (x, y)
        rects.append(rect)
    return rects

# ------------------------------------------------------------
# PANTALLA DE MENÚ PRINCIPAL
# ------------------------------------------------------------

def draw_menu_principal(
    pantalla,
    ancho: int,
    alto: int,
    texto_ingresado: str,
    mensaje_error: str = None
):
    _draw_background_cowboy(pantalla)

    panel_width = int(ancho * 0.5)
    panel_height = int(alto * 0.4)
    panel_x = (ancho - panel_width) // 2
    panel_y = (alto - panel_height) // 2
    _draw_panel(pantalla, panel_x, panel_y, panel_width, panel_height, alpha=220)

    titulo = FONT_TITULO.render("Cowboy Battle", True, (255, 230, 180))
    pantalla.blit(titulo, (panel_x + (panel_width - titulo.get_width()) // 2, panel_y + 20))

    instruccion = FONT_SUBTITULO.render("Ingresa tu nombre:", True, (255, 255, 255))
    pantalla.blit(instruccion, (panel_x + 30, panel_y + 80))

    campo_nombre_x = panel_x + 30
    campo_nombre_y = panel_y + 115
    campo_w = panel_width - 60
    campo_h = 40
    pygame.draw.rect(pantalla, (255, 255, 255), (campo_nombre_x, campo_nombre_y, campo_w, campo_h))
    pygame.draw.rect(pantalla, (255, 255, 0), (campo_nombre_x, campo_nombre_y, campo_w, campo_h), width=3)
    campo_nombre_rect = pygame.Rect(campo_nombre_x, campo_nombre_y, campo_w, campo_h)

    texto_render = FONT_TEXTO.render(
        texto_ingresado if texto_ingresado else "Escribe tu nombre...",
        True,
        (0, 0, 0) if texto_ingresado else (150, 150, 150)
    )
    pantalla.blit(texto_render, (campo_nombre_x + 10, campo_nombre_y + 8))

    boton_y = panel_y + panel_height - 70
    boton_h = 50
    boton_w = 180
    espacio = 30

    boton_crear_x = panel_x + (panel_width - (boton_w * 2 + espacio)) // 2
    boton_crear_rect = pygame.Rect(boton_crear_x, boton_y, boton_w, boton_h)
    color_crear = (0, 150, 0) if texto_ingresado else (100, 100, 100)
    pygame.draw.rect(pantalla, color_crear, boton_crear_rect, border_radius=5)
    texto_crear = FONT_SUBTITULO.render("Crear Partida", True, (255, 255, 255))
    pantalla.blit(texto_crear, (boton_crear_x + (boton_w - texto_crear.get_width()) // 2, boton_y + 12))

    boton_unirse_x = boton_crear_x + boton_w + espacio
    boton_unirse_rect = pygame.Rect(boton_unirse_x, boton_y, boton_w, boton_h)
    color_unirse = (0, 100, 200) if texto_ingresado else (100, 100, 100)
    pygame.draw.rect(pantalla, color_unirse, boton_unirse_rect, border_radius=5)
    texto_unirse = FONT_SUBTITULO.render("Unirse", True, (255, 255, 255))
    pantalla.blit(texto_unirse, (boton_unirse_x + (boton_w - texto_unirse.get_width()) // 2, boton_y + 12))

    if mensaje_error:
        error_texto = FONT_PEQUE.render(mensaje_error, True, (255, 100, 100))
        pantalla.blit(error_texto, (panel_x + 30, panel_y + panel_height - 30))

    return boton_crear_rect, boton_unirse_rect, campo_nombre_rect


def draw_ingresar_codigo(
    pantalla,
    ancho: int,
    alto: int,
    nombre_jugador: str,
    texto_codigo: str,
    mensaje_error: str = None
):
    _draw_background_cowboy(pantalla)

    panel_width = int(ancho * 0.5)
    panel_height = int(alto * 0.45)
    panel_x = (ancho - panel_width) // 2
    panel_y = (alto - panel_height) // 2
    _draw_panel(pantalla, panel_x, panel_y, panel_width, panel_height, alpha=220)

    titulo = FONT_TITULO.render("Unirse a Partida", True, (255, 230, 180))
    pantalla.blit(
        titulo,
        (panel_x + (panel_width - titulo.get_width()) // 2, panel_y + 20)
    )

    nombre_texto = FONT_TEXTO.render(f"Jugador: {nombre_jugador}", True, (255, 255, 255))
    pantalla.blit(nombre_texto, (panel_x + 30, panel_y + 70))

    instruccion = FONT_SUBTITULO.render("Ingresa el código de la sala:", True, (255, 255, 255))
    pantalla.blit(instruccion, (panel_x + 30, panel_y + 110))

    campo_codigo_x = panel_x + 30
    campo_codigo_y = panel_y + 145
    campo_codigo_w = panel_width - 60
    campo_codigo_h = 40
    pygame.draw.rect(
        pantalla,
        (255, 255, 255),
        (campo_codigo_x, campo_codigo_y, campo_codigo_w, campo_codigo_h)
    )
    pygame.draw.rect(
        pantalla,
        (255, 255, 0),
        (campo_codigo_x, campo_codigo_y, campo_codigo_w, campo_codigo_h),
        width=3
    )
    campo_codigo_rect = pygame.Rect(
        campo_codigo_x, campo_codigo_y, campo_codigo_w, campo_codigo_h
    )

    codigo_render = FONT_TEXTO.render(
        texto_codigo if texto_codigo else "ABC123",
        True,
        (0, 0, 0) if texto_codigo else (150, 150, 150)
    )
    pantalla.blit(codigo_render, (campo_codigo_x + 10, campo_codigo_y + 8))

    boton_h = 50
    boton_w = 150
    espacio = 20
    boton_y = campo_codigo_y + campo_codigo_h + 10

    limite_inferior_panel = panel_y + panel_height
    max_boton_y = limite_inferior_panel - boton_h - 20
    boton_y = min(boton_y, max_boton_y)

    boton_cancelar_x = panel_x + (panel_width - (boton_w * 2 + espacio)) // 2
    boton_cancelar_rect = pygame.Rect(boton_cancelar_x, boton_y, boton_w, boton_h)
    pygame.draw.rect(pantalla, (150, 150, 150), boton_cancelar_rect, border_radius=5)
    texto_cancelar = FONT_SUBTITULO.render("Cancelar", True, (255, 255, 255))
    pantalla.blit(
        texto_cancelar,
        (boton_cancelar_x + (boton_w - texto_cancelar.get_width()) // 2,
         boton_y + 12)
    )

    boton_unirse_x = boton_cancelar_x + boton_w + espacio
    boton_unirse_rect = pygame.Rect(boton_unirse_x, boton_y, boton_w, boton_h)
    color_unirse = (0, 100, 200) if texto_codigo.strip() else (100, 100, 100)
    pygame.draw.rect(pantalla, color_unirse, boton_unirse_rect, border_radius=5)
    texto_unirse = FONT_SUBTITULO.render("Unirse", True, (255, 255, 255))
    pantalla.blit(
        texto_unirse,
        (boton_unirse_x + (boton_w - texto_unirse.get_width()) // 2,
         boton_y + 12)
    )

    if mensaje_error:
        error_texto = FONT_PEQUE.render(mensaje_error, True, (255, 100, 100))
        error_y = boton_y + boton_h + 10
        if error_y + error_texto.get_height() > limite_inferior_panel - 10:
            error_y = limite_inferior_panel - 10 - error_texto.get_height()
        pantalla.blit(error_texto, (panel_x + 30, error_y))

    return boton_cancelar_rect, boton_unirse_rect, campo_codigo_rect


# ------------------------------------------------------------
# PANTALLA DE LOBBY
# ------------------------------------------------------------

def draw_lobby_screen(
    pantalla,
    ancho: int,
    alto: int,
    player_id: int | None,
    yo_listo: bool,
    estado_sala: Dict[str, Any],
    es_host: bool = False,
    codigo_sala: str | None = None
):
    _draw_background_cowboy(pantalla)

    panel_width = int(ancho * 0.7)
    panel_height = int(alto * 0.6)
    panel_x = (ancho - panel_width) // 2
    panel_y = (alto - panel_height) // 2
    _draw_panel(pantalla, panel_x, panel_y, panel_width, panel_height, alpha=200)

    titulo = FONT_TITULO.render("Cowboy Battle - Lobby", True, (255, 230, 180))
    pantalla.blit(titulo, (panel_x + 20, panel_y + 15))

    if es_host:
        host_texto = FONT_SUBTITULO.render("(HOST)", True, (255, 215, 0))
        pantalla.blit(host_texto, (panel_x + titulo.get_width() + 30, panel_y + 20))

    if codigo_sala:
        codigo_texto = FONT_SUBTITULO.render(f"Código de sala: {codigo_sala}", True, (255, 255, 0))
        pantalla.blit(codigo_texto, (panel_x + 20, panel_y + 60))
        instruccion_codigo = FONT_PEQUE.render("Comparte este código con otros jugadores", True, (200, 200, 200))
        pantalla.blit(instruccion_codigo, (panel_x + 20, panel_y + 85))

    jugadores = estado_sala.get("jugadores", {})
    y_text = panel_y + 120

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
                color_nombre = (0, 230, 255)
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

    y_text = panel_y + panel_height - 120
    if es_host:
        instr1 = FONT_TEXTO.render("Presiona ESPACIO para iniciar la partida", True, (255, 255, 0))
        pantalla.blit(instr1, (panel_x + 20, y_text))
        y_text += 30
    else:
        instr1 = FONT_TEXTO.render("Esperando a que el host inicie la partida...", True, (255, 255, 255))
        pantalla.blit(instr1, (panel_x + 20, y_text))
        y_text += 30

    estado_txt = "LISTO" if yo_listo else "No listo"
    color_estado = (0, 255, 120) if yo_listo else (255, 120, 120)
    texto_estado = FONT_TEXTO.render(f"Tu estado: {estado_txt}", True, color_estado)
    pantalla.blit(texto_estado, (panel_x + 20, y_text))


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
    jugadores_danados: Dict[int, float] = None,
    nombres_jugadores: Dict[int, str] = None
):
    _draw_arena_background(pantalla)

    # DIBUJAR OBSTÁCULOS (barriles rectangulares)
    _draw_obstaculos(pantalla)

    # Balas
    for bala_id, info in estado_balas.items():
        bx = int(info.get("x", 0))
        by = int(info.get("y", 0))
        pygame.draw.circle(pantalla, COLOR_BALA, (bx, by), TAMAÑO_BALA // 2)

    dano_img = _load_jugador_dano_image()
    if jugadores_danados is None:
        jugadores_danados = {}
    if nombres_jugadores is None:
        nombres_jugadores = {}

    # Jugadores remotos
    for pid, pos in estado_jugadores.items():
        jx = int(pos.get("x", 0))
        jy = int(pos.get("y", 0))

        esta_danado = pid in jugadores_danados

        if esta_danado and dano_img:
            imagen_a_dibujar = dano_img
        else:
            imagen_a_dibujar = _load_jugador_image(pid)

        if imagen_a_dibujar:
            rect_jugador = imagen_a_dibujar.get_rect()
            rect_jugador.center = (jx, jy)
            pantalla.blit(imagen_a_dibujar, rect_jugador)
        else:
            rect = pygame.Rect(0, 0, TAMAÑO_CUADRADO, TAMAÑO_CUADRADO)
            rect.center = (jx, jy)
            pygame.draw.rect(pantalla, COLOR_JUGADOR_OTRO, rect, border_radius=5)

        nick = nombres_jugadores.get(pid, f"P{pid}")
        label = FONT_PEQUE.render(nick, True, (255, 255, 255))
        pantalla.blit(label, (jx - label.get_width() // 2, jy - TAMAÑO_CUADRADO // 2 - 18))

    # Jugador local
    if player_id is not None:
        x_local_int = int(x_local)
        y_local_int = int(y_local)

        esta_danado_local = player_id in jugadores_danados

        if esta_danado_local and dano_img:
            imagen_a_dibujar_local = dano_img
        else:
            imagen_a_dibujar_local = _load_jugador_image(player_id)

        if imagen_a_dibujar_local:
            rect_jugador_local = imagen_a_dibujar_local.get_rect()
            rect_jugador_local.center = (x_local_int, y_local_int)
            pantalla.blit(imagen_a_dibujar_local, rect_jugador_local)
        else:
            rect_local = pygame.Rect(0, 0, TAMAÑO_CUADRADO, TAMAÑO_CUADRADO)
            rect_local.center = (x_local_int, y_local_int)
            pygame.draw.rect(pantalla, COLOR_JUGADOR_LOCAL, rect_local, border_radius=8)

        label_local = FONT_PEQUE.render("Tú", True, (255, 255, 255))
        pantalla.blit(label_local, (x_local_int - label_local.get_width() // 2,
                                    y_local_int - TAMAÑO_CUADRADO // 2 - 18))

    _draw_scoreboard(pantalla, ancho, puntuacion, player_id, nombres_jugadores)


def _draw_scoreboard(pantalla, ancho: int, puntuacion: Dict[int, int], player_id: int | None, nombres_jugadores: Dict[int, str] = None):
    if not puntuacion:
        return

    if nombres_jugadores is None:
        nombres_jugadores = {}

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
        nombre = nombres_jugadores.get(pid, f"P{pid}")
        texto = FONT_TEXTO.render(f"{nombre}: {score}", True, color)
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
    puntuacion: Dict[int, int],
    nombres_jugadores: Dict[int, str] = None
):
    _draw_background_cowboy(pantalla)

    if nombres_jugadores is None:
        nombres_jugadores = {}

    panel_width = int(ancho * 0.6)
    panel_height = int(alto * 0.5)
    panel_x = (ancho - panel_width) // 2
    panel_y = (alto - panel_height) // 2
    _draw_panel(pantalla, panel_x, panel_y, panel_width, panel_height, alpha=220)

    titulo = FONT_TITULO.render("¡Duelo finalizado!", True, (255, 230, 180))
    pantalla.blit(titulo, (panel_x + (panel_width - titulo.get_width()) // 2, panel_y + 20))

    if ganador_id is not None:
        nombre_ganador = nombres_jugadores.get(ganador_id, f"P{ganador_id}")
        texto_ganador = FONT_SUBTITULO.render(
            f"Ganador: {nombre_ganador}",
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

    y = panel_y + 130
    encabezado = FONT_SUBTITULO.render("Marcador final:", True, (255, 255, 255))
    pantalla.blit(encabezado, (panel_x + 30, y))
    y += 35

    for pid, score in sorted(puntuacion.items(), key=lambda kv: kv[1], reverse=True):
        nombre = nombres_jugadores.get(pid, f"P{pid}")
        linea = FONT_TEXTO.render(f"{nombre}: {score}", True, (255, 255, 255))
        pantalla.blit(linea, (panel_x + 40, y))
        y += 26

    texto_instr = FONT_TEXTO.render("Cierra la ventana para salir.", True, (255, 255, 255))
    pantalla.blit(
        texto_instr,
        (panel_x + (panel_width - texto_instr.get_width()) // 2,
         panel_y + panel_height - 50)
    )
