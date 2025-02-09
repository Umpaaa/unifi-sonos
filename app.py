from flask import Flask, request, jsonify
import logging
import os
from soco import SoCo
from threading import Thread
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration: Update these as needed.
SONOS_IP = os.environ.get("SONOS_IP", "192.168.1.18")
CHIME_URL = os.environ.get("CHIME_URL", "https://raw.githubusercontent.com/johnzanussi/unifi-g4-doorbell-sounds/main/sounds/sounds_ring_button/Chime.mp3")
CHIME_DURATION = 4  # Duration in seconds of the doorbell chime

def restore_volume(coordinator, prev_volume, delay):
    """Wait for the chime to finish, then restore the previous volume."""
    time.sleep(delay)
    try:
        coordinator.volume = prev_volume
        app.logger.info("Restored volume to %s", prev_volume)
    except Exception as e:
        app.logger.error("Error restoring volume: %s", str(e))

@app.route('/doorbell', methods=['POST'])
def doorbell():
    """Receives a webhook, plays the doorbell chime, and then restores the previous volume."""
    data = request.get_json(silent=True)
    app.logger.info("Received webhook with data: %s", data)
    try:
        # Connect to the Sonos speaker.
        speaker = SoCo(SONOS_IP)

        # Use the group's coordinator if the speaker is grouped.
        if speaker.group and speaker.group.coordinator != speaker:
            coordinator = speaker.group.coordinator
            app.logger.info("Speaker is in a group. Using coordinator at %s", coordinator.ip_address)
        else:
            coordinator = speaker
            app.logger.info("Speaker is not grouped. Using speaker at %s", speaker.ip_address)

        # Capture the current volume.
        prev_volume = coordinator.volume
        app.logger.info("Captured previous volume: %s", prev_volume)

        # Set volume to a level for the doorbell chime.
        coordinator.volume = 65
        app.logger.info("Setting volume to %s on coordinator %s", coordinator.volume, coordinator.ip_address)

        # Play the chime.
        coordinator.play_uri(uri=CHIME_URL)
        app.logger.info("Playing chime from %s", CHIME_URL)

        # Start a background thread to restore the previous volume after the chime.
        restore_thread = Thread(target=restore_volume, args=(coordinator, prev_volume, CHIME_DURATION))
        restore_thread.start()

        return jsonify({"status": "success", "message": "Chime played"}), 200

    except Exception as e:
        app.logger.error("Error playing chime: %s", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
