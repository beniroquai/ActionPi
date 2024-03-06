# -*- coding: utf-8 -*-
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse, FileResponse
from picamera2 import Picamera2
import uvicorn
import io
import time

app = FastAPI()

# Initialize the Pi camera
picam2 = Picamera2()

# Define separate configurations for preview and capture
preview_config = picam2.create_preview_configuration(main={"size": (320, 240)})
still_config = picam2.create_still_configuration()

# Set an initial configuration; can be changed later
picam2.configure(preview_config)
picam2.start()

def generate_mjpeg():
    picam2.configure(preview_config)  # Configure for preview
    while True:
        stream = io.BytesIO()
        picam2.capture_file(stream, format="jpeg")
        stream.seek(0)
        frame = stream.read()

        boundary = "--frameboundary"
        yield (b"--%b\r\n" b"Content-Type: image/jpeg\r\n\r\n" % boundary.encode() + frame + b"\r\n")
        time.sleep(0.1)

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_mjpeg(), media_type="multipart/x-mixed-replace;boundary=frameboundary")

@app.get("/capture/")
def capture_picture():
    picam2.configure(still_config)  # Configure for high-res capture
    picam2.capture_file("/tmp/high_res.jpg")
    picam2.configure(preview_config)  # Reconfigure back to preview if needed
    return FileResponse("/tmp/high_res.jpg", media_type="image/jpeg")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
