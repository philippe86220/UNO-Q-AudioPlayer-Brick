# AudioPlayer Brick for Arduino App Lab (UNO Q)

## Overview

The AudioPlayer brick provides a lightweight Python client API for controlling audio playback on Arduino UNO Q through a dedicated Linux backend service.

It is designed for Arduino App Lab custom bricks and demonstrates how a Python brick can encapsulate not only reusable application logic, but also a specialized backend service with direct hardware access.

Supported audio sources include:

- HTTP / HTTPS MP3 audio streams
- local MP3 files stored on the UNO Q host filesystem

The brick provides a simple Python API:

```python
player.play(source)
player.stop()
player.set_volume(value)
player.status()
```

while the actual audio playback is handled by a separate backend service.

This separation keeps the public API simple while isolating Linux audio execution details from the application layer.

---

## Architecture

The runtime architecture is intentionally split into multiple layers:

```text
App Lab Python application
        ↓
AudioPlayer brick (__init__.py)
        ↓
internal HTTP JSON API
        ↓
audio_service.py
        ↓
mpg123 / amixer
        ↓
ALSA (/dev/snd)
        ↓
physical audio output
```

### Layer responsibilities

#### App Lab Python application

This is the user application (`main.py`).

It contains the application logic:

- selecting a radio stream
- playing a local MP3
- changing volume
- stopping playback
- querying backend status

Example:

```python
player.play("http://icecast.radiofrance.fr/franceinfo-lofi.mp3")
```

The application does not directly interact with Linux audio tools.

---

#### AudioPlayer brick (`__init__.py`)

This layer acts as a lightweight Python client.

Its responsibilities are:

- exposing a clean Python API
- encoding request parameters
- sending HTTP requests to the backend
- parsing JSON responses
- maintaining synchronized local state

It hides all backend communication details from the application.

---

#### Internal HTTP API

Communication between the brick and the backend service is performed through a local HTTP JSON API.

Examples:

```text
GET /play?source=...
GET /stop
GET /status
GET /volume?value=70
```

This API is internal to the brick architecture.

It provides a stable control interface between the client layer and the backend execution layer.

---

#### Backend service (`audio_service.py`)

This is the actual execution engine.

Responsibilities:

- receiving control requests
- managing audio player lifecycle
- launching and stopping `mpg123`
- adjusting volume via `amixer`
- maintaining playback state
- returning JSON responses

This service owns the actual playback process.

---

#### Linux audio tools

The backend delegates execution to standard Linux tools:

**mpg123**

Used for:

- streaming internet MP3 audio
- playing local MP3 files

**amixer**

Used for:

- controlling ALSA volume

These tools perform the actual low-level work.

---

#### ALSA

ALSA (Advanced Linux Sound Architecture) is the Linux audio subsystem used by the backend.

The backend explicitly targets:

```text
hw:0,0
```

which typically corresponds to the primary audio device.

The container receives access through:

```yaml
devices:
  - /dev/snd
```

---

## Design rationale

This architecture is intentionally more modular than directly calling Linux audio tools from the application.

### Separation of responsibilities

Application logic:

```python
player.play(...)
```

Audio execution:

```python
subprocess.Popen(["mpg123", ...])
```

These responsibilities remain isolated.

This improves maintainability and clarity.

---

### Stable control interface

The internal HTTP API becomes a stable contract:

```text
/play
/stop
/status
/volume
```

The frontend implementation may change without affecting the backend.

Examples of interchangeable frontends:

- App Lab Python application
- Web UI
- hardware buttons
- REST client
- automation scripts

As long as the backend API remains unchanged, the audio engine remains reusable.

---

### Hardware isolation

Linux audio access remains confined to the backend service.

The application layer never directly manipulates:

- ALSA
- `/dev/snd`
- `mpg123`
- `amixer`

This keeps the public API much simpler.

---

### Backend replaceability

Because the frontend communicates through HTTP, the backend implementation could be replaced later.

For example:

Current:

```text
mpg123
```

Possible future replacement:

```text
ffplay
vlc
gstreamer
custom decoder
```

without changing the public Python API.

