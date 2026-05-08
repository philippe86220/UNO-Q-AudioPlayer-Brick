import time
from audioplayer import AudioPlayer
from arduino.app_utils import App

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

result = player.play("/hosthome/test.mp3")
# result = player.play("http://icecast.radiofrance.fr/franceinfo-lofi.mp3")

print(result)

App.run()
