# UNO-Q-AudioPlayer-Brick

## Introduction

This project demonstrates a generic audio playback brick for Arduino App Lab on UNO Q.

Supported audio sources currently include:

- HTTP / HTTPS audio streams
- local MP3 files stored on the UNO Q host filesystem

The brick provides:

- audio playback from arbitrary sources
- ALSA audio playback
- containerized backend service
- volume control
- playback control
- playback status
- reusable Python API

The backend uses:

- Docker containers
- mpg123
- ALSA
- `/dev/snd` device exposure
- optional host media directory mounting

---

## Example

```python
from audioplayer import AudioPlayer
from arduino.app_utils import App
import time

player = AudioPlayer()

print("Waiting for audio backend...")

for attempt in range(30):
    status = player.status()

    if status.get("ok"):
        print("Audio backend ready")
        break

    print("Audio backend not ready yet...")
    time.sleep(2)

player.set_volume(50)

# HTTP stream
player.play("http://icecast.radiofrance.fr/franceinfo-lofi.mp3")

# Local MP3 example
# player.play("/hosthome/test.mp3")

App.run()
```

---

## Available Methods

```python
player.play(source)
player.stop()
player.set_volume(value)
player.status()
```

---

## Architecture

```text
Python App
    ↓
AudioPlayer Brick
    ↓
Internal HTTP API
    ↓
Containerized audio service
    ↓
mpg123
    ↓
ALSA (/dev/snd)
```

---

## Runtime Interaction Model

The AudioPlayer brick acts as a lightweight Python client.

For example:

```python
player.play("http://icecast.radiofrance.fr/franceinfo-lofi.mp3")
```

does not directly play audio itself.

Instead, it translates the request into an internal HTTP call to the backend service:

```text
GET http://player:9000/play?source=http://icecast.radiofrance.fr/franceinfo-lofi.mp3
```

Other examples:

```text
GET http://player:9000/play?source=/hosthome/test.mp3
GET http://player:9000/volume?value=70
GET http://player:9000/stop
GET http://player:9000/status
```

The backend audio service is the actual owner of playback:

```text
audio_service.py
    ↓
mpg123
    ↓
ALSA
    ↓
/dev/snd
    ↓
USB audio device
```

This means the App Lab Python application does **not** directly control ALSA audio playback.

Instead, it communicates with a dedicated internal audio service through HTTP requests.

Execution flow:

```text
App Lab Python app (main.py)
        ↓
AudioPlayer brick (__init__.py)
        ↓
Internal HTTP request
        ↓
Containerized audio backend (audio_service.py)
        ↓
mpg123 / amixer
        ↓
ALSA (/dev/snd)
        ↓
physical audio output
```

Responsibility separation:

```text
main.py              = application logic
AudioPlayer brick    = simplified client API
audio_service.py     = audio backend server
mpg123 / ALSA        = Linux audio execution
```

This client-server architecture makes the design flexible and reusable.

The frontend control mechanism can change:

- Web UI
- Modulino buttons
- LCD interface
- another Python application
- REST API calls
- automation scripts

without changing the audio engine itself.

As long as the backend HTTP API remains stable, the playback system remains reusable.

---

## Local MP3 Playback

A local host directory can be mounted inside the container:

```yaml
volumes:
  - /home/arduino/mp3:/hosthome
```

Example:

```python
player.play("/hosthome/test.mp3")
```

This allows the brick to play MP3 files stored directly on the UNO Q host filesystem.

---

## Custom Brick Container

This project uses the App Lab custom brick container feature through `brick_compose.yaml`.

The brick declares and manages its own Linux backend service:

```yaml
services:
  player:
    image: debian:bookworm-slim
    user: root

    devices:
      - /dev/snd

    volumes:
      - .:/audioplayer
      - /home/arduino/mp3:/hosthome

    command: >
      sh -c "
      apt update &&
      apt install -y python3 mpg123 alsa-utils procps curl ca-certificates &&
      exec python3 /audioplayer/audio_service.py
      "
```

### Explanation

- `services: player`

  Declares a dedicated backend service container for the brick.

---

- `image: debian:bookworm-slim`

  Uses a lightweight Debian Linux container as the runtime environment for the audio backend.

---

- `user: root`

  Runs the backend process as root **inside the container**.

  This simplifies package installation (`apt install`) and access to audio-related system resources.

---

- `devices: /dev/snd`

  Exposes the UNO Q audio device to the container.

  Without this mapping, ALSA audio playback would not be possible.

---

- `volumes: .:/audioplayer`

  Mounts the brick directory itself inside the container.

  This allows the container to access files shipped with the brick, including:

```text
audio_service.py
```

  which becomes:

```text
/audioplayer/audio_service.py
```

  inside the container.

---

- `volumes: /home/arduino/mp3:/hosthome`

  Mounts a host directory containing local MP3 files.

Example:

Host filesystem:

```text
/home/arduino/mp3/test.mp3
```

Container view:

```text
/hosthome/test.mp3
```

Create the directory if needed:

```bash
mkdir -p /home/arduino/mp3
```

Then copy your MP3 files into that directory (within available storage space on the UNO Q host filesystem).

---

- `command: ...`

  Container startup command.

  It performs:

#### 1. Update package lists

```bash
apt update
```

#### 2. Install required packages

```bash
python3
mpg123
alsa-utils
procps
curl
ca-certificates
```

Package details:

- `python3`

  Python runtime used to execute the backend service (`audio_service.py`).

- `mpg123`

  Lightweight command-line MP3 audio player.

  Used to decode and play:

  - internet MP3 streams
  - local MP3 files

- `alsa-utils`

  ALSA (Advanced Linux Sound Architecture) utility tools.

  Provides:

```bash
amixer
```

  used by the project to control audio volume.

- `procps`

  Linux process management utilities.

  Provides tools such as:

```bash
ps
pkill
```

  useful for debugging or process management.

- `curl`

  Command-line HTTP client.

  Useful for manually testing the internal backend API:

```bash
curl http://localhost:9000/status
```

- `ca-certificates`

  SSL/TLS certificate bundle.

  Required so HTTPS audio streams can be accessed securely.

  Without it, URLs such as:

```text
https://...
```

  may fail with certificate validation errors.

#### 3. Start backend service

```bash
python3 /audioplayer/audio_service.py
```

`exec` replaces the shell process with the Python backend process, which is cleaner for container lifecycle management.

---
### Why this matters

This demonstrates that a custom App Lab brick can encapsulate not only Python logic, but also:

- its own Linux runtime environment
- its own backend service
- hardware access
- local filesystem access
- reusable APIs
## Notes

On first startup, the container dynamically installs required Debian packages:

- python3
- mpg123
- alsa-utils
- curl
- ca-certificates

Because of this initialization step, audio playback may become available after approximately 30 to 60 seconds on a fresh installation.

---

## Repository Content

```text
bricks/
    audioplayer/
        __init__.py
        brick_config.yaml
        brick_compose.yaml
        audio_service.py

python/
    main.py

README.md
app.yaml
```

---

## Credits

This project was developed through experimentation and architectural exploration of the UNO Q platform.

It also benefited from technical discussions and architectural exploration with ChatGPT (OpenAI).

---

## License

MIT License