---

### Simplicity for users

Without this architecture, application code would need to manage:

- subprocess creation
- process termination
- command-line arguments
- error handling
- audio device selection
- JSON formatting
- backend state management

Instead:

```python
player.play(source)
```

is sufficient.

---

## Backend service: `audio_service.py`

This file implements the dedicated audio control service.

It is a small HTTP server exposing a JSON control API for audio playback.

Main responsibilities:

- start playback
- stop playback
- adjust volume
- report status

Runtime model:

```text
HTTP request
    ↓
audio_service.py
    ↓
audio control helper
    ↓
Linux audio tool
```

---

## Imports

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
```

Provides the standard Python HTTP server framework.

Used for:

- receiving HTTP requests
- dispatching request handlers
- sending responses

---

```python
import subprocess
```

Used to launch and control external Linux processes:

- `mpg123`
- `amixer`

---

```python
import json
```

Used to serialize API responses.

Example:

```json
{"ok": true, "running": true}
```

---

```python
import urllib.parse
```

Used to parse:

```text
/play?source=http://...
```

into:

- request path
- query parameters

---

## Configuration constants

```python
HOST = "0.0.0.0"
PORT = 9000
```

### HOST

```text
0.0.0.0
```

means:

listen on all network interfaces available inside the container.

This allows other containers (such as the App Lab Python container) to reach the service.

---

### PORT

```text
9000
```

Internal control API listening port.

Example:

```text
http://player:9000/status
```

---

## Audio configuration

```python
AUDIO_DEVICE = "hw:0,0"
```

Explicit ALSA target device.

Meaning:

- card 0
- device 0

Typical use case:

USB audio adapter connected before board boot, becoming the primary ALSA device.

---

## Global runtime state

```python
player_process = None
current_source = ""
volume = 50
```

These variables maintain backend state between requests.

### player_process

Stores the active `subprocess.Popen()` object.

Used for:

- stop requests
- status inspection

---

### current_source

Stores the currently selected source:

Example:

```text
http://icecast.radiofrance.fr/franceinfo-lofi.mp3
```

or:

```text
/hosthome/test.mp3
```

---

### volume

Stores current logical volume state:

```text
0 → 100
```

This mirrors the backend audio level.

## Audio control helpers

The backend service uses a small set of helper functions to manage playback state and interact with Linux audio tools.

These functions are called by the HTTP request handler.

---

### `stop_player()`

Purpose:

- stop the currently running audio process
- clean up backend state

Implementation:

```python
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
```

---

### Why `global player_process`

The backend stores the active playback process in a global variable:

```python
player_process
```

because HTTP requests are independent.

The request handler is instantiated separately for each incoming request.

Persistent playback state therefore cannot be stored inside the handler instance.

The backend process state must live outside request-local objects.

---

### Graceful shutdown first

```python
player_process.terminate()
```

sends a termination signal to the external process.

This allows `mpg123` to exit cleanly.

Then:

```python
player_process.wait(timeout=2)
```

waits up to two seconds for normal termination.

---

### Forced shutdown fallback

If normal termination fails:

```python
player_process.kill()
```

forces immediate process termination.

This prevents orphaned audio processes.

---

### Final cleanup

```python
player_process = None
```

marks the backend as having no active player process.

---

## `start_player(source)`

Purpose:

- validate requested audio source
- stop any previous playback
- launch a new `mpg123` process
- update backend state

Implementation:

```python
def start_player(source):
    global player_process, current_source

    if not source:
        return {"ok": False, "error": "Missing source"}

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
```

---

### Source validation

```python
if not source:
```

prevents launching the player without input.

Examples of valid sources:

Internet stream:

```text
http://icecast.radiofrance.fr/franceinfo-lofi.mp3
```

Local file:

```text
/hosthome/test.mp3
```

Invalid:

```text
empty source
```

---

### Why stop previous playback first

```python
stop_player()
```

ensures only one audio process exists.

Without this step:

multiple `mpg123` processes could run simultaneously.

That would produce:

- overlapping audio
- resource leaks
- inconsistent backend state

---

### `subprocess.Popen()`

Used because playback must remain asynchronous.

The HTTP server must continue handling requests while audio plays.

If blocking execution were used:

```python
subprocess.run(...)
```

the backend would freeze until playback ended.

That would make:

```text
/stop
/status
/volume
```

unreachable during playback.

---

### `mpg123` arguments

```python
"mpg123"
```

Audio playback engine.

---

```python
"-o", "alsa"
```

Select ALSA audio output backend.

---

```python
"-a", AUDIO_DEVICE
```

Select explicit ALSA target:

```text
hw:0,0
```

---

```python
"--buffer", "4096"
```

Internal playback buffer size.

Helps smooth streaming playback.

---

```python
source
```

Input source:

stream URL or local MP3 file.

---

## `set_volume(value)`

Purpose:

- validate requested volume
- clamp allowed range
- update ALSA mixer
- synchronize backend state

Implementation:

```python
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
    ])

    return {
        "ok": True,
        "volume": volume
    }
