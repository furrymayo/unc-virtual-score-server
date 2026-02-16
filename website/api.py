from flask import Blueprint, jsonify, request

from . import ingestion, trackman

api = Blueprint("api", __name__)


@api.route("/update_server_config", methods=["POST"])
def update_server_config():
    config = request.json or {}

    source = str(config.get("source", "auto")).lower()
    serial_port = config.get("port", "COM1")
    tcp_port = int(config.get("tcp_port", ingestion.DEFAULT_TCP_PORT))
    udp_port = int(config.get("udp_port", ingestion.DEFAULT_UDP_PORT))

    ingestion.stop_serial_reader()
    ingestion.stop_network_listeners()

    if source == "serial":
        ingestion.start_serial_reader(serial_port)
    elif source in {"udp", "auto"}:
        ingestion.start_network_listeners(tcp_port, udp_port, source)
    else:
        source = "auto"
        ingestion.start_network_listeners(tcp_port, udp_port, source)

    return jsonify(
        {
            "status": "Server config updated",
            "source": source,
            "tcp_port": tcp_port,
            "udp_port": udp_port,
            "serial_port": serial_port,
        }
    )


@api.route("/trackman_config/<sport>", methods=["GET", "POST"])
def trackman_config_endpoint(sport):
    sport_name = trackman.normalize_sport(sport)
    if not sport_name:
        return jsonify({"error": "unsupported sport"}), 404

    if request.method == "GET":
        return jsonify(trackman.get_config(sport_name))

    payload = request.json or {}
    result, status_code = trackman.update_config(sport_name, payload)
    return jsonify(result), status_code


@api.route("/data_sources", methods=["GET", "POST"])
def data_sources_endpoint():
    if request.method == "GET":
        with ingestion.data_sources_lock:
            return jsonify({"sources": list(ingestion.data_sources)})

    payload = request.json or {}
    host = str(payload.get("host", "")).strip()
    name = str(payload.get("name", "")).strip() or host
    port = payload.get("port")

    if not host or port is None:
        return jsonify({"error": "host and port required"}), 400

    try:
        port = int(port)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid port"}), 400

    source_id = ingestion._make_source_id(host, port)
    entry = {
        "id": source_id,
        "name": name,
        "host": host,
        "port": port,
        "enabled": True,
    }

    with ingestion.data_sources_lock:
        for source in ingestion.data_sources:
            if source["id"] == source_id:
                return jsonify({"error": "source already exists"}), 409
        ingestion.data_sources.append(entry)

    ingestion._save_data_sources()
    ingestion.start_tcp_client(entry)

    return jsonify({"status": "added", "source": entry})


@api.route("/data_sources/<source_id>", methods=["DELETE", "PATCH"])
def data_source_item(source_id):
    source_id = source_id.strip()
    if not source_id:
        return jsonify({"error": "source id required"}), 400

    if request.method == "DELETE":
        removed = None
        with ingestion.data_sources_lock:
            for idx, source in enumerate(ingestion.data_sources):
                if source["id"] == source_id:
                    removed = ingestion.data_sources.pop(idx)
                    break

        if not removed:
            return jsonify({"error": "source not found"}), 404

        ingestion.stop_tcp_client(source_id)
        ingestion._save_data_sources()
        return jsonify({"status": "deleted", "source": removed})

    payload = request.json or {}
    enabled = payload.get("enabled")
    name = payload.get("name")

    updated = None
    with ingestion.data_sources_lock:
        for source in ingestion.data_sources:
            if source["id"] == source_id:
                if enabled is not None:
                    source["enabled"] = bool(enabled)
                if name:
                    source["name"] = str(name)
                updated = dict(source)
                break

    if not updated:
        return jsonify({"error": "source not found"}), 404

    if enabled is not None:
        if bool(enabled):
            ingestion.start_tcp_client(updated)
        else:
            ingestion.stop_tcp_client(source_id)

    ingestion._save_data_sources()
    return jsonify({"status": "updated", "source": updated})


@api.route("/get_available_com_ports", methods=["GET"])
def get_available_com_ports():
    ports = ingestion.get_available_com_ports()
    return jsonify({"ports": ports})


@api.route("/get_raw_data/<sport>", methods=["GET"])
def get_raw_data(sport):
    source_id = request.args.get("source")
    return jsonify(ingestion.get_sport_data(sport, source_id))


@api.route("/get_trackman_data/<sport>", methods=["GET"])
def get_trackman_data(sport):
    sport_name = trackman.normalize_sport(sport)
    if not sport_name:
        return jsonify({}), 404
    return jsonify(trackman.get_data(sport_name))


@api.route("/get_trackman_debug/<sport>", methods=["GET"])
def get_trackman_debug(sport):
    sport_name = trackman.normalize_sport(sport)
    if not sport_name:
        return jsonify({}), 404
    return jsonify(trackman.get_debug(sport_name))


@api.route("/get_sources", methods=["GET"])
def get_sources():
    return jsonify({"sources": ingestion.get_sources_snapshot()})
