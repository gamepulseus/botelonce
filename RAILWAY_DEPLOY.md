# 🚀 Despliegue en Railway

Guía paso a paso para publicar el bot en Railway y que corra 24/7.

---

## 📋 Requisitos previos

1. **Cuenta en Railway** (gratis, te dan $5 de crédito al mes) → https://railway.app
2. **Cuenta en GitHub** (gratis) → https://github.com
3. Tu **API key de API-Football** (ya la tienes)
4. Tu **token de bot de Telegram** (ya lo tienes: `@Eloncetitularbot`)
5. Tu **@canal de Telegram** (ya lo tienes: `@ElOnceTitular`)

---

## 🗂️ Paso 1: Subir el código a GitHub

### Opción A: Crear repo nuevo

1. Entra a https://github.com/new
2. Repository name: `bot-futbol-telegram`
3. Marca **Private** (¡importante! aunque las credenciales van en variables, mejor privado)
4. **NO** marques "Add a README" ni "Add .gitignore" (ya los tenemos)
5. Click **Create repository**

### Opción B: Subir desde tu computadora

```bash
# En tu PC, descomprime el ZIP descargado y entra a la carpeta
cd telegram-football-bot

# Inicializar git
git init
git add .
git commit -m "Bot de fútbol para Railway"

# Conectar con tu repo de GitHub (reemplaza USUARIO por tu username)
git branch -M main
git remote add origin https://github.com/USUARIO/bot-futbol-telegram.git
git push -u origin main
```

> 💡 Si no tienes git instalado, puedes **arrastrar los archivos directamente** en la web de GitHub (entra a tu repo → "uploading an existing file").

---

## 🚂 Paso 2: Conectar Railway con GitHub

1. Entra a https://railway.app y haz login con GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Selecciona tu repo `bot-futbol-telegram`
4. Railway detecta automáticamente el `Dockerfile` o `railway.json` y empieza el build

---

## ⚙️ Paso 3: Configurar variables de entorno

En el dashboard de Railway, ve a **Settings → Variables** y añade estas variables:

### 🔑 Obligatorias (sin estas el bot no arranca)

| Variable | Valor |
|----------|-------|
| `API_FOOTBALL_KEY` | `cbb0f106154c72d158f3de7d4db9f27b` |
| `TELEGRAM_BOT_TOKEN` | `8822719172:AAE_adfmCnxpKBkAtXifH37SE529gHiye70` |
| `TELEGRAM_CHANNEL` | `@ElOnceTitular` |

### 📊 Opcionales (con valores por defecto)

| Variable | Valor por defecto | Para qué sirve |
|----------|-------------------|----------------|
| `LEAGUES` | `39,140,135,78,61` | IDs de ligas a monitorear |
| `POLL_INTERVAL_SECONDS` | `60` | Frecuencia de consulta a la API |
| `TIMEZONE` | `America/Caracas` | Zona horaria para mostrar horarios |
| `LANGUAGE` | `es` | Idioma de los mensajes |
| `LOG_LEVEL` | `INFO` | Nivel de logs (DEBUG/INFO/WARNING/ERROR) |
| `STATE_FILE` | `/data/state.json` | Ruta del estado persistente |

### 🏆 Valor recomendado para LEAGUES (16 ligas)

```
39,140,135,78,61,2,3,848,4,5,7,13,11,71,128,299
```

Copia y pega esto como valor de `LEAGUES` para tener las 5 grandes ligas + Champions + Libertadores + Venezuela, etc.

---

## 💾 Paso 4: Montar volumen para persistencia

Sin esto, el bot perdería el estado en cada redeploy y publicaría eventos duplicados.

1. En Railway, ve a tu servicio → **Settings → Volumes**
2. Click **Add Volume**
3. Mount path: `/data`
4. Click **Add**

Esto crea un volumen persistente donde se guardará `state.json`.

> ⚠️ Si no montas el volumen, en cada redeploy el bot "olvida" qué eventos ya publicó y puede duplicarlos.

---

## ▶️ Paso 5: Primer deploy

1. Railway hará el build automáticamente (1-2 min)
2. Ve a **Deployments** → verás el progreso
3. Cuando termine, en **Logs** verás:
   ```
   2026-07-30 12:00:00 [INFO] bot: === Bot de fútbol iniciando ===
   2026-07-30 12:00:00 [INFO] bot: Ligas: [39, 140, 135, 78, 61, ...]
   2026-07-30 12:00:01 [INFO] telegram_client: Bot conectado: @Eloncetitularbot
   2026-07-30 12:00:02 [INFO] bot: Bot listo. Comenzando loop principal.
   ```