```

---

### Input conversion

HTTP query parameters arrive as strings.

Example:

```text
/value?value=75
```

produces:

```python
"75"
```

Conversion:

```python
int(value)
```

is therefore required.

---

### Invalid input fallback

Example invalid input:

```text
abc
```

Fallback:

```python
50
```

prevents backend failure.

---

### Range clamping

```python
max(0, min(100, value))
```

guarantees valid bounds:

```text
0 → mute
100 → maximum
```

Examples:

```text
-20 → 0
150 → 100
```

---

### ALSA mixer control

```python
amixer
```

is the standard ALSA command-line mixer tool.

---

```python
-c 0
```

selects sound card 0.

---

```python
cset
```

changes a mixer control directly.

---

```python
numid=3
```

identifies the target mixer control.

This depends on the actual audio device.

Example:

USB audio adapter exposing headphone volume.

---

## `get_status()`

Purpose:

return backend runtime state.

Implementation:

```python
def get_status():
    return {
        "ok": True,
        "source": current_source,
        "volume": volume,
        "running": player_process is not None and player_process.poll() is None
    }
```

---

### `poll()` behavior

```python
player_process.poll()
```

returns:

- `None` if process is still running
- exit code if process has finished

Therefore:

```python
player_process.poll() is None
```

means:

audio playback is still active.

---

## HTTP request handler

The backend HTTP API is implemented using:

```python
BaseHTTPRequestHandler
```

from Python's standard library.

---

### Handler definition

```python
class Handler(BaseHTTPRequestHandler):
```

This creates a custom request handler.

Its purpose:

- receive HTTP requests
- parse paths and query parameters
- dispatch control actions
- send JSON responses

---

## Handler lifecycle

The handler is **not instantiated manually**.

The HTTP server creates one handler instance per incoming connection.

Conceptual flow:

```text
HTTPServer receives connection
        ↓
creates Handler instance
        ↓
calls do_GET()
        ↓
response sent
        ↓
instance becomes unreachable
```

The instance is request-local.

Persistent playback state must therefore live outside the handler.

---

## `_send_json(self, data)`

Purpose:

send consistent JSON responses.

Implementation:

```python
def _send_json(self, data):
    body = json.dumps(data).encode("utf-8")

    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)
```

---

### JSON serialization

```python
json.dumps(data)
```

converts:

```python
{"ok": True}
```

into:

```json
{"ok": true}
```

---

### UTF-8 encoding

HTTP responses must be bytes:

```python
.encode("utf-8")
```

---

### Response headers

```python
Content-Type
```

declares JSON payload.

---

```python
Content-Length
```

declares response size.

---

### Output stream

```python
self.wfile.write(body)
```

writes response bytes to the client connection.

## `do_GET(self)`

The backend exposes its control API through HTTP GET requests.

```python
def do_GET(self):
    parsed = urllib.parse.urlparse(self.path)
    path = parsed.path.strip("/")
    query = urllib.parse.parse_qs(parsed.query)
