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
