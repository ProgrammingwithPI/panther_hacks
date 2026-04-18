import math
import time
import threading
import numpy as np
import sounddevice as sd
import serial
import serial.tools.list_ports
import speech_recognition as sr

# ── Config ────────────────────────────────────────────────────────────────────
SAMPLE_RATE     = 44100
NOISE_THRESHOLD = 0.02
BLOCK_SIZE      = 1024
BAUD_RATE       = 9600

# ── Globals ───────────────────────────────────────────────────────────────────
arduino          = None
sensor_triggered = False
stopwatch_start  = None
stopwatch_running = False

# =============================================================================
# MATH + BINARY SEARCH FUNCTIONS (reused from key detection logic)
# =============================================================================

def logarithm_check(lis, peak):
    y, x = lis[peak]
    if 900 < lis[x-5] ** math.log(lis[x+5], 1000) < 1100: #mathematical idea of logs, log of lis[x+5] to 1000 gives what value lis[x+5]
        #needs to be raised to get to 1000, raising lis[x-5] by that number if its close to lis[x+5]'s value will give a number close to 1000
        return True
    return False

def trig_check(lis, peak):
    y, x = lis[peak]
    tan_ratio_left  = abs(5 / lis[x-5]) #lis[x-5] gives y value
    tan_ratio_right = abs(5 / lis[x+5]) #lis[x+5] gives y value
    '''Difference between the peakx and leftx/rightx x-vals tells the you the amount of units of x that changed between their x-coords, 
        or how many units of x they are apart. Which is distance, which is the length of that side of the triangle which is the base.'''
    if tan_ratio_left == tan_ratio_right: #make it about equal
        return True
    return False

def summation_notation(lis, peak):
    y, x = lis[peak]
    #find average value of lis brightness value
    # find distance between last average value and peak
    # find next average value after peak
    # take sum of everything between last average value and peak and peak to next average value.
    # they should have close to same sum
    # Use summation formula where we find mean then multiply it by number of terms between them or "distance"
    # Keep a comment saying "The idea is if its symmetric it should have similar sum, we can find sum by taking average then multiplying it by the number of terms as the lower end and higherend values will all average up to the middle
    # so we can just multiply number of terms by average."

def binary_search(target, lis):
    low = 0
    up  = len(lis)
    '''if lower equal to upper that means there's only one element, and if it 
        didn't exit loop then its not equal to target'''
    middle = None
    while low < up:
        middle = (low + up) // 2
        if lis[middle] == target:
            return low + 1
        elif lis[middle] < target:
            low = middle + 1
            '''since the list is sorted if the middle value is less then the targets value, that means every index lower to the middle index
                isn't the solution as they are less then the middle index's value as its a sorted list so the middle value which has a greater index to them would have a greater value as well.
                 That value itself is smaller then the target so everything with a lower index hence lower value would have a lower value to the target because their value is less then the middle which is less then the target.
                As a result low the value should equal middle index + 1, cause we already know middle value isn't the solution. '''
        elif lis[middle] > target:
            up = middle
            '''Same logic as above except if middle value is larger then target, all index values above it should be cut out, as again its sorted
                so if they have a larger index they have a larger value then middle, if middle value itself is larger then target everything else would be as well.
                we already know middle not solution so we subtract 1'''
    return low

# =============================================================================
# SERIAL / ARDUINO HELPERS
# =============================================================================

def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    print("\n[PORTS] Available serial ports:")
    for p in ports:
        print(f"  {p.device} — {p.description}")
    for p in ports:
        if any(kw in p.description.lower() for kw in ["arduino", "ch340", "cp210", "usbserial", "usbmodem"]):
            print(f"\n[PORTS] Auto-detected Arduino at: {p.device}")
            return p.device
    print("\n[PORTS] Could not auto-detect Arduino. Plug it in and try again.")
    return None

def send_serial(cmd: bytes):
    global arduino
    if arduino and arduino.is_open:
        arduino.write(cmd)