```

---

### URL parsing

Example request:

```text
/play?source=http%3A%2F%2Fexample.com%2Fradio.mp3
```

is parsed into:

```python
path = "play"
query = {
    "source": ["http://example.com/radio.mp3"]
}
```

`parse_qs()` returns values as lists, because a query parameter can appear multiple times.

---

## Endpoint: `/play`

```python
if path == "play":
    source = query.get("source", [""])[0]
    self._send_json(start_player(source))
    return
```

Purpose:

- extract the `source` parameter
- start playback
- return backend status

Example:

```text
GET /play?source=/hosthome/test.mp3
```

Response example:

```json
{
  "ok": true,
  "source": "/hosthome/test.mp3"
}
```

---

## Endpoint: `/stop`

```python
if path == "stop":
    stop_player()
    self._send_json({
        "ok": True,
        "source": current_source,
        "running": False
    })
    return
```

Purpose:

- stop active playback
- preserve the last known source
- return stopped state

Response example:

```json
{
  "ok": true,
  "source": "/hosthome/test.mp3",
  "running": false
}
```

---

## Endpoint: `/status`

```python
if path == "status":
    self._send_json(get_status())
    return
```

Purpose:

- query current backend state
- check whether playback is still active

Response example:

```json
{
  "ok": true,
  "source": "/hosthome/test.mp3",
  "volume": 50,
  "running": true
}
```

---

## Endpoint: `/volume`

```python
if path == "volume":
    value = query.get("value", ["50"])[0]
    self._send_json(set_volume(value))
    return
```

Purpose:

- extract the `value` parameter
- clamp volume to the `0..100` range
- apply ALSA mixer control

Example:

```text
GET /volume?value=75
```

Response example:

```json
{
  "ok": true,
  "volume": 75
}
```

---

## Unknown endpoint

```python
self._send_json({
    "ok": False,
    "error": "Not found",
    "path": path
})
```

Purpose:

- return a structured JSON error
- avoid crashing on unknown paths

Example:

```text
GET /unknown
```

Response example:

```json
{
  "ok": false,
  "error": "Not found",
  "path": "unknown"
}
```

Note:

The response body reports an error, but the helper currently always sends HTTP status `200`.

For a stricter API, `_send_json()` could be extended later to accept an HTTP status code such as `404`.

---

## Endpoint summary

| Endpoint | Query parameter | Action | Example |
|---|---|---|---|
| `/play` | `source` | Starts playback with `mpg123` | `/play?source=/hosthome/test.mp3` |
| `/stop` | none | Stops current playback process | `/stop` |
| `/status` | none | Returns backend state | `/status` |
| `/volume` | `value` | Sets ALSA volume | `/volume?value=70` |

---

## Main entry point

```python
if __name__ == "__main__":
    print("[audio_service] starting on port", PORT)
    HTTPServer((HOST, PORT), Handler).serve_forever()
```

---

### `__name__ == "__main__"`

This condition means:

the server starts only when the file is executed directly.

Example:

```bash
python3 /audioplayer/audio_service.py
```

---

### `HTTPServer((HOST, PORT), Handler)`

Creates an HTTP server bound to:

```text
0.0.0.0:9000
```

and tells it to use:

```python
Handler
```

for incoming requests.

---

### `serve_forever()`

Starts the server loop.

The process remains active and continuously handles incoming HTTP requests.

Conceptual behavior:

```text
wait for request
    ↓
create handler
    ↓
process request
    ↓
send response
    ↓
wait for next request
```

---

## Backend request lifecycle

Example:

```text
GET /play?source=/hosthome/test.mp3
```

Execution flow:

```text
HTTPServer
    ↓
creates Handler instance
    ↓
Handler.do_GET()
    ↓
parse path and query
    ↓
start_player("/hosthome/test.mp3")
    ↓
stop previous player if needed
    ↓
subprocess.Popen(["mpg123", ...])
    ↓
