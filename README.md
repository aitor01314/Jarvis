# JARVIS — Plataforma de IA Personal

Asistente personal inspirado en el JARVIS de Iron Man: multi-cerebro,
multi-agente, con control del sistema operativo, voz y HUD futurista.
**100% gratuito**: usa solo APIs con tier gratuito (Groq, Gemini,
Cerebras, Mistral, GitHub Models) con **failover automático a
OpenRouter** (modelos `:free`) y a **Ollama** local como último recurso.

> Documento de arquitectura completo: `docs/ARQUITECTURA.md`

## Arranque rápido (MVP)

```bash
# 1. Claves gratuitas (con UNA basta para empezar)
copy .env.example .env       # y rellena GROQ_API_KEY, GEMINI_API_KEY, etc.

# 2. Dependencias
python -m venv .venv && .venv\Scripts\activate
pip install -e .[dev]

# 3. Infraestructura (opcional en esta fase)
docker compose -f infra/docker-compose.yml up -d

# 4a. Chat en terminal
python -m core.interfaces.cli

# 4b. API + WebSocket
uvicorn core.interfaces.api:app --reload
#   GET  /health    -> estado de la cadena de failover
#   POST /chat      -> {"message": "hola jarvis"}
#   WS   /ws/chat   -> streaming
```

## Failover gratuito

Orden de la cadena (se salta lo que no tenga clave):

1. **Groq** → 2. **Gemini** → 3. **Cerebras** → 4. **Mistral** →
5. **GitHub Models** → 6. **OpenRouter (`:free`)** → 7. **Ollama (local)**

Si un proveedor devuelve `429` (límite por minuto agotado), entra en
cooldown el tiempo que indique `Retry-After` y la petición pasa al
siguiente escalón automáticamente. Con esto JARVIS nunca deja de
responder aunque todo sea gratis.

## Estructura del monorepo

```
core/            núcleo (Clean Architecture)
  domain/        entidades y contratos puros
  application/   casos de uso: router, failover, orquestador
  infrastructure/ adaptadores (proveedores LLM, BD, bus)
  interfaces/    FastAPI (REST+WS) y CLI
brains/          configuración de cerebros
agents/          agentes (procesos independientes) — Fase Beta
system-daemon/   control del SO (Windows) — Fase MVP
voice-pipeline/  wake word + STT + TTS — Fase MVP
hud/             interfaz HUD (Tauri + React) — Fase MVP
plugins/         herramientas MCP propias — Fase 1.0
workflows/       automatizaciones declarativas — Fase Beta
infra/           docker-compose, migraciones
docs/            arquitectura y ADRs
```

## Verificación

```bash
ruff check .
pytest
```
