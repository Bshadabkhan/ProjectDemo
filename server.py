from flask import Flask, render_template, request
import asyncio
import json
import base64
import os
import pyaudio
from websockets.asyncio.client import connect

app = Flask(__name__)

class SimpleGeminiVoice:
    def __init__(self):
        self.audio_queue = asyncio.Queue()
        self.api_key = "AIzaSyDTz38KnuvqeZyFT42sFMCacBd0SDsPQgw"  # Replace with your actual API key
        self.model = "gemini-2.0-flash-exp"
        self.uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={self.api_key}"
        # Audio settings
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.CHUNK = 512
        self.RATE = 16000

    async def start(self):
        # Initialize websocket
        self.ws = await connect(
            self.uri, additional_headers={"Content-Type": "application/json"}
        )
        await self.ws.send(json.dumps({"setup": {"model": f"models/{self.model}"}}))
        await self.ws.recv(decode=False)
        # Start audio streaming
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.capture_audio())
            tg.create_task(self.stream_audio())
            tg.create_task(self.play_response())

    async def capture_audio(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        while True:
            data = await asyncio.to_thread(stream.read, self.CHUNK)
            await self.ws.send(
                json.dumps(
                    {
                        "realtime_input": {
                            "media_chunks": [
                                {
                                    "data": base64.b64encode(data).decode(),
                                    "mime_type": "audio/pcm",
                                }
                            ]
                        }
                    }
                )
            )

    async def stream_audio(self):
        async for msg in self.ws:
            response = json.loads(msg)
            try:
                audio_data = response["serverContent"]["modelTurn"]["parts"][0][
                    "inlineData"
                ]["data"]
                self.audio_queue.put_nowait(base64.b64decode(audio_data))
            except KeyError:
                pass
            try:
                turn_complete = response["serverContent"]["turnComplete"]
            except KeyError:
                pass
            else:
                if turn_complete:
                    print("\nEnd of turn")
                    while not self.audio_queue.empty():
                        self.audio_queue.get_nowait()

    async def play_response(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=24000,
            output=True,
        )

        while True:
            data = await self.audio_queue.get()
            await asyncio.to_thread(stream.write, data)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/send_audio", methods=["POST"])
def send_audio():
    try:
        audio_data = base64.b64decode(request.get_data())
        voice_client.audio_queue.put_nowait(audio_data)
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error processing audio: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    voice_client = SimpleGeminiVoice()
    asyncio.run(debug=True)