return JSON response
```

---

## Important implementation detail

The backend uses:

```python
HTTPServer
```

not:

```python
ThreadingHTTPServer
```

This means requests are handled sequentially.

For this project, that is acceptable because the request handlers are short-lived.

Playback itself is launched asynchronously through:

```python
subprocess.Popen()
```

so the HTTP server is not blocked while audio continues playing.

---

## AudioPlayer client: `__init__.py`

The `__init__.py` file defines the public Python API exposed by the brick.

It acts as a client for the backend HTTP service.

Its role is not to play audio directly.

Instead, it translates Python method calls into HTTP requests.

Example:

```python
player.play("/hosthome/test.mp3")
```

becomes:

```text
GET http://player:9000/play?source=%2Fhosthome%2Ftest.mp3
```

---

## Imports

```python
import json
```

Used to decode JSON responses returned by the backend service.

---

```python
import time
```

Used by the optional `run()` loop.

---

```python
import urllib.parse
```

Used to URL-encode audio sources before sending them as query parameters.

This is important because audio sources may contain special characters.

Example:

```text
https://example.com/radio?token=abc&quality=low
```

must be encoded before being inserted into:

```text
/play?source=...
```

---

```python
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
```

Used to perform HTTP GET requests and handle common network errors.

---

## `AudioPlayer` class

```python
class AudioPlayer:
```

This is the main class exposed by the brick.

A user application typically creates one instance:

```python
player = AudioPlayer()
```

---

## Constructor

```python
def __init__(self, host="http://player:9000"):
    self.host = host
    self.source = ""
    self.volume = 50
    self.running = False
```

---

### `host`

```python
host="http://player:9000"
```

Default backend URL.

In the custom brick Docker setup, `player` is the service name declared in `brick_compose.yaml`.

Docker internal DNS resolves:

```text
player
```

to the backend service container.

---

### Local client state

```python
self.source = ""
self.volume = 50
self.running = False
```

The client keeps a local copy of backend state.

This local state is updated when backend calls succeed.

The authoritative state remains the backend service.

---

## `_get_json(self, path)`

Purpose:

- perform a GET request
- parse the JSON response
- return a structured error if communication fails

Implementation:

```python
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
```

---

### Timeout

```python
timeout=3
```

prevents the application from blocking indefinitely if the backend service is unavailable.

---

### JSON decoding

```python
json.loads(...)
```

converts the backend response into a Python dictionary.

Example backend response:

```json
{
  "ok": true,
  "running": true
}
```

becomes:

```python
{
    "ok": True,
    "running": True
}
```

---

### Error handling

The client handles:

- HTTP errors
- connection errors
- DNS errors
- backend unavailable
- malformed or unexpected failures

Instead of raising directly to the application, it returns structured dictionaries.

Example:

```python
{
    "ok": False,
    "error": "URL error",
    "details": "..."
}
```

## Public API

The `AudioPlayer` class exposes four main methods:

```python
player.play(source)
player.stop()
player.set_volume(value)
player.status()
```

These methods are the public interface used by `main.py`.

---

## `play(source)`

Purpose:

- request playback of an HTTP / HTTPS stream or local MP3 file
- URL-encode the source
- call the backend `/play` endpoint
- update local state if playback starts successfully

Implementation:

```python
def play(self, source):
    encoded_source = urllib.parse.quote(source, safe="")
    result = self._get_json("/play?source=" + encoded_source)

    if result.get("ok"):
        self.source = source
        self.running = True

    return {
        "ok": result.get("ok", False),
        "source": self.source,
        "running": self.running,
        "raw": result
    }
```

---

### Why URL encoding is required

Audio sources can contain characters that have special meaning in URLs:

```text
:
/
?
&
=
'
space
```

Example:

```text
https://example.com/radio.mp3?token=abc&quality=low
```

If inserted directly into:

```text
/play?source=...
```

the backend could parse it incorrectly.

This is why the source is encoded:

```python
urllib.parse.quote(source, safe="")
```

Example:

```python
player.play("/hosthome/BARBARA_L'AIGLE-NOIR.MP3")
```

becomes an HTTP-safe request.

---

### Python call to HTTP request

```python
player.play("/hosthome/test.mp3")
```

maps to:

```text
GET http://player:9000/play?source=%2Fhosthome%2Ftest.mp3
```

The backend decodes the query parameter and passes the source to `mpg123`.

---

## `stop()`

Purpose:

- request backend playback termination
- update local running state

Implementation:

```python
def stop(self):
    result = self._get_json("/stop")

    if result.get("ok"):
        self.running = False

    return {
        "ok": result.get("ok", False),
        "source": self.source,
        "running": self.running,
        "raw": result
    }
