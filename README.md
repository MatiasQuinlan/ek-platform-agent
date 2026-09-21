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

## Builds

GitHub Actions produce builds independientes para macOS y Windows con PyInstaller. Se ejecutan manualmente o al publicar un tag `v*`.

La versión inicial es un agente de escritorio sin firma/notarización. Antes de distribución pública hay que añadir certificados de firma de Apple y Authenticode para Windows.
