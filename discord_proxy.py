from app.controller import create_app  # noqa: E402
from app.constants import APP_PORT, DEBUG_MODE  # noqa: E402

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT, debug=DEBUG_MODE)