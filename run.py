"""Development entrypoint: python run.py"""

import os

from dotenv import load_dotenv

load_dotenv()  # before importing app, so Config sees values from .env

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
