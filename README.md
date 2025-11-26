# Proyecto 2 Redes – Cowboy Battle

Proyecto de redes en Python que implementa un servidor autoritativo y cliente usando WebSockets para comunicación en tiempo real.

## Requisitos

- Python 3.10 o superior
- pip (gestor de paquetes de Python)

## Configuración del Entorno Virtual

### Windows

1. Crear el entorno virtual:
```bash
python -m venv venv
```

2. Activar el entorno virtual:
```bash
venv\Scripts\activate
```

## Instalación de Dependencias

Una vez activado el entorno virtual, instala las dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

### Servidor

Para iniciar el servidor, ejecuta:

```bash
python servidor/server.py
```

El servidor escuchará en `0.0.0.0:9000`, lo que permite conexiones desde cualquier interfaz de red.

### Cliente

En otra terminal (con el entorno virtual activado), ejecuta:

```bash
python cliente/client.py
```

El cliente se conectará a `localhost:9000` por defecto.

## Pruebas entre Dos Computadoras

Para probar la comunicación entre dos computadoras diferentes (por ejemplo, tu computadora y la de Camila):

1. **En la computadora del servidor:**
   - Ejecuta el servidor: `python servidor/server.py`
   - Averigua la IP de la computadora:
     - Windows: `ipconfig` (busca "IPv4 Address")
     - Linux/macOS: `ifconfig` o `ip addr`
   - Si usas Radmin VPN u otra VPN, usa la IP asignada por la VPN

2. **En la computadora del cliente:**
   - Edita `cliente/client.py` y cambia la línea:
     ```python
     uri = "ws://localhost:9000"
     ```
     Por:
     ```python
     uri = "ws://[IP_DEL_SERVIDOR]:9000"
     ```
     Reemplaza `[IP_DEL_SERVIDOR]` con la IP real (por ejemplo: `ws://192.168.1.100:9000`)

3. **Asegúrate de que:**
   - El firewall permita conexiones en el puerto 9000
   - Ambas computadoras estén en la misma red o VPN

## Estructura del Proyecto

```
Proyecto-2-Redes/
│
├── servidor/
│   └── server.py          # Servidor WebSocket autoritativo
│
├── cliente/
│   └── client.py          # Cliente WebSocket
│
├── requirements.txt       # Dependencias del proyecto
└── README.md             # Este archivo
```

## Funcionalidad Actual

- **Servidor:**
  - Acepta múltiples conexiones de clientes
  - Envía mensaje de bienvenida a cada cliente que se conecta
  - Reenvía (hace eco) todos los mensajes recibidos a todos los clientes conectados
  - Maneja desconexiones limpiamente

- **Cliente:**
  - Se conecta al servidor
  - Envía un mensaje de saludo al conectarse
  - Escucha y muestra mensajes recibidos del servidor
  - Maneja desconexiones limpiamente

## Próximos Pasos

- Integración con Pygame para gráficos
- Implementación de la lógica del juego Cowboy Battle
- Sistema de autenticación de jugadores
- Sincronización de estado del juego

