import os

from website import create_app
from website.ingestion import start_configured_sources, start_cleanup_thread
from website.statcrew import start_configured_watchers as start_statcrew_watchers
from website.virtius import start_configured_watchers as start_virtius_watchers

app = create_app()

if __name__ == "__main__":
    start_configured_sources()
    start_cleanup_thread()
    start_statcrew_watchers()
    start_virtius_watchers()
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