def read_serial_loop():
    global arduino
    print("[SERIAL] Monitoring Arduino serial output...\n")
    while True:
        try:
            if arduino and arduino.in_waiting > 0:
                line = arduino.readline().decode("utf-8", errors="replace").strip()
                if line:
                    print(f"  [ARDUINO] {line}")
        except serial.SerialException as e:
            print(f"[SERIAL ERROR] {e}")
            break
        time.sleep(0.01)

# =============================================================================
# TONE / BUZZER
# =============================================================================

def play_tone(frequency: float, duration: float):
    t    = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    wave = 0.4 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
    sd.play(wave, samplerate=SAMPLE_RATE)
    sd.wait()

def buzz():
    """Short alert buzz on computer speakers."""
    play_tone(880, 0.2)

def play_startup_melody():
    notes = [(262, 0.5), (330, 0.5), (392, 0.5), (523, 0.5)]
    print("\n[BUZZER] Playing startup melody...")
    for freq, dur in notes:
        print(f"  ♪  {freq} Hz")
        play_tone(freq, dur)
    print("[BUZZER] Done.\n")

# =============================================================================
# VOICE COMMAND ACTIONS
# =============================================================================

def cmd_fan_on():
    print("[CMD] Fan ON")
    send_serial(b'F')           # Arduino handles 'F' → fan on

def cmd_fan_off():
    print("[CMD] Fan OFF")
    send_serial(b'f')           # Arduino handles 'f' → fan off

def cmd_led_on():
    print("[CMD] LED ON")
    send_serial(b'L')           # Arduino handles 'L' → LED on

def cmd_led_off():
    print("[CMD] LED OFF")
    send_serial(b'l')           # Arduino handles 'l' → LED off

def cmd_timer(seconds: int):
    print(f"[CMD] Timer set for {seconds} seconds")
    def _timer():
        time.sleep(seconds)
        print(f"\n[TIMER] {seconds}s timer done!")
        buzz()
    threading.Thread(target=_timer, daemon=True).start()

def cmd_stopwatch_start():
    global stopwatch_start, stopwatch_running
    stopwatch_start   = time.time()
    stopwatch_running = True
    print("[CMD] Stopwatch started.")

def cmd_stopwatch_query():
    global stopwatch_start, stopwatch_running
    if stopwatch_running and stopwatch_start:
        elapsed = time.time() - stopwatch_start
        print(f"[STOPWATCH] {elapsed:.1f} seconds have passed.")
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(f"{elapsed:.0f} seconds have passed")
        engine.runAndWait()
    else:
        print("[STOPWATCH] Stopwatch is not running.")

def cmd_party_mode():
    print("[CMD] Party mode! 🎉")
    def _party():
        for _ in range(20):          # flash 20 times
            send_serial(b'L')
            time.sleep(0.1)
            send_serial(b'l')
            time.sleep(0.1)
        send_serial(b'l')            # make sure LED ends off
        print("[CMD] Party mode done.")
    threading.Thread(target=_party, daemon=True).start()

# =============================================================================
# VOICE RECOGNITION — parse commands from speech
# =============================================================================

