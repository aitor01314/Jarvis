# JARVIS — Arquitectura de una Plataforma de IA Personal

> Documento de diseño v1.0 — antes de escribir una sola línea de código.
> Horizonte: producto profesional mantenible durante 10 años.

---

## Índice

1. [Filosofía y principios de diseño](#1-filosofía-y-principios-de-diseño)
2. [Visión general de la arquitectura](#2-visión-general-de-la-arquitectura)
3. [El núcleo (Kernel)](#3-el-núcleo-kernel)
4. [Router Inteligente y Cerebros](#4-router-inteligente-y-cerebros)
5. [Sistema de agentes](#5-sistema-de-agentes)
6. [Sistema de herramientas (plugins) y MCP](#6-sistema-de-herramientas-plugins-y-mcp)
7. [Sistema de memoria](#7-sistema-de-memoria)
8. [Control del sistema operativo](#8-control-del-sistema-operativo)
9. [Voz: wake word, STT, TTS](#9-voz-wake-word-stt-tts)
10. [Interfaz HUD estilo Iron Man](#10-interfaz-hud-estilo-iron-man)
11. [Automatización y workflows](#11-automatización-y-workflows)
12. [Bus de eventos y comunicación interna](#12-bus-de-eventos-y-comunicación-interna)
13. [Persistencia de datos](#13-persistencia-de-datos)
14. [Seguridad y permisos](#14-seguridad-y-permisos)
15. [Escalado multi-dispositivo](#15-escalado-multi-dispositivo)
16. [Estructura de repositorio propuesta](#16-estructura-de-repositorio-propuesta)
17. [Hoja de ruta: MVP → Beta → 1.0 → Futuro](#17-hoja-de-ruta)
18. [Riesgos y decisiones abiertas](#18-riesgos-y-decisiones-abiertas)

---

## 1. Filosofía y principios de diseño

Reglas que gobiernan TODAS las decisiones de este documento:

1. **El núcleo no sabe nada de modelos, agentes ni herramientas concretas.** Solo conoce interfaces (puertos). Todo lo concreto es un adaptador reemplazable. Esto es Clean Architecture / Hexagonal aplicada al problema: si dentro de 3 años Claude 7 o un modelo local supera a todo lo actual, se cambia un adaptador, no la plataforma.
2. **Todo es un evento.** Cada acción (usuario habla, agente termina, CPU sube, tarea falla) es un evento en un bus. La UI, los logs, la memoria y las automatizaciones son *consumidores* de ese bus. Así se desacopla todo de todo.
3. **Contratos primero.** Cada módulo se define por su contrato (schemas Pydantic / JSON Schema versionados), no por su implementación.
4. **Local-first, cloud-optional.** JARVIS debe funcionar sin internet (modelos Ollama, STT local) con degradación elegante, y mejorar cuando hay nube.
5. **Seguridad por capacidades.** Ningún agente/plugin tiene acceso a nada que no declare y que el usuario no haya concedido.
6. **DDD donde aporta:** dominios claros (Conversación, Memoria, Tareas, Agentes, Dispositivos), no DDD ceremonial en módulos triviales.

---

## 2. Visión general de la arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│  CAPA DE PRESENTACIÓN                                            │
│  HUD Desktop (Tauri+React)   ·   Chat   ·   Voz   ·   API REST   │
└───────────────▲──────────────────────────────▲───────────────────┘
                │ WebSocket (eventos)          │ HTTP (comandos)
┌───────────────┴──────────────────────────────┴───────────────────┐
│  JARVIS CORE (FastAPI, Python)                                   │
│                                                                  │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Orquestador│─▶│ Router       │─▶│ Cerebros (Brains)        │  │
│  │ (sesiones, │  │ Inteligente  │  │ conversación · código ·  │  │
│  │  intents,  │  └──────────────┘  │ mates · creativo ·       │  │
│  │  planes)   │                    │ visual · voz · autónomo  │  │
│  └─────┬──────┘                    └────────────┬─────────────┘  │
│        │                                        │ (proveedores)  │
│  ┌─────▼──────────┐   ┌─────────────┐   ┌───────▼─────────────┐  │
│  │ Registro de    │   │ Sistema de  │   │ Adaptadores LLM     │  │
│  │ Agentes        │   │ Memoria     │   │ Claude·GPT·Gemini·  │  │
│  │ (procesos      │   │ (6 niveles) │   │ Ollama (local)      │  │
│  │  independ.)    │   └─────────────┘   └─────────────────────┘  │
│  └─────┬──────────┘                                              │
│        │           ┌──────────────────────────────────────────┐  │
│  ┌─────▼───────┐   │ BUS DE EVENTOS (Redis Streams)           │  │
│  │ Registro de │   │ + Cola de tareas (arq / Celery)          │  │
│  │ Herramientas│   └──────────────────────────────────────────┘  │
│  │ (plugins+MCP)│                                                │
│  └─────────────┘                                                 │
└───────┬───────────────────────────────────────────┬──────────────┘
        │ gRPC/WS                                   │
┌───────▼───────────┐                       ┌───────▼──────────────┐
│ AGENTES (procesos │                       │ DAEMON DE SISTEMA    │
│ independientes):  │                       │ (control SO): ratón, │
│ correo, calendario│                       │ teclado, ventanas,   │
│ github, spotify,  │                       │ pantalla, OCR, audio,│
│ docker, youtube…  │                       │ procesos, hardware   │
└───────────────────┘                       └──────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────────────┐
│ PERSISTENCIA: SQLite (config) · PostgreSQL (datos) ·             │
│ Qdrant (memoria vectorial) · Redis (colas/estado efímero)        │
└──────────────────────────────────────────────────────────────────┘
```

**Decisión clave: monolito modular, no microservicios (al principio).**
- **Por qué:** un solo proceso core con módulos desacoplados por interfaces + agentes como procesos externos. Los microservicios puros añadirían latencia, complejidad operativa y fricción de desarrollo enorme para un producto de una persona.
- **Alternativas:** microservicios completos (Kubernetes) — sobredimensionado; script monolítico — imposible de mantener 10 años.
- **Ventajas:** despliegue simple, refactor fácil, límites claros por módulo. **Inconvenientes:** hay que ser disciplinado con las fronteras (se mitiga con imports prohibidos entre módulos salvo por interfaces, verificado con lint como `import-linter`).
- **Multi-dispositivo:** como TODO pasa por el bus de eventos y contratos serializables, cualquier módulo puede extraerse a otro proceso/máquina más adelante sin reescritura (el monolito modular es la vía probada hacia microservicios *cuando hagan falta*).

---

## 3. El núcleo (Kernel)

Responsabilidades del core (y solo estas):

| Módulo | Responsabilidad |
|---|---|
| **Orquestador** | Recibe entradas (voz/chat/API/automatización), mantiene la sesión, decide: ¿respuesta directa, herramienta, agente, o plan autónomo? |
| **Router Inteligente** | Elige cerebro + modelo concreto para cada paso (§4) |
| **Registro de Agentes** | Ciclo de vida, salud, permisos y descubrimiento de agentes (§5) |
| **Registro de Herramientas** | Carga de plugins y servidores MCP, catálogo de acciones (§6) |
| **Gestor de Memoria** | API única de lectura/escritura de memoria (§7) |
| **Gestor de Tareas** | Cola, prioridades, reintentos, cancelación |
| **Gestor de Permisos** | Concesión/auditoría de capacidades |
| **Bus de Eventos** | Publicación/suscripción de todos los eventos (§12) |

**Lenguaje: Python 3.12+ con FastAPI.**
- **Por qué:** ecosistema IA sin rival (SDKs de todos los proveedores, Whisper, Playwright, OCR), FastAPI es async, tipado (Pydantic) y con WebSockets nativos.
- **Alternativas:** Node/TypeScript (buen ecosistema pero peor en IA/audio/visión), Rust (rendimiento, pero velocidad de desarrollo 5x menor; se usará vía Tauri donde importa), Go (bueno para daemons, débil en IA).
- **Inconvenientes de Python:** GIL/rendimiento — se mitiga porque el trabajo pesado es I/O (llamadas a LLM) y lo intensivo (STT, OCR) corre en procesos separados.
- **Escalado:** Python corre en PC, servidor, Raspberry Pi y nube. En móvil no corre el core: el móvil será *cliente* del core (§15).

---

## 4. Router Inteligente y Cerebros

### 4.1 Concepto

Un **Cerebro** = rol + política de selección de modelos + prompt de sistema + herramientas permitidas. Un **Proveedor** = adaptador a una API concreta (Anthropic, OpenAI, Google, Ollama). Los cerebros NO están casados con proveedores: cada cerebro tiene una lista ordenada de modelos con fallback.

```yaml
# brains.yaml — configuración, no código
brains:
  conversational:
    models: [claude-sonnet, gemini-flash, gpt-4o, ollama/llama3]
    tools: [memory, web_search]
  coding:
    models: [claude-opus, gpt-5, gemini-pro]
    tools: [filesystem, terminal, github]
  math:
    models: [gpt-5, claude-opus]
    features: [code_interpreter]
  creative:
    models: [claude-opus, gemini-pro]
  visual:
    models: [gemini-pro-vision, gpt-4o, ollama/llava]
  voice:
    stt: [whisper-local, azure-speech]
    tts: [azure-speech, piper-local]
  autonomous:
    models: [claude-opus]
    max_steps: 50
```

### 4.2 El Router

Pipeline de decisión en dos etapas:

1. **Clasificación rápida** (latencia < 300 ms): un modelo pequeño y barato (Gemini Flash u Ollama local) clasifica la entrada → `{intent, brain, complejidad, urgencia, ¿requiere_agente?, ¿requiere_plan?}`. Reglas deterministas por delante para casos obvios ("abre X" → daemon SO directamente, sin LLM).
2. **Selección de modelo** dentro del cerebro según: complejidad estimada, coste, latencia requerida (voz exige rapidez), disponibilidad (¿hay internet?, ¿API caída?) y presupuesto diario configurable.

- **Por qué así:** un clasificador pequeño delante es el patrón estándar (mixture-of-experts a nivel de aplicación); barato, rápido, y sus errores son recuperables (un cerebro puede re-enrutar).
- **Alternativas:** (a) que un modelo grande decida siempre — caro y lento; (b) reglas por palabras clave — frágil; (c) frameworks tipo LangChain/LlamaIndex routing — acoplan tu núcleo a sus abstracciones, que cambian cada 6 meses. **Decisión: no usar LangChain en el núcleo.** Los SDKs oficiales de cada proveedor + una interfaz propia `LLMProvider` de ~200 líneas dan control total y cero deuda de framework.
- **Escalado:** el router es puro (entrada→decisión), sin estado; se puede replicar en cualquier dispositivo.

### 4.3 Interfaz de proveedor (contrato estable a 10 años)

```python
class LLMProvider(Protocol):
    async def complete(self, req: CompletionRequest) -> CompletionResponse: ...
    async def stream(self, req: CompletionRequest) -> AsyncIterator[Delta]: ...
    def capabilities(self) -> ModelCapabilities  # visión, tools, contexto, coste
```

Añadir un modelo nuevo = un archivo nuevo + una entrada en YAML. Nada más cambia.

### 4.4 Cerebro Autónomo

Es el único cerebro con bucle propio (plan → ejecutar → observar → revisar):
- Descompone objetivos en un **grafo de subtareas** (no lista plana: permite paralelismo y dependencias).
- Cada subtarea se re-enruta por el Router (una subtarea de código va al cerebro de código).
- Checkpoints persistentes en PostgreSQL: si JARVIS se reinicia a mitad de una tarea de 2 horas, retoma.
- Límites duros: máx. pasos, máx. coste, y **puntos de confirmación humana** para acciones irreversibles (enviar correo, borrar archivos, publicar vídeo).

---

## 5. Sistema de agentes

### 5.1 Modelo de ejecución

Cada agente = **proceso independiente** que se conecta al core por WebSocket/gRPC y se registra con un **manifiesto**:

```yaml
# agent.yaml
name: gmail
version: 1.2.0
capabilities: [read_email, send_email, summarize_inbox]
permissions:
  - network: ["gmail.googleapis.com"]
  - secrets: ["GMAIL_OAUTH"]
tools: [gmail.search, gmail.send, gmail.label]
memory: private        # namespace propio en la memoria
health_check: /health
```

- **Por qué procesos independientes:** aislamiento de fallos (si el agente de WhatsApp crashea, JARVIS sigue), permisos reales a nivel de SO, actualización en caliente, y pueden estar escritos en cualquier lenguaje (solo importa el protocolo).
- **Alternativas:** (a) plugins in-process (rápidos pero un plugin malo tumba todo y hereda todos los permisos); (b) contenedores Docker por agente (aislamiento máximo; **se adopta como opción** para agentes de servidor, pero no obligatorio en el PC del usuario por fricción).
- **Inconvenientes:** más RAM y complejidad de IPC. Mitigación: agentes ligeros arrancan bajo demanda y se duermen tras inactividad (como systemd socket activation).
- **Escalado multi-dispositivo:** este es el mayor beneficio — un agente puede correr EN OTRA MÁQUINA (el agente `nas` corre en el NAS, el agente `servidor` en el servidor) y conectarse al mismo core por el mismo protocolo. La arquitectura de agentes-como-procesos-remotos te da distribución gratis.

### 5.2 Cada agente tiene

- **Capacidades** (qué sabe hacer, en lenguaje natural + schema — el Router las usa para delegar).
- **Permisos** (declarados en manifiesto, concedidos por el usuario, auditados).
- **Herramientas** (acciones invocables con JSON Schema).
- **Estado** (idle / busy / error / sleeping, publicado al bus → visible en el HUD).
- **Memoria propia** (namespace aislado en la memoria central; no lee la de otros).
- **Logs** (estructurados, JSON, al bus → HUD y archivo).

### 5.3 Protocolo agente ↔ core

Mensajes JSON versionados sobre WebSocket: `register`, `heartbeat`, `task.assign`, `task.progress`, `task.result`, `event.emit`, `memory.read/write`, `permission.request`. Se documenta como spec pública desde el día 1 → cualquiera (o el propio JARVIS) puede escribir agentes nuevos.

---

## 6. Sistema de herramientas (plugins) y MCP

**Decisión: MCP (Model Context Protocol) como formato nativo de herramienta.**

- **Por qué:** es el estándar emergente respaldado por Anthropic/OpenAI/Google; ya existen cientos de servidores MCP (GitHub, Drive, Slack, Postgres, Playwright…) que JARVIS obtiene *gratis*; y desacopla herramientas de modelos exactamente como quieres.
- **Alternativas:** formato de plugin propio (control total pero ecosistema cero); OpenAPI-as-tools (bueno para APIs web, malo para herramientas locales). **Solución híbrida:** el Registro de Herramientas habla MCP hacia fuera y expone un contrato interno único; un plugin propio es simplemente un servidor MCP con un `plugin.yaml` extra (permisos + dependencias + UI).
- **Inconveniente:** MCP aún evoluciona → se aísla tras una interfaz interna `ToolProvider` para absorber cambios de la spec.
- **Escalado:** los servidores MCP pueden ser remotos por diseño (SSE/HTTP) → herramientas en otras máquinas sin trabajo extra.

Instalación de plugin: `jarvis plugin install <ruta|url>` → valida manifiesto → sandbox → solicita permisos al usuario → aparece en el catálogo del Router.

---

## 7. Sistema de memoria

Seis niveles, una sola API (`MemoryManager`), backends distintos por nivel:

| Nivel | Contenido | Backend | TTL |
|---|---|---|---|
| **Inmediata** | Ventana de trabajo del turno actual | RAM (proceso) | minutos |
| **Conversación** | Historial por sesión, resúmenes progresivos | PostgreSQL | días–meses |
| **Usuario** | Preferencias, hechos ("Aitor usa VSCode", "responde en español") | PostgreSQL (estructurada) | permanente |
| **Proyectos** | Estado, decisiones y contexto por proyecto | PostgreSQL + Qdrant | vida del proyecto |
| **Vectorial** | Embeddings de todo lo anterior + documentos | **Qdrant** | según origen |
| **Permanente** | Hechos consolidados, identidad de JARVIS | PostgreSQL, backup versionado | para siempre |

- **Qdrant vs Chroma:** Qdrant. Es un servidor real (Rust) con filtrado por payload, cuantización, snapshots y modo distribuido — apto para 10 años y multi-dispositivo. Chroma es más simple de embeber (bueno para prototipos) pero más débil operativamente. Inconveniente de Qdrant: un contenedor más que ejecutar (trivial con Docker Compose).
- **Consolidación automática ("qué guardar y qué olvidar"):** un trabajo nocturno (cerebro conversacional en modo barato) revisa las conversaciones del día → extrae hechos nuevos → los puntúa (relevancia, novedad, frecuencia) → promociona a memoria de usuario/permanente o deja decaer. Patrón inspirado en *Generative Agents* (memoria episódica → reflexión → memoria semántica), que es también la línea de Fable/Showrunner.
- **Alternativas a construirlo:** servicios tipo Mem0/Zep — aceleran pero acoplan un componente crítico a un tercero; la memoria es el activo más valioso de JARVIS y debe ser tuya. Se puede adoptar su *diseño* sin adoptar su dependencia.
- **Escalado:** PostgreSQL y Qdrant se mueven a un servidor doméstico/nube cuando haya varios dispositivos → todos los clientes comparten la misma memoria (JARVIS "te recuerda" igual desde el móvil que desde el PC).

---

## 8. Control del sistema operativo

**Daemon de Sistema**: proceso separado con los privilegios de SO, que expone acciones tipadas al core. El core NUNCA toca el SO directamente.

Capas (de más fiable a más general):

1. **APIs nativas** (preferidas siempre que existan): Windows → `pywin32`/WinRT (ventanas, portapapeles, notificaciones, procesos); `psutil`/`pynvml` (CPU/RAM/GPU); COM/UI Automation (**UIA**) para leer y manipular controles de aplicaciones *sin* visión.
2. **Automatización de navegador**: **Playwright** (web es el 60 % de los casos de uso: correo web, YouTube Studio, redes).
3. **Control humano-simulado**: ratón/teclado (`pynput`), captura de pantalla + **OCR** (RapidOCR/Tesseract local) + cerebro visual para "usar cualquier app como un humano" — el último recurso, porque es lento y frágil.

- **Por qué esta jerarquía:** los agentes "computer-use" puros (solo visión+clic) son espectaculares pero lentos y poco fiables; UIA/APIs son deterministas. La regla: *API si existe, UIA si no, visión como último recurso*.
- **Alternativas:** usar solo computer-use de Anthropic/OpenAI (dependencia total de nube + coste por cada clic); AutoHotkey (no integrable limpiamente).
- **Escalado:** el daemon es *por dispositivo*. En multi-dispositivo, cada máquina ejecuta su daemon y el core enruta "abre VSCode en el PC del salón" al daemon correspondiente. Este es el motivo de separarlo del core desde el día 1.
- **Seguridad:** toda acción del daemon queda auditada; las destructivas requieren confirmación (configurable por acción).

---

## 9. Voz: wake word, STT, TTS

Pipeline siempre-activo (proceso propio, no bloquea el core):

```
micrófono → VAD (Silero) → Wake word ("Jarvis") → grabación hasta silencio
→ STT → texto → Orquestador → respuesta → TTS → altavoces → volver a espera
```

| Componente | Elección | Por qué | Alternativas |
|---|---|---|---|
| Wake word | **openWakeWord** (local, gratis, modelo entrenable "Jarvis") | privacidad, sin coste, latencia ~0 | Porcupine (mejor precisión, licencia de pago), Snowboy (muerto) |
| VAD | **Silero VAD** | estándar de facto, ligero | WebRTC VAD (peor calidad) |
| STT | **faster-whisper local** (GPU) con fallback **Azure Speech** | privacidad + funciona offline; Azure para máquinas sin GPU y streaming largo | Whisper API OpenAI, Deepgram |
| TTS | **Azure Speech (neural)** para calidad "JARVIS" + **Piper** local como fallback offline | Azure tiene las voces más naturales y SSML; Piper corre hasta en una Raspberry Pi | ElevenLabs (mejor voz, más caro), Coqui (mantenimiento incierto) |

- **Conversación continua:** tras responder, ventana de escucha de N segundos sin wake word (como Alexa "follow-up mode"). Interrumpible: si hablas mientras JARVIS habla, se calla (barge-in vía VAD).
- **Escalado:** el pipeline de voz es *cliente*: puede correr en una Raspberry Pi con micrófono en cada habitación, enviando texto al core central — arquitectura idéntica a los satélites de Home Assistant/Wyoming.

---

## 10. Interfaz HUD estilo Iron Man

**Decisión: Tauri 2 + React + TypeScript** (no Electron).

- **Por qué Tauri:** binario de ~10 MB vs ~150 MB, mucha menos RAM (importante: JARVIS estará SIEMPRE abierto), backend Rust útil para overlays/transparencia/always-on-top nativos, y soporta móvil (iOS/Android) en Tauri 2 → misma base de código para el cliente móvil futuro.
- **Alternativas:** Electron (más maduro, más ejemplos, pero pesado para una app residente 24/7); web pura en navegador (sin overlays ni integración de bandeja). **Inconveniente de Tauri:** usa el webview del SO (WebView2 en Windows — perfectamente capaz para esta UI).
- **Stack de la UI:** React + TypeScript + **Zustand** (estado) + **framer-motion** (animaciones) + **SVG/Canvas propios** para los anillos/paneles HUD (las librerías de gráficos genéricas no dan la estética JARVIS; los medidores circulares se hacen a mano en SVG, que además es barato de animar) + **ECharts** para gráficos de series (CPU/RAM históricos) + **tokens de diseño**: fondo #0a0a0f, acento naranja #ff8c1a, tipografía tipo Rajdhani/Orbitron, glow con `drop-shadow`.

**Toda la UI es un consumidor del bus de eventos** (WebSocket). No pide datos: los recibe. Paneles:

- Estado del sistema (anillos CPU/RAM/GPU en tiempo real, desde el daemon).
- Modelo activo + indicador "pensando" (tokens/seg. en streaming).
- Agentes: cuáles corren, estado, tarea actual.
- Cola de tareas y grafo del plan autónomo en curso.
- Chat con historial y memoria.
- Onda de micrófono / estado de voz (espera / escuchando / hablando).
- Consola de logs en vivo (filtrable por agente/nivel).
- Herramientas abiertas y permisos concedidos.

---

## 11. Automatización y workflows

Motor propio, declarativo:

```yaml
# workflows/manana.yaml
name: rutina_manana
trigger: { schedule: "0 7 * * MON-FRI" }
steps:
  - agent: gmail      action: summarize_inbox
  - brain: conversational  action: resumir_noticias
  - agent: calendar   action: today
  - agent: server     action: health_check
  - notify: { if: incidencias, via: voz+hud }
```

- **Triggers:** cron, eventos del bus ("cuando llegue un correo de X"), webhooks, comandos de voz ("Jarvis, ejecuta el pipeline de YouTube").
- **Por qué motor propio y no n8n/Node-RED:** los workflows deben poder invocar cerebros, agentes y memoria con contexto — un motor externo lo convertiría en integración permanente y frágil. n8n queda como *agente opcional* para quien ya lo use. Alternativa considerada: Temporal (durabilidad excelente, pero un clúster entero para un asistente personal es demasiado; sus ideas — workflows reanudables con checkpoints — se adoptan en el diseño).
- Los workflows complejos ("genera un vídeo de YouTube y publícalo") son simplemente **objetivos entregados al Cerebro Autónomo** con plantilla previa — lo declarativo para lo repetible, lo autónomo para lo variable.

---

## 12. Bus de eventos y comunicación interna

**Decisión: Redis (Streams + pub/sub) como bus, `arq` como cola de tareas.**

- **Por qué Redis Streams:** persistencia de eventos (la UI que se reconecta puede reproducir lo perdido), grupos de consumidores, ya está en tu stack para colas, huella mínima (corre en una Raspberry Pi).
- **Alternativas:** NATS (excelente y ligero, candidato serio si algún día molesta Redis — la interfaz `EventBus` interna lo permite), Kafka/RabbitMQ (sobredimensionados), bus in-process puro (no sobrevive a multi-proceso ni multi-dispositivo).
- **Taxonomía de eventos versionada:** `voice.wake`, `chat.message`, `router.decision`, `brain.thinking`, `agent.task.progress`, `system.cpu`, `memory.consolidated`, `workflow.step.done`… Todo evento lleva `schema_version`.
- **Escalado:** con Redis accesible en red, cualquier dispositivo se suscribe al mismo bus → el HUD del móvil ve lo mismo que el del PC en tiempo real.

## 13. Persistencia de datos

| Almacén | Uso | Justificación |
|---|---|---|
| **SQLite** | Config local del dispositivo, caché | cero administración, por-dispositivo |
| **PostgreSQL** | Conversaciones, memoria, tareas, auditoría, workflows | fiabilidad probada a décadas, JSONB para flexibilidad, se muda a servidor/nube sin cambiar código (misma URL) |
| **Qdrant** | Vectores | §7 |
| **Redis** | Colas, estado efímero, bus | §12 |

Todo bajo **Docker Compose** (perfil `jarvis-infra`). Migraciones con Alembic desde el día 1. Backups automáticos (el agente `backup` es de los primeros).

## 14. Seguridad y permisos

- **Modelo de capacidades:** cada agente/plugin declara permisos granulares (`fs:read:~/Documentos`, `net:gmail.googleapis.com`, `os:keyboard`); el usuario concede una vez; todo queda auditado en PostgreSQL.
- **Secretos:** en Windows Credential Manager/keyring (nunca en YAML ni en la BD). Los agentes reciben secretos por referencia en tiempo de ejecución.
- **Niveles de riesgo por acción:** `safe` (leer pantalla) / `notify` (abrir app) / `confirm` (enviar correo, publicar) / `forbidden` sin desbloqueo explícito (borrar masivo, pagos).
- **Sandbox:** plugins de terceros corren con permisos mínimos; opción Docker para los de servidor.
- **Multi-dispositivo:** autenticación mutua core↔daemon/agentes remotos con tokens por dispositivo (mTLS o similar) desde que existan dos máquinas.

## 15. Escalado multi-dispositivo

La arquitectura ya lo prepara; el camino es:

1. **Hoy (1 PC):** todo en local. Core+infra en Docker, HUD y daemon nativos.
2. **Core en servidor doméstico/NAS:** se mueven core+PostgreSQL+Qdrant+Redis al servidor; el PC conserva HUD + daemon + pipeline de voz. Cambio: URLs en config. Cero cambio de código — esta es la prueba de fuego del diseño.
3. **Satélites:** Raspberry Pi con micro/altavoz por habitación (solo pipeline de voz). Agentes corriendo junto a sus recursos (agente `nas` en el NAS).
4. **Móvil:** app Tauri 2 (misma base React) como cliente de chat/voz/HUD contra el core por WireGuard/Tailscale.
5. **Nube (opcional):** el core es portable a un VPS; lo sensato es nube *híbrida* — core en casa, túnel para acceso externo, quizá réplicas de lectura de memoria en nube.

Reglas que lo hacen posible (y que ya están en el diseño): nada de estado en el cliente, todo evento serializado, daemon-por-dispositivo, agentes remotos por protocolo, almacenes accesibles por red.

## 16. Estructura de repositorio propuesta

Monorepo:

```
jarvis/
├─ core/                    # Python. Clean Architecture por capas
│  ├─ domain/               # entidades y contratos puros (sin dependencias)
│  ├─ application/          # casos de uso: orquestador, router, memoria…
│  ├─ infrastructure/       # adaptadores: LLMs, Qdrant, Redis, Postgres
│  └─ interfaces/           # FastAPI (REST+WS), CLI
├─ brains/                  # config YAML + prompts por cerebro
├─ agents/                  # un paquete por agente (proceso independiente)
│  ├─ _sdk/                 # SDK para escribir agentes (protocolo §5.3)
│  ├─ gmail/  calendar/  github/  docker/  spotify/ …
├─ system-daemon/           # control del SO (Windows primero)
├─ voice-pipeline/          # wake word + STT + TTS
├─ hud/                     # Tauri + React + TS
├─ plugins/                 # herramientas MCP propias
├─ workflows/               # YAML declarativos
├─ infra/                   # docker-compose, migraciones, scripts
└─ docs/                    # specs de protocolos y ADRs (decisiones)
```

Cada decisión arquitectónica futura se registra como **ADR** (Architecture Decision Record) en `docs/adr/` — imprescindible para un proyecto de 10 años.

---

## 17. Hoja de ruta

### Fase 0 — Cimientos (fundacional)
- Monorepo, Docker Compose (Postgres/Redis/Qdrant), CI, lint de fronteras entre módulos.
- Contratos: `LLMProvider`, `EventBus`, protocolo de agentes, schemas de eventos.
- ADRs iniciales (este documento troceado).

### Fase 1 — MVP: "JARVIS habla y actúa en mi PC"
Objetivo: hablar con JARVIS por chat y voz, y que controle lo básico del PC.
- Core: orquestador + router v1 (reglas + clasificador barato) + 2 cerebros (conversacional, código).
- Proveedores: Claude + GPT + Ollama.
- Memoria: inmediata + conversación (Postgres) + vectorial básica (Qdrant).
- Daemon SO v1: abrir/cerrar apps, ventanas, portapapeles, métricas CPU/RAM/GPU, captura+OCR.
- Voz v1: openWakeWord + faster-whisper + Piper/Azure.
- HUD v1: chat, estado sistema, modelo activo, logs.
- 3 agentes: `filesystem`, `browser` (Playwright), `terminal`.
- **Criterio de éxito:** "Jarvis, abre VSCode", "Jarvis, resume este PDF", "Jarvis, ¿cuánta RAM uso?" funcionan de extremo a extremo por voz.

### Fase 2 — Beta: "JARVIS es útil todos los días"
- Los 7 cerebros completos + fallbacks + presupuesto de coste.
- Cerebro Autónomo v1 (grafo de subtareas, checkpoints, confirmaciones).
- Sistema de agentes maduro: SDK público, manifiestos, permisos, agentes `gmail`, `calendar`, `github`, `spotify`, `docker`, `notion`.
- MCP: consumo de servidores MCP de terceros.
- Memoria completa: 6 niveles + consolidación nocturna.
- Motor de workflows + rutina de la mañana.
- HUD v2: agentes, cola de tareas, grafo de planes, permisos.
- Seguridad: niveles de riesgo, auditoría, keyring.

### Fase 3 — Versión 1.0: "Plataforma"
- Instalador de plugins (`jarvis plugin install`), catálogo, sandbox.
- UIA (UI Automation) para control fiable de apps sin visión.
- Pipelines de contenido: YouTube/TikTok (generación, subida, comentarios) como workflows + agentes.
- Agentes de finanzas, servidor/NAS, domótica (puente Home Assistant).
- Core desplegable en servidor (paso 2 de §15) + satélite de voz en Raspberry Pi.
- Documentación completa de protocolos, tests E2E, telemetría local.

### Fase 4 — Futuro
- Cliente móvil (Tauri 2) + acceso remoto (Tailscale).
- Multi-usuario/multi-perfil, identificación por voz.
- Modelos locales potentes como primarios (a medida que el hardware lo permita).
- Aprendizaje de hábitos: JARVIS propone automatizaciones observando patrones.
- Marketplace de agentes/plugins de la comunidad.

**Orden recomendado de implementación dentro del MVP:** bus de eventos → contratos LLM → orquestador+router → chat en terminal (sin UI) → daemon SO → HUD → voz. La voz al final del MVP: es lo más vistoso pero depende de que todo lo demás sea estable.

---

## 18. Riesgos y decisiones abiertas

| Riesgo | Mitigación |
|---|---|
| Coste de APIs (uso continuo) | presupuestos por cerebro, clasificador barato delante, Ollama para lo trivial, caché de respuestas |
| Fiabilidad del control por visión | jerarquía API>UIA>visión (§8) |
| Cambios en MCP / APIs de proveedores | interfaces internas propias; adaptadores finos |
| WhatsApp/Instagram sin API oficial | vía Playwright/apps de escritorio; asumir fragilidad y ToS |
| Wake word con nombre "Jarvis" | entrenar modelo openWakeWord propio (soportado); Porcupine de pago como plan B |
| Alcance enorme | la hoja de ruta por fases + criterio de éxito por fase; nunca empezar una fase sin cerrar la anterior |

Decisiones que conviene tomar contigo antes de codificar:
1. ¿Hardware del PC principal (GPU) para dimensionar STT/Ollama locales?
2. ¿Presupuesto mensual aproximado de APIs?
3. ¿Idioma de trabajo de JARVIS solo español, o bilingüe?
4. ¿Empezamos el repositorio (Fase 0 + esqueleto del MVP) en la siguiente sesión?
