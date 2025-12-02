# Documentación del Cliente - Cowboy Battle

## Índice
1. [Introducción](#introducción)
2. [Arquitectura WebSocket en el Cliente](#arquitectura-websocket-en-el-cliente)
3. [Ciclo de Vida del Cliente](#ciclo-de-vida-del-cliente)
4. [Estados del Juego](#estados-del-juego)
5. [Sincronización con el Servidor](#sincronización-con-el-servidor)
6. [Gestión de Entrada del Usuario](#gestión-de-entrada-del-usuario)
7. [Renderizado y Visualización](#renderizado-y-visualización)
8. [Manejo de Red y Reconexión](#manejo-de-red-y-reconexión)

---

## Introducción

El cliente de **Cowboy Battle** es una aplicación **Pygame** que se conecta a un servidor WebSocket para jugar en tiempo real. El cliente maneja:

- Interfaz de usuario (menús, lobby, juego)
- Captura de entrada del jugador (teclado)
- Renderizado visual (Pygame)
- Comunicación con el servidor (WebSocket)
- Sincronización del estado del juego

### Tecnologías Utilizadas

- **Python 3.12+**
- **Pygame**: Renderizado gráfico y captura de entrada
- **websockets**: Cliente WebSocket para comunicación con el servidor
- **asyncio**: Para manejar WebSocket de forma asíncrona junto con Pygame

### Arquitectura Híbrida

El cliente combina dos loops principales:

1. **Loop de Pygame**: Síncrono, renderiza a 60 FPS
2. **Loop de WebSocket**: Asíncrono, recibe mensajes del servidor

Ambos se ejecutan en la misma función asíncrona usando `asyncio.wait_for()` para no bloquear el renderizado.

---

## Arquitectura WebSocket en el Cliente

### Conexión Inicial

El cliente se conecta al servidor usando:

```python
uri = "ws://localhost:9000"
websocket = await websockets.connect(uri)
```

- **Protocolo**: `ws://` para WebSocket (o `wss://` para seguro)
- **Dirección**: `localhost:9000` por defecto (cambiable para conexiones remotas)
- **Handshake**: Se establece automáticamente al conectar

### Comunicación Bidireccional

**Cliente → Servidor**:
```python
mensaje = {
    "tipo": "crear_partida",
    "nombre": "Jugador1"
}
await websocket.send(json.dumps(mensaje))
```

**Servidor → Cliente**:
```python
mensaje = await asyncio.wait_for(websocket.recv(), timeout=0.005)
datos = json.loads(mensaje)
# Procesar datos
```

### Manejo Asíncrono

El cliente usa `asyncio.wait_for()` con timeout muy corto (5ms) para no bloquear el loop de Pygame:

```python
try:
    mensaje = await asyncio.wait_for(websocket.recv(), timeout=0.005)
    # Procesar mensaje
except asyncio.TimeoutError:
    # No hay mensajes, continuar con el renderizado
    pass
```

Esto permite:
- Recibir mensajes del servidor cuando están disponibles
- No bloquear el renderizado si no hay mensajes
- Mantener 60 FPS en Pygame

---

## Ciclo de Vida del Cliente

### 1. Inicialización

```python
# Inicializar Pygame
pygame.init()
pantalla = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Cowboy Battle - Cliente")

# Estado inicial
en_menu_principal = True
websocket = None
player_id = None
```

### 2. Menú Principal

**Estado**: `en_menu_principal = True`

- El usuario ingresa su nombre
- Elige "Crear Partida" o "Unirse"
- Si elige crear/unirse, se conecta al servidor

**Acción "Crear Partida"**:
```python
websocket = await websockets.connect(uri)
mensaje = {
    "tipo": "crear_partida",
    "nombre": nombre_jugador
}
await websocket.send(json.dumps(mensaje))
```

**Acción "Unirse"**:
1. Usuario ingresa código de sala
2. Se conecta al servidor
3. Envía mensaje `unirse_partida` con el código

### 3. Asignación de ID

El servidor responde con:

```json
{
    "tipo": "asignacion_id",
    "player_id": 1,
    "x": 200,
    "y": 300,
    "es_host": true,
    "codigo_sala": "ABC123",
    "sprite_index": 1
}
```

**El cliente**:
- Guarda `player_id`, `codigo_sala`, `es_host`
- Actualiza posición local con la del servidor
- Cambia a estado `en_lobby = True`

### 4. Lobby

**Estado**: `en_lobby = True`

- Muestra lista de jugadores en la sala
- Muestra estado de "listo" de cada jugador
- El usuario puede presionar `L` para marcar/desmarcar "listo"
- Si es host, puede hacer click en "Iniciar Partida" (botón habilitado solo si todos están listos)

**Mensajes enviados**:
- `ready`: Cambiar estado de "listo"
- `iniciar_partida`: Iniciar la partida (solo host)

**Mensajes recibidos**:
- `estado_sala`: Actualización del estado del lobby

### 5. Partida en Curso

**Estado**: `en_juego = True`

- El servidor envía `start_game`
- El cliente cambia a modo juego
- Se recibe estado periódicamente (`~60 veces/segundo`)

**Input del jugador**:
- **Movimiento**: WASD o flechas
- **Disparo**: ESPACIO o J

**Sincronización**:
- El cliente envía su posición periódicamente (throttling)
- El cliente recibe estado de todos los jugadores y balas

### 6. Game Over

**Estado**: `game_over = True`

- El servidor envía `game_over` con el ganador
- Se muestra pantalla de fin de juego
- El usuario puede:
  - "Volver a jugar": Resetear y volver al menú
  - "Cerrar": Salir del juego

---

## Estados del Juego

El cliente mantiene varios estados booleanos que controlan qué pantalla mostrar:

```python
en_menu_principal = True    # Pantalla inicial
ingresando_codigo = False   # Ingresando código de sala
en_lobby = False            # En la sala esperando
en_juego = False            # Jugando
game_over = False           # Partida terminada
```

### Transiciones de Estado

```
MENÚ PRINCIPAL
    ↓ (Crear/Unirse)
LOBBY
    ↓ (Host inicia, todos listos)
JUGANDO
    ↓ (Alguien gana o todos se desconectan)
GAME OVER
    ↓ (Volver a jugar)
MENÚ PRINCIPAL
```

---

## Sincronización con el Servidor

### Concepto: Servidor Autoritativo

El servidor tiene la **verdad absoluta** del estado del juego. El cliente:

1. **Predice localmente** (movimiento suave)
2. **Envía actualizaciones** al servidor
3. **Recibe correcciones** del servidor
4. **Se sincroniza** cuando hay diferencias grandes

### Sincronización de Posición

**Movimiento Local (Predicción)**:

El cliente mueve al jugador localmente según las teclas:

```python
if teclas[pygame.K_w]:
    movimiento_y = -VELOCIDAD_MOVIMIENTO
    # Verificar colisiones con obstáculos
    # Aplicar movimiento si no hay colisión
    y = nuevo_y
```

**Envío al Servidor (Throttling)**:

```python
if (x, y) != posicion_anterior:
    if tiempo_actual - ultimo_envio_posicion >= 0.05:  # 50ms
        mensaje = {
            "tipo": "update_pos",
            "player_id": player_id,
            "x": x,
            "y": y
        }
        await websocket.send(json.dumps(mensaje))
        ultimo_envio_posicion = tiempo_actual
```

**Recepción y Corrección**:

El servidor envía el estado periódicamente. Si la posición local difiere mucho de la del servidor, se corrige:

```python
if player_id in jugadores_recibidos:
    pos_servidor = jugadores_recibidos[player_id]
    dist = math.sqrt((x - pos_servidor["x"]) ** 2 + (y - pos_servidor["y"]) ** 2)
    if dist > 50:  # Diferencia grande
        x = pos_servidor["x"]  # Corregir
        y = pos_servidor["y"]
```

### Sincronización de Otros Jugadores

**Recepción**:
```python
estado_jugadores = {}
for pid, pos in jugadores_recibidos.items():
    if pid != player_id:  # No incluir al jugador local
        estado_jugadores[pid] = pos
```

**Renderizado**:
El cliente dibuja a los otros jugadores exactamente como el servidor los reporta (sin predicción local).

### Sincronización de Balas

**Recepción**:
```python
estado_balas = datos.get("balas", {})
```

**Detección de Desaparición**:
Comparando con el estado anterior, se detecta qué balas desaparecieron (impacto, salida de pantalla, etc.)

```python
balas_que_desaparecieron = set(estado_balas_anterior.keys()) - set(estado_balas.keys())
if balas_que_desaparecieron:
    # Reproducir efecto de impacto, etc.
```

**Renderizado**:
Las balas se dibujan exactamente como el servidor las reporta (movimiento autoritativo).

### Sincronización de Puntuación

```python
puntuacion = datos.get("puntuacion", {})
```

**Detección de Cambios**:
Comparando con la puntuación anterior, se detecta cuando alguien fue golpeado para mostrar efectos visuales.

### Sincronización de Power-ups

```python
estrella_pos = datos.get("estrella")  # {"x": x, "y": y} o None
jugadores_invencibles = datos.get("jugadores_invencibles", {})
```

El cliente muestra la estrella y los efectos de invencibilidad según el estado del servidor.

---

## Gestión de Entrada del Usuario

### Movimiento

**Teclas**:
- `W` / `↑`: Arriba
- `S` / `↓`: Abajo
- `A` / `←`: Izquierda
- `D` / `→`: Derecha

**Lógica**:
```python
movimiento_x = 0
movimiento_y = 0

if teclas[pygame.K_w]:
    movimiento_y = -VELOCIDAD_MOVIMIENTO
    ultima_direccion_movimiento = "up"
# ... más direcciones

# Verificar colisiones con obstáculos ANTES de mover
obstaculos_rects = theme.get_obstaculos_rects()
rect_jugador = pygame.Rect(0, 0, 60, 60)
rect_jugador.center = (nuevo_x, nuevo_y)

if not any(rect_jugador.colliderect(o) for o in obstaculos_rects):
    x = nuevo_x  # Aplicar movimiento
```

**Importante**: El cliente previene movimiento a través de obstáculos **localmente** para mejor UX, pero el servidor también tiene las posiciones correctas.

### Disparo

**Teclas**: `ESPACIO` o `J`

**Lógica**:
```python
if puede_disparar and en_juego:
    direccion = ultima_direccion_movimiento
    mensaje = {
        "tipo": "shoot",
        "player_id": player_id,
        "direccion": direccion
    }
    await websocket.send(json.dumps(mensaje))
    puede_disparar = False  # Prevenir spam
    # Se reactiva cuando la bala desaparece
```

### Estado "Listo"

**Tecla**: `L` (en lobby)

```python
yo_listo = not yo_listo
mensaje = {
    "tipo": "ready",
    "player_id": player_id,
    "listo": yo_listo
}
await websocket.send(json.dumps(mensaje))
```

---

## Renderizado y Visualización

### Arquitectura de Renderizado

El cliente usa el módulo `cowboy_theme.py` para todo el renderizado. Esto separa la lógica de red de la lógica visual.

**Función principal**:
```python
theme.draw_game_screen(
    pantalla,
    ancho, alto,
    player_id,
    estado_jugadores,      # Del servidor
    x, y,                  # Posición local
    estado_balas,          # Del servidor
    puntuacion,            # Del servidor
    jugadores_danados,     # Calculado localmente
    nombres_jugadores,
    estrella_pos,          # Del servidor
    jugadores_invencibles, # Del servidor
    sprite_indices         # Del servidor
)
```

### Loop de Renderizado

```python
while corriendo:
    # 1. Procesar eventos (teclado, mouse, cerrar ventana)
    for evento in pygame.event.get():
        # Manejar eventos
    
    # 2. Actualizar lógica (movimiento, input)
    # 3. Recibir mensajes del servidor (con timeout)
    # 4. Renderizar según el estado actual
    if en_menu_principal:
        theme.draw_menu_principal(...)
    elif en_lobby:
        theme.draw_lobby_screen(...)
    elif game_over:
        theme.draw_game_over_screen(...)
    else:
        theme.draw_game_screen(...)
    
    pygame.display.flip()
    reloj.tick(60)  # 60 FPS
```

### Renderizado de Jugadores

**Jugador Local**:
- Se dibuja usando la posición local (`x`, `y`)
- Tiene etiqueta "Tú"
- Efectos visuales especiales si es invencible

**Otros Jugadores**:
- Se dibujan usando `estado_jugadores` (del servidor)
- Usan `sprite_index` para el sprite correcto
- Tienen sus nombres encima

### Renderizado de Balas

```python
for bala_id, info in estado_balas.items():
    bx = int(info.get("x", 0))
    by = int(info.get("y", 0))
    pygame.draw.circle(pantalla, COLOR_BALA, (bx, by), 4)
```

Las balas se dibujan exactamente como el servidor las reporta.

### Efectos Visuales

**Daño**:
- Cuando se detecta un cambio en puntuación, se muestra sprite de daño
- Duración: 0.3 segundos

**Invencibilidad**:
- Aura dorada pulsante alrededor del jugador
- Parpadeo: 5 veces por segundo
- Etiqueta especial: "Tú [INV]"

---

## Manejo de Red y Reconexión

### Gestión de Conexión

**Conexión Inicial**:
```python
try:
    websocket = await websockets.connect(uri)
except ConnectionRefusedError:
    # Servidor no disponible
    mensaje_error = "No se pudo conectar al servidor"
```

**Desconexión**:
```python
except websockets.exceptions.ConnectionClosed:
    print("Conexión cerrada por el servidor")
    # El cliente puede cerrar o intentar reconectar
```

### Manejo de Errores

**Mensajes Inválidos**:
```python
try:
    datos = json.loads(mensaje)
except json.JSONDecodeError:
    # Ignorar mensaje inválido
    pass
```

**Excepciones Generales**:
```python
except Exception as e:
    print(f"Error en la conexión: {e}")
    # Continuar ejecutando si es posible
```

### Timeout en Recepción

El uso de `asyncio.wait_for(websocket.recv(), timeout=0.005)` permite:
- No bloquear el renderizado
- Continuar si no hay mensajes
- Mantener 60 FPS constantes

---

## Estructura de Datos del Cliente

### Estado del Juego

```python
# Identificación
player_id: int | None
es_host: bool
codigo_sala: str | None

# Estado de conexión
websocket: websockets.WebSocketClientProtocol | None

# Estados de pantalla
en_menu_principal: bool
en_lobby: bool
en_juego: bool
game_over: bool

# Estado del jugador local
x: float
y: float
yo_listo: bool

# Estado recibido del servidor
estado_jugadores: Dict[int, Dict[str, float]]  # Otros jugadores
estado_balas: Dict[str, Dict[str, float]]
puntuacion: Dict[int, int]
estrella_pos: Dict[str, float] | None
jugadores_invencibles: Dict[int, float]
estado_sala: Dict[str, Any]  # Info del lobby
sprite_indices: Dict[int, int]  # Sprite por jugador
```

### Estado Temporal

```python
jugadores_danados: Dict[int, float]  # Para efecto visual
puede_disparar: bool  # Control de disparo
ultima_direccion_movimiento: str  # Para disparo
```

---

## Flujo de Mensajes Cliente-Servidor

### Secuencia: Crear Partida

```
CLIENTE                          SERVIDOR
  |                                 |
  |--- crear_partida -------------->|
  |                                 | Crea sala
  |                                 | Asigna player_id
  |<-- asignacion_id ---------------|
  |                                 |
  |<-- estado_sala -----------------|
  |
  (Ahora en lobby)
```

### Secuencia: Unirse a Partida

```
CLIENTE                          SERVIDOR
  |                                 |
  |--- unirse_partida ------------->|
  |    (codigo: "ABC123")           | Valida código
  |                                 | Agrega a sala
  |<-- asignacion_id ---------------|
  |                                 |
  |<-- estado_sala -----------------|
  |                                 | (también a otros jugadores)
  |
  (Ahora en lobby)
```

### Secuencia: Iniciar Partida

```
CLIENTE (Host)                  SERVIDOR
  |                                 |
  |--- iniciar_partida ----------->|
  |                                 | Valida (todos listos?)
  |                                 | Cambia a "jugando"
  |<-- start_game -----------------|
  |                                 |
  |<-- estado ---------------------|
  |     (periódicamente ~60/s)      |
  |
  (Ahora jugando)
```

### Secuencia: Movimiento y Disparo

```
CLIENTE                          SERVIDOR
  |                                 |
  |--- update_pos ----------------->|
  |    (cada 50ms si cambió)        | Actualiza estado
  |                                 |
  |--- shoot ---------------------->|
  |                                 | Crea bala
  |<-- estado ---------------------|
  |    (con nueva bala)             |
  |                                 |
  |--- update_pos ----------------->|
  |<-- estado ---------------------|
  |    (bala movida, impactos, etc) |
```

### Secuencia: Game Over

```
CLIENTE                          SERVIDOR
  |                                 |
  |                                 | (Alguien llega a 3)
  |<-- game_over ------------------|
  |    (ganador, puntuación)        |
  |
  (Pantalla de game over)
```

---

## Sincronización Detallada

### Problema: Latencia de Red

**Escenario**: El jugador se mueve, pero hay 50ms de latencia.

**Solución**: **Predicción local + Corrección**

1. **Cliente mueve localmente** → Movimiento instantáneo, sin esperar servidor
2. **Cliente envía al servidor** → El servidor actualiza su estado
3. **Cliente recibe confirmación** → Si hay diferencia grande, se corrige

**Resultado**: Movimiento fluido incluso con latencia.

### Problema: Desincronización

**Escenario**: La posición local difiere mucho de la del servidor.

**Solución**: **Corrección automática**

```python
if dist_respawn > 50:  # Diferencia > 50 píxeles
    x = servidor_x  # Corregir inmediatamente
    y = servidor_y
```

**Resultado**: El jugador siempre se mantiene sincronizado con el servidor.

### Throttling de Actualizaciones

**Problema**: Enviar cada frame (60/segundo) es excesivo.

**Solución**: Enviar solo cuando:
- La posición cambió
- Ha pasado suficiente tiempo (50ms = 20/segundo)

**Resultado**: Menos tráfico de red, misma experiencia de juego.

---

## Detección de Eventos Locales

Aunque el servidor es autoritativo, el cliente detecta algunos eventos localmente para efectos visuales inmediatos:

### Detección de Impacto

```python
# Comparar puntuación anterior con nueva
if puntuacion.get(pid, 0) > puntuacion_anterior.get(pid, 0):
    # Alguien fue golpeado
    # Mostrar sprite de daño
    jugadores_danados[pid] = time.time()
```

### Detección de Bala Desaparecida

```python
balas_que_desaparecieron = set(estado_balas_anterior.keys()) - set(estado_balas.keys())
if balas_que_desaparecieron:
    # La bala desapareció (impacto o salida)
    puede_disparar = True  # Permitir nuevo disparo
```

---

## Manejo de Desconexiones

### Cuando el Servidor Se Desconecta

```python
except websockets.exceptions.ConnectionClosed:
    print("Conexión cerrada por el servidor")
    # El juego puede cerrarse o mostrar mensaje de error
```

### Cuando Otro Jugador Se Desconecta

El cliente simplemente deja de recibir actualizaciones de ese jugador:
- Desaparece de `estado_jugadores`
- Se elimina de la lista de jugadores
- Si era el último, puede ganar por abandono (notificado por servidor)

---

## Optimizaciones

### 1. Throttling de Posición

Evita enviar actualizaciones excesivas:
- Solo si la posición cambió
- Máximo cada 50ms

### 2. Timeout Corto en Recepción

`timeout=0.005` (5ms) permite:
- No bloquear el renderizado
- Mantener 60 FPS

### 3. Predicción Local

Movimiento local inmediato sin esperar servidor:
- Mejor experiencia de usuario
- Corrección automática si es necesario

### 4. Caché de Sprites

Los sprites se cargan una vez y se reutilizan:
- Mejor rendimiento
- Menos I/O de disco

---

## Flujo Completo de una Sesión

1. **Inicio**: Cliente muestra menú principal
2. **Conexión**: Usuario ingresa nombre, crea/unirse a sala
3. **Lobby**: Cliente recibe estado de sala, muestra jugadores
4. **Listo**: Usuario marca "listo", servidor actualiza
5. **Inicio**: Host inicia, cliente recibe `start_game`
6. **Juego**:
   - Cliente captura input (movimiento, disparo)
   - Cliente envía actualizaciones al servidor
   - Cliente recibe estado del servidor (~60/s)
   - Cliente renderiza todo
7. **Fin**: Cliente recibe `game_over`, muestra pantalla final
8. **Post-juego**: Usuario puede volver a jugar o cerrar

---

## Consideraciones de Rendimiento

### Frame Rate

- **Objetivo**: 60 FPS
- **Renderizado**: Síncrono, bloqueante
- **Red**: Asíncrono, no bloqueante

### Uso de CPU

- Renderizado: ~16ms por frame (60 FPS)
- Red: Timeout de 5ms no bloquea
- Total: < 20ms por iteración del loop

### Uso de Red

- **Envío**: ~20 mensajes/segundo (posición si cambia)
- **Recepción**: ~60 mensajes/segundo (estado completo)
- **Tamaño**: Mensajes JSON pequeños (< 1 KB típicamente)

---

## Conclusión

El cliente actúa como la **interfaz** del juego, capturando input del usuario, renderizando el estado visual, y manteniéndose sincronizado con el servidor autoritativo. La combinación de predicción local y corrección del servidor proporciona una experiencia fluida incluso con latencia de red, mientras que el uso de WebSockets garantiza comunicación en tiempo real eficiente.