def parse_command(text: str):
    """
    Takes recognised speech text and maps it to an action.
    Uses binary_search to locate a keyword token in a sorted command list,
    keeping the math/search reuse the user asked for.
    """
    text = text.lower().strip()
    print(f"[VOICE] Heard: '{text}'")

    # Sorted keyword list — binary_search used to check membership
    sorted_keywords = sorted(["fan", "light", "timer", "stopwatch", "party", "time"])

    # ── Fan ──────────────────────────────────────────────────────────────────
    if "fan" in text:
        idx = binary_search("fan", sorted_keywords)
        print(f"[SEARCH] 'fan' found at sorted index {idx}")
        if "off" in text:
            cmd_fan_off()
        else:
            cmd_fan_on()

    # ── LED / Light ──────────────────────────────────────────────────────────
    elif "light" in text:
        idx = binary_search("light", sorted_keywords)
        print(f"[SEARCH] 'light' found at sorted index {idx}")
        if "off" in text:
            cmd_led_off()
        else:
            cmd_led_on()

    # ── Timer ─────────────────────────────────────────────────────────────────
    elif "timer" in text:
        idx = binary_search("timer", sorted_keywords)
        print(f"[SEARCH] 'timer' found at sorted index {idx}")
        # Try to extract a number from the phrase e.g. "timer 30"
        words   = text.split()
        seconds = 10                 # default if number unclear
        for w in words:
            if w.isdigit():
                seconds = int(w)
                break
        cmd_timer(seconds)

    # ── Stopwatch query ───────────────────────────────────────────────────────
    elif "how much time" in text or ("time" in text and "pass" in text):
        cmd_stopwatch_query()

    # ── Stopwatch start ───────────────────────────────────────────────────────
    elif "stopwatch" in text or "stop watch" in text:
        idx = binary_search("stopwatch", sorted_keywords)
        print(f"[SEARCH] 'stopwatch' found at sorted index {idx}")
        cmd_stopwatch_start()

    # ── Party mode ────────────────────────────────────────────────────────────
    elif "party" in text:
        idx = binary_search("party", sorted_keywords)
        print(f"[SEARCH] 'party' found at sorted index {idx}")
        cmd_party_mode()

    else:
        print("[VOICE] Command not recognised.")

def voice_listen_loop():
    recognizer = sr.Recognizer()

    print("[VOICE] Voice command listener active.")
    print("        Say: 'fan', 'light', 'timer 30', 'stopwatch',")
    print("             'how much time passed', 'party mode'\n")

    while True:
        try:
            # Record audio using sounddevice instead of PyAudio
            print("[VOICE] Listening...")
            audio_data = sd.rec(int(5 * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                                channels=1, dtype='int16')
            sd.wait()

            # Convert to AudioData format that SpeechRecognition understands
            audio_bytes = audio_data.tobytes()
            audio       = sr.AudioData(audio_bytes, SAMPLE_RATE, 2)

            text = recognizer.recognize_google(audio)
            parse_command(text)

        except sr.UnknownValueError:
            print("[VOICE] Could not understand audio.")
        except sr.RequestError as e:
            print(f"[VOICE] STT request error: {e}")
        except Exception as e:
            print(f"[VOICE] Error: {e}")
        time.sleep(0.1)

# =============================================================================
# MIC NOISE DETECTION (original RMS trigger → sends 'T'/'R' to Arduino)
# =============================================================================

def audio_callback(indata, frames, time_info, status):
    global sensor_triggered
    rms = np.sqrt(np.mean(indata ** 2))
    if rms > NOISE_THRESHOLD and not sensor_triggered:
        sensor_triggered = True
        print(f"\n[MIC] Noise detected! (RMS={rms:.4f})")
        threading.Thread(target=send_trigger, daemon=True).start()

def send_trigger():
    global sensor_triggered
    send_serial(b'T')
    time.sleep(3)
    send_serial(b'R')
    print("[SERIAL] Reset sent. Listening again...\n")
    sensor_triggered = False

# =============================================================================
# MAIN
# =============================================================================

def main():
    global arduino

    port = '/dev/cu.usbmodem101'
    if not port:
        print("\n[ERROR] No Arduino found. Plug it in and try again.")
        return

    try:
        arduino = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f"[SERIAL] Connected to {port} at {BAUD_RATE} baud.")
    except serial.SerialException as e:
        print(f"[ERROR] Could not open port {port}: {e}")
        return

    # Startup melody on computer speakers instead of buzzer
    play_startup_melody()

    # Background: read Arduino serial prints
    threading.Thread(target=read_serial_loop, daemon=True).start()

    # Background: voice command listener
    threading.Thread(target=voice_listen_loop, daemon=True).start()

    # Foreground: RMS noise trigger stream
    print(f"[MIC] RMS noise trigger active (threshold > {NOISE_THRESHOLD})...")
    print("      Press Ctrl+C to stop.\n")
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=BLOCK_SIZE,
            callback=audio_callback,
            dtype="float32",
        ):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[EXIT] Stopped.")
    finally:
        if arduino and arduino.is_open:
            arduino.close()
            print("[SERIAL] Port closed.")

if __name__ == "__main__":
    main()