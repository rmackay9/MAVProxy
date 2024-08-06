'''
AI Chat Module voice-to-text class
Randy Mackay, December 2023

AP_FLAKE8_CLEAN
'''

import time

try:
    import pyaudio  # install using, "sudo apt-get install python3-pyaudio"
    import wave     # install with "pip3 install wave"
    from openai import OpenAI
except Exception:
    print("chat: failed to import pyaudio, wave or openai.  See https://ardupilot.org/mavproxy/docs/modules/chat.html")
    exit()

from MAVProxy.modules.lib import multiproc

class chat_voice_to_text():
    def __init__(self):
        # initialise variables
        self.client = None
        self.assistant = None
        self.stop_recording = False
        self.external_cmd_queue = multiproc.Queue()

    # set the OpenAI API key
    def set_api_key(self, api_key_str):
        self.client = OpenAI(api_key=api_key_str)

    # check connection to OpenAI assistant and connect if necessary
    # returns True if connection is good, False if not
    def check_connection(self):
        # create connection object
        if self.client is None:
            try:
                self.client = OpenAI()
            except Exception:
                print("chat: failed to connect to OpenAI")
                return False

        # return True if connected
        return self.client is not None

    # record audio from microphone
    # returns filename of recording or None if failed
    def record_audio(self):
        # Initialize PyAudio
        p = pyaudio.PyAudio()

        # Open stream
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        except Exception:
            print("chat: failed to connect to microphone")
            return None

        # calculate time recording should stop
        curr_time = time.time()
        time_stop = curr_time + 5
        self.stop_recording = False

        # empty queue
        self.external_cmd_queue.empty()

        # record until specified time
        print("chat: voice-to-text started recording!")
        frames = []
        while curr_time < time_stop and not self.stop_recording:
            data = stream.read(1024)
            frames.append(data)
            curr_time = time.time()
            queue_item = self.external_cmd_queue.get_nowait()
            print("chat:" + queue_item)
            if queue_item == "stop":
                print("chat: voice-to-text got stop command!")
                self.external_cmd_queue.empty()
                break

        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()

        # Save audio file
        wf = wave.open("recording.wav", "wb")
        wf.setnchannels(1)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
        wf.setframerate(44100)
        wf.writeframes(b''.join(frames))
        wf.close()
        return "recording.wav"

    # stop recording audio
    def stop_record_audio(self):
        print("chat: voice-to-text will stop recording!")
        self.stop_recording = True
        self.external_cmd_queue.put("stop")

    # convert audio to text
    # returns transcribed text on success or None if failed
    def convert_audio_to_text(self, audio_filename):
        # check connection
        if not self.check_connection():
            return None

        # Process with Whisper
        audio_file = open(audio_filename, "rb")
        transcript = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text")
        return transcript
