"""
Server entrypoint for DevSynapse API.
"""

from __future__ import annotations

import uvicorn

from api.dependencies import devsynapse_brain, memory_system, opencode_bridge, settings


def run_server():
    """Run the FastAPI application."""

    print(
        f"""
    🚀 DevSynapse AI API
    ====================

    📍 Endpoint: http://{settings.api_host}:{settings.api_port}
    📚 Documentação: http://{settings.api_host}:{settings.api_port}/docs

    ⚙️  Configuração:
    - Host: {settings.api_host}
    - Port: {settings.api_port}
    - Debug: {settings.api_debug}

    🔧 Componentes:
    - ✅ Memory System: {memory_system.db_path}
    - ✅ OpenCode Bridge: {len(opencode_bridge.allowed_commands)} comandos permitidos
    - {'✅' if devsynapse_brain.api_key else '❌'} DeepSeek API: {'Configurada' if devsynapse_brain.api_key else 'Não configurada'}
    """
    )

    uvicorn.run(
        "api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level="info" if settings.api_debug else "warning",
    )


if __name__ == "__main__":
    run_server()
