# Bot de Telegram — Resultados de Fútbol en Vivo

Bot en Python que consulta la **API-Football v3** cada 60 segundos y publica en un canal de Telegram los eventos en vivo de **16 competiciones** (5 grandes ligas europeas + Champions + Libertadores + Sudamérica + Venezuela): goles, tarjetas, cambios, alineaciones, VAR, inicio/fin de partido y resumen con estadísticas.

---

## 🚀 Despliegue rápido

### Opción A: Railway (24/7 recomendado) 🚂

Lee [`RAILWAY_DEPLOY.md`](./RAILWAY_DEPLOY.md) para la guía completa paso a paso.

Resumen:
1. Sube este proyecto a GitHub (privado)
2. Conecta Railway con tu repo
3. Configura variables: `API_FOOTBALL_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL`
4. Monta un volumen en `/data`
5. ¡Deploy automático!

### Opción B: Local (pruebas)

```bash
cd telegram-football-bot
pip install -r requirements.txt
cp .env.example .env  # edita con tus credenciales
python bot.py
```

---

## 📋 Requisitos

- Python 3.9 o superior (Railway usa 3.11 automáticamente)
- Cuenta activa en [api-football.com](https://www.api-football.com/) con API key
- Un bot de Telegram creado con [@BotFather](https://t.me/BotFather)
- Un canal de Telegram donde el bot sea **administrador**

---

## 🚀 Instalación local (para pruebas)

```bash
# 1. Entrar a la carpeta del bot
cd /home/z/my-project/scripts/telegram-football-bot

# 2. (Opcional) Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Copiar el archivo de ejemplo de configuración
cp .env.example .env

# 5. Editar .env con tus credenciales
nano .env
```

### Contenido del `.env`

```ini
API_FOOTBALL_KEY=tu_api_key_aqui
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhi...
TELEGRAM_CHANNEL=@tu_canal_de_futbol
POLL_INTERVAL_SECONDS=60
LEAGUES=39,140,135,78,61
TIMEZONE=America/Caracas
LANGUAGE=es
LOG_LEVEL=INFO
STATE_FILE=state.json
```

---

## 🔑 Obtener el token de Telegram (paso a paso)

1. Abre Telegram y busca `@BotFather` (verificado, con ✔️ azul).
2. Envía `/newbot`.
3. BotFather te pedirá un **nombre** (ej: `Bot de Fútbol En Vivo`).
4. Luego un **username** que termine en `bot` (ej: `futbol_en_vivo_bot`).
5. BotFather te responde con el token en formato `123456789:ABCdefGhi...`.
6. Cópialo y pégalo en tu `.env` como `TELEGRAM_BOT_TOKEN`.

---

## 📺 Crear el canal y añadir el bot como administrador

1. En Telegram, pulsa el icono de lápiz → **Nuevo Canal**.
2. Ponle nombre, descripción y foto.
3. Elige **Canal Público** y define un @username (ej: `@resultados_en_vivo`).
4. Una vez creado, entra al canal → **Administrar Canal** → **Administradores** → **Añadir administrador**.
5. Busca el username de tu bot y añádelo con permiso para **Publicar mensajes**.
6. En tu `.env`, configura `TELEGRAM_CHANNEL=@resultados_en_vivo` (con la `@`).

> Si tu canal es privado, en lugar de `@username` debes usar el ID numérico (empieza por `-100...`). Para obtenerlo: añade al canal un bot como `@getidsbot`, envíale un mensaje reenviado desde el canal y te dará el ID.

---

## ▶️ Ejecutar el bot

```bash
python bot.py
```

Verás en consola algo así:

```
2026-07-30 15:50:00 [INFO] bot: === Bot de fútbol iniciando ===
2026-07-30 15:50:00 [INFO] bot: Ligas: [39, 140, 135, 78, 61]
2026-07-30 15:50:00 [INFO] bot: Poll interval: 60s
2026-07-30 15:50:00 [INFO] bot: Canal Telegram: @resultados_en_vivo
2026-07-30 15:50:01 [INFO] telegram_client: Bot conectado: @futbol_en_vivo_bot
2026-07-30 15:50:02 [INFO] bot: Bot listo. Comenzando loop principal.
```

En el canal recibirá un mensaje de prueba:

> ✅ **Bot de fútbol en línea**
>
> El bot se ha iniciado correctamente y publicará eventos en vivo aquí.

Para detener: `Ctrl+C`.

---

## 🧪 Tests sin publicar a Telegram

### Smoke test (verifica API + formateo)

```bash
python test_dry_run.py
```

### Test con partido histórico real

```bash
python test_historical.py
```

Muestra cómo se verían todos los tipos de mensajes (inicio, gol, tarjeta, cambio, fin) usando el partido **Villarreal 5-1 Atlético de Madrid** como ejemplo.

---

## 📂 Estructura del proyecto

```
telegram-football-bot/
├── bot.py              # Script principal (entry point)
├── config.py           # Carga .env y define constantes
├── api_client.py       # Cliente HTTP de API-Football v3
├── telegram_client.py  # Cliente de la Bot API de Telegram
├── formatter.py        # Generación de mensajes con HTML y emojis
├── state.py            # Persistencia de estado en JSON
├── test_dry_run.py     # Smoke test (no publica a Telegram)
├── test_historical.py  # Test con partido real histórico
├── requirements.txt    # Dependencias Python
├── .env.example        # Plantilla de configuración
├── .env                # Tu configuración (no subir a git)
├── state.json          # Estado persistido (se crea solo)
└── README.md           # Este archivo
```

---

## ⚙️ Configuración avanzada

### Cambiar ligas

Edita `LEAGUES` en `.env`. IDs comunes:

| ID  | Liga                     |
|-----|--------------------------|
| 39  | Premier League (Inglaterra) |
| 140 | La Liga (España)         |
| 135 | Serie A (Italia)         |
| 78  | Bundesliga (Alemania)    |
| 61  | Ligue 1 (Francia)        |
| 2   | UEFA Champions League    |
| 3   | UEFA Europa League       |
| 13  | Copa Libertadores        |
| 11  | Copa Sudamericana        |
| 253 | MLS (EE. UU.)            |
| 262 | Liga MX (México)         |

Ejemplo para incluir Champions y Libertadores:
```ini
LEAGUES=39,140,135,78,61,2,13
```

### Cambiar frecuencia de polling

```ini
POLL_INTERVAL_SECONDS=30   # más rápido, consume más cuota
POLL_INTERVAL_SECONDS=120  # más lento, ahorra cuota
```

### Consumo de cuota API (plan Pro: 7500 requests/día)

Por cada minuto con un partido en vivo:
- 1 request para listar partidos en vivo (`/fixtures?live=all`)
- 1 request por partido activo para obtener eventos (`/fixtures/events`)

Estimación con 5 partidos simultáneos en vivo durante 2 horas:
- 120 min × (1 + 5) = **720 requests**

Con plan Pro tienes margen amplio. Si tu plan es Free (100 req/día), sube `POLL_INTERVAL_SECONDS` a 300 o reduce ligas.

---

## 🔧 Solución de problemas

### `Configuración incompleta`
Revisa que todas las variables de `.env` tengan valores válidos, especialmente `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHANNEL`.

### `Telegram error: chat not found`
El bot no es administrador del canal, o el `@username` del canal está mal escrito. Vuelve a los pasos de "Crear el canal".

### `Telegram error: Forbidden: bot is not a member of the channel supergroup chat`
Añade el bot al canal **como administrador** (no basta con invitarlo como miembro).

### `HTTP 429` desde API-Football
Has excedido la cuota diaria. Sube `POLL_INTERVAL_SECONDS` o reduce `LEAGUES`.

### El bot no detecta partidos en vivo
1. Verifica que haya partidos en vivo (la temporada europea va de agosto a mayo).
2. Ejecuta `python test_dry_run.py` para ver qué devuelve la API.

### Los eventos se duplican
El bot usa `state.json` para recordar eventos ya publicados. Si lo borras, el bot volverá a publicar eventos pasados la próxima vez que consulte un partido.

---

## 🔒 Seguridad

- **Nunca** subas tu `.env` a GitHub. Añádelo a `.gitignore`.
- Si publicaste tu API key en algún chat, regenérala desde el panel de api-football.com.
- El token del bot de Telegram es equivalente a una contraseña: trátalo como tal.

---

## 📝 Próximas mejoras sugeridas

- Soporte para Docker / systemd (despliegue en VPS)
- Comandos interactivos del bot (`/proximos`, `/live`, `/liga`)
- Estadísticas del partido (posesión, tiros, córners) al final
- Notificación previa (15 min antes del inicio)
- Soporte multi-idioma (en/es/pt)
- Filtrado por equipos favoritos en lugar de por ligas

---

## 📜 Licencia

Uso personal y educativo. Respeta los términos de servicio de API-Football y Telegram.
