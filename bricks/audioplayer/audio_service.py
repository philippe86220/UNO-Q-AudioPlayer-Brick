from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import json
import urllib.parse

HOST = "0.0.0.0"
PORT = 9000

AUDIO_DEVICE = "hw:0,0"

player_process = None
current_source = ""
volume = 50


def stop_player():
    global player_process

    if player_process is not None:
        try:
            player_process.terminate()
            player_process.wait(timeout=2)
        except Exception:
            try:
                player_process.kill()
            except Exception:
                pass

        player_process = None


def start_player(source):
    global player_process, current_source

    if not source:
        return {
            "ok": False,
            "error": "Missing source"
        }

    stop_player()

    player_process = subprocess.Popen([
        "mpg123",
        "-o", "alsa",
        "-a", AUDIO_DEVICE,
        "--buffer", "4096",
        source
    ])

    current_source = source

    return {
        "ok": True,
        "source": current_source
    }


def set_volume(value):
    global volume

    try:
        value = int(value)
    except Exception:
        value = 50

    value = max(0, min(100, value))
    volume = value

    subprocess.run([
        "amixer",
        "-c", "0",
        "cset",
        "numid=3",
        str(value) + "%"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return {
        "ok": True,
        "volume": volume
    }


def get_status():
    return {
        "ok": True,
        "source": current_source,
        "volume": volume,
        "running": player_process is not None and player_process.poll() is None
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, data):
        body = json.dumps(data).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.strip("/")
        query = urllib.parse.parse_qs(parsed.query)

        if path == "play":
            source = query.get("source", [""])[0]
            self._send_json(start_player(source))
            return

        if path == "stop":
            stop_player()
            self._send_json({
                "ok": True,
                "source": current_source,
                "running": False
            })
            return

        if path == "status":
            self._send_json(get_status())
            return

        if path == "volume":
            value = query.get("value", ["50"])[0]
            self._send_json(set_volume(value))
            return

        self._send_json({
            "ok": False,
            "error": "Not found",
            "path": path
        })


if __name__ == "__main__":
    print("[audio_service] starting on port", PORT)
    HTTPServer((HOST, PORT), Handler).serve_forever()
