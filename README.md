# UNO-Q-AudioPlayer-Brick

## Introduction

**This first version focuses on audio playback from HTTP/HTTPS streams.**

Local MP3 file playback will be explored in a future update.
This project demonstrates a generic audio playback brick for Arduino App Lab on UNO Q.

The brick provides:

- audio streaming from arbitrary URLs
- ALSA audio playback
- containerized backend service
- volume control
- playback control
- reusable Python API

The backend uses:

- Docker containers
- mpg123
- ALSA
- `/dev/snd` device exposure

---

## Example

```python
from audioplayer import AudioPlayer
from arduino.app_utils import App

player = AudioPlayer()

player.set_volume(50)

player.play("http://icecast.radiofrance.fr/franceinfo-lofi.mp3")

App.run()
```

---

## Available Methods

```python
player.play(url)
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
Containerized audio service
    ↓
mpg123
    ↓
ALSA (/dev/snd)
```

---

## Notes

On first startup, the container dynamically installs required Debian packages.

Because of this initialization step, audio playback may become available after approximately 30 to 60 seconds on a fresh installation.

---

## Repository Content

```text
bricks/
    audioplayer/
        __init__.py
        brick_config.yaml
        brick_compose.yaml
        radio_service.py

python/
    main.py
```

---

## Credits

This project was developed through experimentation and architectural exploration of the UNO Q platform.

It also benefited from technical discussions and architectural exploration with ChatGPT (OpenAI).

---

## License

MIT License
