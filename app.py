from flask import Flask, request, jsonify
import logging
import os
from soco import SoCo
from threading import Thread
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration: update with your Sonos speaker's IP and the URL of your chime MP3.
SONOS_IP = os.environ.get("SONOS_IP", "192.168.1.18")
# This URL should point to your chime file served via Flask's static directory.
CHIME_URL = os.environ.get("CHIME_URL", "https://raw.githubusercontent.com/johnzanussi/unifi-g4-doorbell-sounds/main/sounds/sounds_ring_button/Chime.mp3")
# Duration (in seconds) for which the chime plays. Adjust as needed.
CHIME_DURATION = 4

def restore_playback(coordinator, prev_state, prev_uri, prev_position, prev_volume, delay):
    """
    Wait for the chime to finish, then restore the previous playback state
    and volume.
    """
    time.sleep(delay)
    try:
        if prev_uri:
            app.logger.info("Restoring previous track: %s", prev_uri)
            coordinator.play_uri(uri=prev_uri)
            time.sleep(1)
            if prev_position:
                try:
                    coordinator.seek(prev_position)
                    app.logger.info("Seeked to %s", prev_position)
                except Exception as e:
                    app.logger.error("Error seeking: %s", str(e))
            if prev_state == "PLAYING":
                coordinator.play()
                app.logger.info("Resumed playback.")
        # Restore the previous volume
        coordinator.volume = prev_volume
        app.logger.info("Restored volume to %s", prev_volume)
    except Exception as e:
        app.logger.error("Error restoring playback: %s", str(e))

@app.route('/doorbell', methods=['POST'])
def doorbell():
    """
    Receives a webhook, plays the doorbell chime, and then restores the previous
    playback state and volume.
    """
    data = request.get_json(silent=True)
    app.logger.info("Received webhook with data: %s", data)

    try:
        # Connect to the Sonos speaker
        speaker = SoCo(SONOS_IP)

        # If the speaker is in a group, use the group's coordinator
        if speaker.group and speaker.group.coordinator != speaker:
            coordinator = speaker.group.coordinator
            app.logger.info("Speaker is in a group. Using coordinator at %s", coordinator.ip_address)
        else:
            coordinator = speaker
            app.logger.info("Speaker is not grouped. Using speaker at %s", speaker.ip_address)

        # Capture current playback state and volume before playing the chime
        transport_info = coordinator.get_current_transport_info()
        media_info = coordinator.get_current_media_info()
        prev_state = transport_info.get('current_transport_state')  # e.g., 'PLAYING', 'PAUSED_PLAYBACK'
        prev_uri = media_info.get('uri')                         # The current track's URI
        prev_position = transport_info.get('elapsed_time')         # Elapsed time in the current track
        prev_volume = coordinator.volume                         # Current volume
        app.logger.info("Captured state: state=%s, uri=%s, position=%s, volume=%s",
                        prev_state, prev_uri, prev_position, prev_volume)

        # Set the volume for the chime (this will be higher than the previous volume)
        coordinator.volume = 65
        app.logger.info("Setting volume to %s on coordinator %s", coordinator.volume, coordinator.ip_address)

        # Play the chime (this interrupts the previous playback)
        coordinator.play_uri(uri=CHIME_URL)
        app.logger.info("Playing chime from %s", CHIME_URL)

        # Start a background thread to restore playback and volume after the chime
        restore_thread = Thread(
            target=restore_playback,
            args=(coordinator, prev_state, prev_uri, prev_position, prev_volume, CHIME_DURATION)
        )
        restore_thread.start()

        return jsonify({"status": "success", "message": "Chime played"}), 200

    except Exception as e:
        app.logger.error("Error playing chime: %s", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
