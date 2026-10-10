# EK Platform Agent

Aplicación local multiplataforma para conectar el chat de EK Platform con el Codex CLI autenticado con la cuenta ChatGPT del trabajador.

## Requisitos

- Python 3.11+ para desarrollo.
- Codex CLI instalado y disponible en `PATH`.
- Sesión Cognito del frontend para obtener el access token de la aplicación.

## Uso local

```bash
uv sync --all-groups
uv run ek-agent
```

Pulsa **Conectar ChatGPT** para abrir el flujo oficial `codex login`. Después indica la URL de API y el token Cognito, y pulsa **Iniciar agente**.

El token Cognito se guarda usando el almacén de credenciales del sistema mediante `keyring`; la sesión de ChatGPT permanece bajo el control de Codex CLI.

### Codex app-server (experimental)

La ejecución persistente se habilita con `EK_CODEX_APP_SERVER=true`. El agente inicia
`codex app-server --listen stdio://` y habla JSONL por stdin/stdout; si la bandera no está
activa, conserva el adaptador compatible basado en `codex exec`.

Cada job incluye `conversationId`. Cuando está habilitado el app-server, el agente guarda el
ID de thread asociado a esa conversación en el almacén protegido de credenciales del sistema
(keyring); nunca lo envía al backend. Así, los jobs posteriores reanudan el mismo thread con
`thread/resume`, incluso después de reiniciar el agente. Durante la ejecución publica eventos
`assistant.delta` y `turn.completed` ordenados por `seq` en el endpoint de eventos del job y
solo después envía el resultado JSON habitual al endpoint de completado.

La ejecución heredada mediante `codex exec` sigue siendo el fallback predeterminado. El
adaptador de ejecución acepta un callback opcional para eventos incrementales, por lo que los
ejecutores personalizados existentes que solo implementan `execute(prompt)` siguen siendo
compatibles.

## Aplicaciones instalables

GitHub Actions genera dos artefactos multiplataforma mediante PyInstaller:

- macOS: `EKPlatformAgent-macOS.dmg`, que contiene `EKPlatformAgent.app`.
- Windows: `EKPlatformAgent.exe` como aplicación GUI, sin ventana de terminal.

La aplicación queda disponible en la barra de menú de macOS o en el área de notificación de Windows. Desde ese menú se puede mostrar la ventana, iniciar/detener el agente o salir. Después del primer login, los siguientes lanzamientos inician el agente automáticamente y muestran la ventana con su estado. Cerrar la ventana la oculta en la bandeja; **Salir** termina la aplicación.

Los registros del agente se guardan en `~/.config/ek-platform-agent/agent.log` en macOS y en `%APPDATA%/ek-platform-agent/agent.log` en Windows.

El workflow se ejecuta manualmente o al publicar un tag `v*`. Los artefactos se descargan desde la ejecución de GitHub Actions `Build agent`. Para distribución pública todavía hay que añadir firma/notarización de Apple y firma Authenticode para Windows.
