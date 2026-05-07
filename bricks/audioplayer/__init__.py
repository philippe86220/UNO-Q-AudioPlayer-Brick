import json
import time
import urllib.parse
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


class AudioPlayer:
    def __init__(self, host="http://player:9000"):
        self.host = host
        self.url = ""
        self.volume = 50
        self.running = False

    def _get_json(self, path):
        try:
            with urlopen(self.host + path, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            return {"ok": False, "error": "HTTP error", "code": e.code}
        except URLError as e:
            return {"ok": False, "error": "URL error", "details": str(e)}
        except Exception as e:
            return {"ok": False, "error": "Unexpected error", "details": str(e)}

    def play(self, url):
        encoded_url = urllib.parse.quote(url, safe="")
        result = self._get_json("/play?url=" + encoded_url)

        if result.get("ok"):
            self.url = url
            self.running = True

        return {
            "ok": result.get("ok", False),
            "url": self.url,
            "running": self.running,
            "raw": result
        }

    def stop(self):
        result = self._get_json("/stop")

        if result.get("ok"):
            self.running = False

        return {
            "ok": result.get("ok", False),
            "url": self.url,
            "running": self.running,
            "raw": result
        }

    def set_volume(self, value):
        try:
            value = int(value)
        except Exception:
            value = 50

        value = max(0, min(100, value))

        result = self._get_json("/volume?value=" + str(value))

        if result.get("ok"):
            self.volume = value

        return {
            "ok": result.get("ok", False),
            "volume": self.volume,
            "raw": result
        }

    def status(self):
        result = self._get_json("/status")

        if result.get("ok"):
            self.url = result.get("url", self.url)
            self.volume = result.get("volume", self.volume)
            self.running = result.get("running", self.running)

        return {
            "ok": result.get("ok", False),
            "url": self.url,
            "volume": self.volume,
            "running": self.running,
            "raw": result
        }

    def run(self):
        print("[AudioPlayer brick] App running")
        while True:
            time.sleep(1)
