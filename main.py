import os

from website import create_app
from website.ingestion import start_configured_sources, start_cleanup_thread

app = create_app()

if __name__ == "__main__":
    start_configured_sources()
    start_cleanup_thread()
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