```

---

### Python call to HTTP request

```python
player.stop()
```

maps to:

```text
GET http://player:9000/stop
```

The backend terminates the active `mpg123` process if one exists.

---

## `set_volume(value)`

Purpose:

- normalize volume input
- clamp it to the `0..100` range
- request backend ALSA volume update
- update local volume state if successful

Implementation:

```python
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
```

---

### Python call to HTTP request

```python
player.set_volume(70)
```

maps to:

```text
GET http://player:9000/volume?value=70
```

The backend then calls:

```bash
amixer -c 0 cset numid=3 70%
```

---

## `status()`

Purpose:

- query backend state
- synchronize client state with backend state

Implementation:

```python
def status(self):
    result = self._get_json("/status")

    if result.get("ok"):
        self.source = result.get("source", self.source)
        self.volume = result.get("volume", self.volume)
        self.running = result.get("running", self.running)

    return {
        "ok": result.get("ok", False),
        "source": self.source,
        "volume": self.volume,
        "running": self.running,
        "raw": result
    }
```

---

### Python call to HTTP request

```python
player.status()
```

maps to:

```text
GET http://player:9000/status
```

Example response:

```python
{
    "ok": True,
    "source": "/hosthome/test.mp3",
    "volume": 70,
    "running": True,
    "raw": {
        "ok": True,
        "source": "/hosthome/test.mp3",
        "volume": 70,
        "running": True
    }
}
```

---

## Local state vs backend state

The backend service remains the authoritative source of truth.

The client state is only a convenience cache:

```python
self.source
self.volume
self.running
```

This means:

- `play()` updates local state only if backend returns success
- `stop()` updates local state only if backend returns success
- `set_volume()` updates local state only if backend returns success
- `status()` resynchronizes local state from the backend

This avoids assuming that a command succeeded when the backend may have failed.

---

## Method-to-endpoint mapping

| Python method | HTTP request | Backend action |
|---|---|---|
| `player.play(source)` | `GET /play?source=...` | starts `mpg123` |
| `player.stop()` | `GET /stop` | terminates `mpg123` |
| `player.set_volume(value)` | `GET /volume?value=...` | calls `amixer` |
| `player.status()` | `GET /status` | returns backend state |

---

## Request lifecycle examples

### Playing a radio stream

Application code:

```python
player.play("http://icecast.radiofrance.fr/franceinfo-lofi.mp3")
```

Execution flow:

```text
main.py
    ↓
AudioPlayer.play()
    ↓
URL-encode source
    ↓
GET http://player:9000/play?source=...
    ↓
audio_service.py
    ↓
Handler.do_GET()
    ↓
start_player(source)
    ↓
stop previous process if needed
    ↓
subprocess.Popen(["mpg123", "-o", "alsa", "-a", "hw:0,0", ...])
    ↓
ALSA output
```

---

### Playing a local MP3 file

Application code:

```python
player.play("/hosthome/test.mp3")
```

Execution flow:

```text
main.py
    ↓
AudioPlayer.play()
    ↓
GET /play?source=%2Fhosthome%2Ftest.mp3
    ↓
audio_service.py
    ↓
mpg123 /hosthome/test.mp3
    ↓
ALSA output
```

---

### Changing volume

Application code:

```python
player.set_volume(80)
```

Execution flow:

```text
main.py
    ↓
AudioPlayer.set_volume()
    ↓
GET /volume?value=80
    ↓
audio_service.py
    ↓
set_volume(80)
    ↓
amixer -c 0 cset numid=3 80%
```

---

### Stopping playback

Application code:

```python
player.stop()
```

Execution flow:

```text
main.py
    ↓
AudioPlayer.stop()
    ↓
GET /stop
    ↓
audio_service.py
    ↓
stop_player()
    ↓
terminate mpg123 process
```

---


