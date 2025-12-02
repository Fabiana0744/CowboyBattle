# Documentación del Servidor - Cowboy Battle

## Índice
1. [Introducción](#introducción)
2. [Arquitectura WebSocket](#arquitectura-websocket)
3. [Sistema de Salas](#sistema-de-salas)
4. [Flujo de Conexión](#flujo-de-conexión)
5. [Sincronización del Estado del Juego](#sincronización-del-estado-del-juego)
6. [Mensajes y Protocolo](#mensajes-y-protocolo)
7. [Lógica del Juego](#lógica-del-juego)
8. [Gestión de Desconexiones](#gestión-de-desconexiones)

---

## Introducción

El servidor de **Cowboy Battle** es un servidor **autoritativo** que gestiona todo el estado del juego usando **WebSockets** para comunicación en tiempo real. El servidor es el único responsable de:

- Validar todas las acciones de los jugadores
- Calcular colisiones y físicas
- Mantener el estado sincronizado entre todos los clientes
- Gestionar múltiples salas de juego independientes

### Tecnologías Utilizadas

- **Python 3.12+**
- **websockets**: Biblioteca para comunicación WebSocket asíncrona
- **asyncio**: Para programación asíncrona y manejo concurrente de conexiones
- **json**: Serialización de mensajes

---

## Arquitectura WebSocket

### ¿Qué es WebSocket?

WebSocket es un protocolo de comunicación **bidireccional** que permite una conexión persistente entre cliente y servidor. A diferencia de HTTP (que es request-response), WebSocket permite que tanto el servidor como el cliente envíen mensajes en cualquier momento.

### Ventajas para Juegos Multiplayer

1. **Baja latencia**: Conexión persistente evita overhead de HTTP
2. **Bidireccional**: El servidor puede enviar actualizaciones sin que el cliente las solicite
3. **Full-duplex**: Permite comunicación simultánea en ambas direcciones
4. **Eficiente**: Headers mínimos después del handshake inicial

### Configuración del Servidor

```python
async with websockets.serve(manejar_cliente, "0.0.0.0", 9000):
    # El servidor escucha en todas las interfaces de red (0.0.0.0) en el puerto 9000
    # Cada cliente nuevo activa la función manejar_cliente()
```

- **Puerto**: 9000
- **Protocolo**: `ws://` (WebSocket) o `wss://` (WebSocket seguro)
- **Escucha en**: `0.0.0.0` (todas las interfaces, permite conexiones remotas)

---

## Sistema de Salas

El servidor maneja múltiples **salas** (rooms) independientes. Cada sala es completamente aislada y tiene su propio estado de juego.

### Estructura de una Sala

Cada sala (`salas[codigo_sala]`) contiene:

```python
{
    "host_id": int,                    # ID del jugador que creó la sala
    "jugadores": [websocket, ...],     # Lista de conexiones WebSocket activas
    "jugadores_info": {                # Información de cada jugador
        websocket: {
            "id": player_id,
            "nombre": "nombre",
            "es_host": bool,
            "sprite_index": int        # Sprite a usar (1, 2 o 3)
        }
    },
    "estado": {                        # Posiciones de jugadores
        player_id: {"x": x, "y": y}
    },
    "balas": {                         # Balas activas en el juego
        bala_id: {
            "x": x, "y": y,
            "vx": vx, "vy": vy,        # Velocidad
            "player_id": owner_id
        }
    },
    "puntuacion": {                    # Puntuación por jugador
        player_id: int
    },
    "estado_partida": str,             # "lobby", "jugando", "game_over"
    "jugadores_listos": {              # Estado de "listo" por jugador
        player_id: bool
    },
    "estrella_actual": {               # Power-up activo o None
        "x": x, "y": y
    } | None,
    "jugadores_invencibles": {         # Tiempo de fin de invencibilidad
        player_id: float               # timestamp
    },
    "siguiente_bala_id": int,          # Contador para IDs únicos de balas
    "ultima_estrella_tiempo": float    # Timestamp de última estrella generada
}
```

### Código de Sala

- **Formato**: 6 caracteres alfanuméricos (ej: "ABC123")
- **Generación**: Aleatorio, garantiza unicidad
- **Uso**: Los jugadores lo usan para unirse a una sala específica

### Mapeo WebSocket → Sala

El diccionario `websocket_a_sala` permite encontrar rápidamente a qué sala pertenece cada conexión:

```python
websocket_a_sala[websocket] = codigo_sala
```

Esto es crucial para enrutar mensajes al estado correcto de la sala.

---

## Flujo de Conexión

### 1. Cliente Se Conecta

Cuando un cliente se conecta al servidor:

```python
async def manejar_cliente(websocket):
    # Se crea una conexión WebSocket para este cliente
    # Se inicia un loop para escuchar mensajes
    async for mensaje in websocket:
        # Procesar cada mensaje recibido
```

**Estado inicial**: El cliente está conectado pero **no está en ninguna sala**.

### 2. Crear Partida (Host)

El cliente envía:

```json
{
    "tipo": "crear_partida",
    "nombre": "NombreJugador"
}
```

**Proceso del servidor**:

1. **Genera código único** de 6 caracteres para la sala
2. **Asigna player_id único** (contador global)
3. **Crea estructura de sala** con estado inicial:
   - `estado_partida = "lobby"`
   - `host_id = player_id`
   - Posición inicial del jugador
4. **Mapea websocket → sala**
5. **Responde al cliente** con:
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
6. **Envía estado de la sala** a todos (en este caso, solo al host)

### 3. Unirse a Partida

El cliente envía:

```json
{
    "tipo": "unirse_partida",
    "nombre": "NombreJugador",
    "codigo_sala": "ABC123"
}
```

**Proceso del servidor**:

1. **Valida el código** de sala
2. **Rechaza si la partida ya está en curso**
3. **Asigna player_id único**
4. **Calcula sprite_index** basado en el orden de entrada (1, 2, 3, rotando)
5. **Agrega jugador a la sala**:
   - Añade websocket a `sala["jugadores"]`
   - Crea entrada en `sala["jugadores_info"]`
   - Inicializa `jugadores_listos[player_id] = False`
   - Asigna posición inicial según número de jugadores
6. **Mapea websocket → sala**
7. **Responde al cliente** con asignación de ID
8. **Notifica a todos** el nuevo estado de la sala

---

## Sincronización del Estado del Juego

El servidor mantiene el **estado autoritativo** del juego y lo sincroniza con todos los clientes periódicamente.

### Actualización de Posiciones

**Cliente → Servidor**:

El cliente envía su posición periódicamente (con throttling):

```json
{
    "tipo": "update_pos",
    "player_id": 1,
    "x": 350.5,
    "y": 250.3
}
```

**Frecuencia**: Máximo cada 50ms (20 veces por segundo), solo si la posición cambió.

**Servidor**:
- **Valida** que el jugador pertenece a esa sala
- **Actualiza** `sala["estado"][player_id] = {"x": x, "y": y}`
- **No responde** directamente (la respuesta viene en la actualización periódica)

### Broadcast del Estado

**Servidor → Clientes**:

El servidor envía el estado completo periódicamente a todos los jugadores de la sala:

```json
{
    "tipo": "estado",
    "jugadores": {
        "1": {"x": 350.5, "y": 250.3},
        "2": {"x": 450.2, "y": 300.1}
    },
    "balas": {
        "5": {
            "x": 400.0,
            "y": 200.0,
            "player_id": 1
        }
    },
    "puntuacion": {
        "1": 0,
        "2": 1
    },
    "estrella": {
        "x": 150.0,
        "y": 400.0
    } | null,
    "jugadores_invencibles": {
        "1": 3.5  // Tiempo restante en segundos
    }
}
```

**Frecuencia**: ~60 veces por segundo (cada 16ms) durante la partida.

**Función**:
```python
async def enviar_estado_a_sala(codigo_sala: str):
    # Prepara el estado completo de la sala
    # Crea un mensaje JSON
    # Envía a todos los websockets en paralelo usando asyncio.gather()
```

### Loop de Actualización de Balas

El servidor tiene un loop dedicado que:

1. **Actualiza posición de balas** según su velocidad
2. **Detecta colisiones**:
   - Con los bordes de la pantalla
   - Con obstáculos (barriles, cactus)
   - Con jugadores (impactos)
3. **Gestiona puntuación** cuando hay impactos
4. **Detecta victoria** (3 impactos = ganador)
5. **Elimina balas** que ya no son válidas
6. **Envía estado actualizado** después de cada ciclo

```python
async def loop_actualizacion_balas():
    while True:
        for codigo_sala, sala in salas.items():
            if sala["estado_partida"] == "jugando":
                if sala["balas"]:
                    await actualizar_balas_sala(codigo_sala)
                await enviar_estado_a_sala(codigo_sala)
        await asyncio.sleep(0.016)  # ~60 FPS
```

### Sistema de Power-ups (Estrellas)

**Loop dedicado**:

```python
async def loop_generar_estrellas():
    while True:
        for codigo_sala, sala in salas.items():
            if sala["estado_partida"] == "jugando":
                # Genera estrella cada 10 segundos si no hay una activa
                # Detecta cuando un jugador la recoge
                # Otorga invencibilidad temporal
        await asyncio.sleep(0.1)  # Revisa cada 100ms
```

---

## Mensajes y Protocolo

Todos los mensajes se envían como **JSON** a través de WebSocket.

### Mensajes Cliente → Servidor

#### 1. `crear_partida`
```json
{
    "tipo": "crear_partida",
    "nombre": "Jugador1"
}
```
**Respuesta**: `asignacion_id`

#### 2. `unirse_partida`
```json
{
    "tipo": "unirse_partida",
    "nombre": "Jugador2",
    "codigo_sala": "ABC123"
}
```
**Respuesta**: `asignacion_id` o `error`

#### 3. `ready`
```json
{
    "tipo": "ready",
    "player_id": 1,
    "listo": true
}
```
**Efecto**: Cambia estado de "listo" del jugador, notifica a todos

#### 4. `iniciar_partida`
```json
{
    "tipo": "iniciar_partida",
    "player_id": 1
}
```
**Validaciones**:
- Solo el host puede iniciar
- Debe haber al menos 2 jugadores
- Todos deben estar listos

**Efecto**: Cambia `estado_partida` a `"jugando"`, envía `start_game` a todos

#### 5. `shoot`
```json
{
    "tipo": "shoot",
    "player_id": 1,
    "direccion": "up"
}
```
**Validaciones**:
- Solo una bala activa por jugador
- Solo si la partida está en curso

**Efecto**: Crea nueva bala en el estado de la sala

#### 6. `update_pos`
```json
{
    "tipo": "update_pos",
    "player_id": 1,
    "x": 350.5,
    "y": 250.3
}
```
**Efecto**: Actualiza posición del jugador en el estado de la sala

### Mensajes Servidor → Cliente

#### 1. `asignacion_id`
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

#### 2. `estado_sala`
```json
{
    "tipo": "estado_sala",
    "estado_partida": "lobby",
    "host_id": 1,
    "codigo_sala": "ABC123",
    "jugadores": {
        "1": {
            "nombre": "Jugador1",
            "listo": true,
            "es_host": true,
            "sprite_index": 1
        }
    }
}
```
**Enviado cuando**: Cambia el estado del lobby (jugador se une, cambia "listo", etc.)

#### 3. `estado`
```json
{
    "tipo": "estado",
    "jugadores": {...},
    "balas": {...},
    "puntuacion": {...},
    "estrella": {...} | null,
    "jugadores_invencibles": {...}
}
```
**Enviado**: ~60 veces por segundo durante la partida

#### 4. `start_game`
```json
{
    "tipo": "start_game",
    "estado_partida": "jugando",
    "puntuacion": {...}
}
```
**Enviado cuando**: El host inicia la partida

#### 5. `game_over`
```json
{
    "tipo": "game_over",
    "ganador": 1,
    "puntuacion": {...},
    "motivo": "abandono" | null
}
```
**Enviado cuando**: Un jugador alcanza 3 impactos o gana por abandono

#### 6. `error`
```json
{
    "tipo": "error",
    "mensaje": "Descripción del error"
}
```

---

## Lógica del Juego

### Sistema de Balas

**Creación**:
- Un jugador dispara → servidor crea bala con velocidad según dirección
- Cada bala tiene un ID único por sala
- Se almacena en `sala["balas"]`

**Actualización**:
```python
bala_info["x"] += bala_info["vx"]
bala_info["y"] += bala_info["vy"]
```

**Colisiones**:

1. **Con bordes**: Si `x < 0` o `x > 800` o `y < 0` o `y > 600` → eliminar
2. **Con obstáculos**: Verifica si la posición de la bala está dentro del rectángulo del obstáculo
3. **Con jugadores**: Calcula distancia, si `dist <= RADIO_IMPACTO` (25px):
   - Incrementa puntuación del atacante
   - Elimina la bala
   - Verifica si hay ganador (3 impactos)

### Sistema de Obstáculos

Los obstáculos son **fijos** y se definen al inicio:

```python
OBSTACULOS = [
    {"tipo": "barril_marron", "x": 400, "y": 300},
    {"tipo": "cactus", "x": 150, "y": 150},
    ...
]
```

**Colisiones con balas**: Rectangulares (comparando coordenadas)

**Colisiones con jugadores**: El cliente las maneja localmente para prevenir movimiento

### Sistema de Power-ups (Estrellas)

**Generación**:
- Cada 10 segundos (si no hay una activa)
- Posición aleatoria que no colisione con obstáculos
- Almacenada en `sala["estrella_actual"]`

**Recogida**:
- El servidor detecta cuando un jugador está cerca (radio de recogida)
- Otorga invencibilidad por 5 segundos
- Almacena `sala["jugadores_invencibles"][player_id] = tiempo_fin`
- Elimina la estrella

**Efecto**:
- Las balas no afectan a jugadores invencibles
- El estado se envía a clientes para mostrar efecto visual

### Sistema de Puntuación y Victoria

- Cada impacto incrementa la puntuación del atacante
- Al alcanzar 3 impactos, el juego termina
- El servidor envía `game_over` a todos con el ganador

---

## Gestión de Desconexiones

### Desconexión de un Jugador No-Host

**Durante Lobby**:
1. Se remueve de todas las estructuras de la sala
2. Se notifica a los demás jugadores (nuevo `estado_sala`)

**Durante Partida**:
1. Se remueve del estado de la sala
2. Se verifica si solo queda **1 jugador**
3. Si solo queda 1 → ese jugador **gana por abandono**
4. Si quedan más → continúa la partida normalmente

### Desconexión del Host

**Durante Lobby**:
- Se elimina toda la sala
- Todos los jugadores son desconectados

**Durante Partida**:
- Si solo queda 1 jugador → ese jugador **gana por abandono**
- Si quedan más jugadores → se elimina la sala (no hay transferencia de host)

### Limpieza

Cuando un jugador se desconecta:
- Se remueve de `sala["jugadores"]`
- Se remueve de `sala["jugadores_info"]`
- Se remueve de `sala["estado"]`
- Se remueve de `sala["jugadores_listos"]`
- Se remueve de `sala["puntuacion"]`
- Se remueve de `sala["jugadores_invencibles"]`
- Se remueve de `websocket_a_sala`

---

## Características Importantes

### 1. Servidor Autoritativo

El servidor **siempre tiene la verdad**. Todas las decisiones importantes se toman en el servidor:
- Colisiones
- Puntuación
- Estado de balas
- Power-ups

### 2. Aislamiento de Salas

Cada sala tiene su propio estado completamente aislado. Dos salas diferentes pueden estar en diferentes fases (lobby vs. jugando) sin afectarse.

### 3. Identificación por WebSocket

Cada conexión WebSocket se mapea a una sala, permitiendo:
- Validar que un mensaje viene del jugador correcto
- Enviar mensajes solo a jugadores de la misma sala
- Limpiar correctamente al desconectarse

### 4. Throttling de Actualizaciones

- **Posiciones**: Máximo cada 50ms (20/segundo)
- **Estado del juego**: ~60 veces/segundo durante partida
- **Estrellas**: Revisión cada 100ms

Esto optimiza el uso de ancho de banda y CPU.

### 5. Manejo de Errores

- Mensajes inválidos se ignoran
- Conexiones cerradas se limpian automáticamente
- Excepciones se capturan para no crashear el servidor

---

## Flujo Completo de una Partida

1. **Jugador A crea sala** → Servidor crea sala, responde con código
2. **Jugador B se une** → Servidor valida código, agrega a sala
3. **Ambos marcan "listo"** → Servidor actualiza estado, notifica a todos
4. **Host inicia partida** → Servidor valida, cambia a "jugando", envía `start_game`
5. **Jugadores se mueven** → Clientes envían `update_pos`, servidor actualiza estado
6. **Jugadores disparan** → Servidor crea balas, las actualiza en loop dedicado
7. **Balas colisionan** → Servidor detecta, actualiza puntuación
8. **Jugador recoge estrella** → Servidor otorga invencibilidad
9. **Alguien llega a 3 impactos** → Servidor detecta, envía `game_over`
10. **Jugadores se desconectan** → Servidor limpia, puede declarar ganador por abandono

---

## Consideraciones de Red

### Latencia

- El servidor actualiza a ~60 FPS
- Los clientes reciben actualizaciones frecuentes para movimiento fluido
- Las posiciones se sincronizan constantemente

### Ancho de Banda

- Mensajes JSON compactos
- Solo se envía estado cambiado
- Throttling previene spam de mensajes

### Escalabilidad

- Cada sala es independiente
- Múltiples salas pueden ejecutarse simultáneamente
- El servidor puede manejar muchos clientes concurrentes (limitado por recursos del sistema)

---

## Seguridad y Validación

- **Validación de player_id**: El servidor verifica que cada mensaje viene del jugador correcto
- **Validación de sala**: Solo se procesan mensajes de jugadores que pertenecen a la sala
- **Validación de estado**: Solo se permiten acciones válidas según el estado actual (ej: no disparar en lobby)
- **Validación de host**: Solo el host puede iniciar partidas

---

## Funciones Principales

### `manejar_cliente(websocket)`
Función principal que maneja una conexión individual. Procesa todos los mensajes del cliente y mantiene la conexión viva.

### `enviar_estado_a_sala(codigo_sala)`
Envía el estado completo del juego a todos los jugadores de una sala.

### `enviar_evento_a_sala(codigo_sala, evento)`
Envía un evento específico (como `game_over`) a todos los jugadores de una sala.

### `actualizar_balas_sala(codigo_sala)`
Actualiza todas las balas de una sala: movimiento, colisiones, puntuación.

### `actualizar_estrellas_sala(codigo_sala)`
Detecta si algún jugador recogió la estrella y otorga invencibilidad.

### `loop_actualizacion_balas()`
Loop asíncrono que actualiza balas y envía estado periódicamente para todas las salas activas.

### `loop_generar_estrellas()`
Loop asíncrono que genera estrellas periódicamente y detecta recogida.

---

## Conclusión

El servidor actúa como el **cerebro** del juego, manteniendo el estado autoritativo y sincronizándolo con todos los clientes. La arquitectura basada en salas permite múltiples partidas simultáneas sin interferencia, y el uso de WebSockets garantiza comunicación en tiempo real con baja latencia.

