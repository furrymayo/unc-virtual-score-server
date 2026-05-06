from website import create_app
from website.cloud_relay import start_cloud_relay
from website.config import CONFIG
from website.ingestion import start_configured_sources, start_cleanup_thread
from website.statcrew import start_configured_watchers as start_statcrew_watchers
from website.virtius import start_configured_watchers as start_virtius_watchers

app = create_app()

if __name__ == "__main__":
    start_configured_sources()
    start_cleanup_thread()
    start_statcrew_watchers()
    start_virtius_watchers()
    start_cloud_relay()
    app.run(
        host=CONFIG.flask_host,
        port=CONFIG.flask_port,
        debug=CONFIG.flask_debug,
        threaded=True,
    )
