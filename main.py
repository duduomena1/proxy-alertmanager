from app.controller import create_app
from app.constants import APP_PORT, DEBUG_MODE


app = create_app()

if __name__ == '__main__':
    # use_reloader=False evita duplicação do PortainerMonitor thread
    # quando DEBUG_MODE está ativo (Flask cria 2 processos com reloader)
    app.run(host='0.0.0.0', port=APP_PORT, debug=DEBUG_MODE, use_reloader=False)