4. En tu canal https://t.me/ElOnceTitular llegará el mensaje de "Bot en línea"

---

## 💰 Costos y plan gratuito

### Plan Hobby ($5/mes, recomendado)
- $5 de crédito gratis al mes
- El bot consume aproximadamente **$3-4/mes** (CPU bajo, RAM ~50MB)
- ✅ 24/7 sin interrupciones
- ✅ Volumen persistente incluido
- ✅ Logs ilimitados

### Plan Trial (gratis, limitado)
- $5 de crédito único (no se renueva)
- ⚠️ Solo dura unas semanas
- Después hay que poner tarjeta

> 💡 **Recomendación**: ponle tarjeta, paga los $5/mes, y tienes 24/7 real sin preocupaciones. Si el bot consume poco (que es el caso), no pagarás más de eso.

---

## 🔧 Operaciones útiles

### Ver logs en vivo
Railway → tu servicio → pestaña **Logs**

### Reiniciar el bot
Railway → tu servicio → **Settings → Redeploy**

### Actualizar código
1. Haz cambios en tu GitHub
2. Railway detecta el push automáticamente y hace redeploy
3. Si no lo detecta: **Settings → Redeploy**

### Cambiar ligas sin tocar código
1. Railway → **Variables** → editar `LEAGUES`
2. Railway hace redeploy automático

### Detener temporalmente
Railway → tu servicio → **Settings → Pause**
Para reanudar: **Resume**

---

## 🩺 Salud del bot

### Diagnóstico rápido
En Railway → **Metrics** deberías ver:
- CPU: <5% (casi siempre idle)
- RAM: 30-80MB
- Network: bajo tráfico saliente (Telegram + API-Football)

### Si el bot no publica nada
1. Revisa **Logs** en busca de errores
2. Verifica que las variables estén bien (especialmente `TELEGRAM_CHANNEL` con la `@`)
3. Verifica que el bot sea admin del canal
4. Usa el comando `python test_dry_run.py` localmente para descartar problemas de API

### Si se cae y no reinicia
Railway reinicia automáticamente hasta 10 veces. Si sigue fallando:
1. Revisa logs
2. Arregla el código
3. Push a GitHub → redeploy automático

---

## 📊 Consumo de API en Railway

Con 16 ligas activas:
- **Sin partidos en vivo**: 1 req/minuto = ~1.440 req/día = **19% del cupo Pro**
- **5 partidos simultáneos**: ~6 req/min = ~540 req en 90 min
- **Día saturado**: máx 4.000 req/día = **53% del cupo**

✅ Plan Pro de 7.500 req/día sobra.

---

## 🆘 Troubleshooting

### Error: `Configuración incompleta`
Falta alguna variable obligatoria. Revisa `API_FOOTBALL_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL`.

### Error: `Telegram error: Forbidden: bot is not a member`
El bot no es admin del canal. Re-añádelo como administrador en Telegram.

### Error: `HTTP 429` desde API-Football
Estás excediendo el cupo. Sube `POLL_INTERVAL_SECONDS` a 90 o 120.

### El bot arranca pero no publica nada
- Verifica que haya partidos en vivo en tus ligas
- Revisa logs: deberías ver `Live fixtures (filtrados): N`
- Si N=0 siempre, quizá las ligas están en off-season (verano europeo)

### Volumen lleno
El `state.json` crece con el tiempo. Cada ~300 fixtures, el bot limpia automáticamente los viejos. Si necesitas resetear:
1. Railway → tu servicio → **Settings → Volumes → Remove**
2. Añade uno nuevo en `/data`
3. Redeploy

---

## ✅ Checklist final

Antes de dar por bueno el deploy, verifica:

- [ ] Repo de GitHub creado (privado recomendado)
- [ ] Railway conectado al repo
- [ ] Variables de entorno configuradas (las 3 obligatorias mínimo)
- [ ] Volumen montado en `/data`
- [ ] Primer deploy exitoso (ver logs)
- [ ] Mensaje "Bot en línea" llegó al canal
- [ ] Con bot en vivo, verificar que detecta fixtures: `Live fixtures (filtrados: N)`
- [ ] Programar reinicio: si quieres que se reinicie cada día, Railway no lo necesita (es 24/7 nativo)

---

## 🎯 Siguiente paso

Una vez desplegado, puedes:
- Modificar código → push a GitHub → Railway redeploya solo
- Cambiar variables → Railway redeploya solo
- Ver métricas y logs en tiempo real desde el dashboard

¡Disfruta tu bot 24/7! ⚽🤖
