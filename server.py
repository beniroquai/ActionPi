from flask import Flask, send_from_directory, render_template, request, redirect, url_for, Response
from zipfile import ZipFile
import os
import shutil
import threading
from datetime import datetime
from subprocess import call
from PIL import Image
import psutil
import io

app = Flask(__name__)

import time
try:
    from rpi_ws281x import PixelStrip, Color
    IS_NEOPIXEL = True
except:
    IS_NEOPIXEL = False

try:
    from picamera2.picamera2 import Picamera2
    IS_PICAMERA2 = True
    # Initialize your camera
    picam2 = Picamera2()
    preview_config = picam2.create_preview_configuration(main={"size": (320, 240)})
    still_config = picam2.create_still_configuration()

    # Set an initial configuration; can be changed later
    picam2.configure(still_config)
    picam2.start()
    picam2.capture_file("/home/pi/camera/test.jpg", format="jpeg")
    

except Exception as e:
    print("Picamera2 not found")
    print(e)
    IS_PICAMERA2 = False


@app.route('/stream')
def stream():
    """Streams the camera images as a multipart HTTP response."""
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def gen_frames():
    if not IS_PICAMERA2:
        return
    picam2.configure(preview_config)  # Configure for preview
    while True:
        stream = io.BytesIO()
        picam2.capture_file(stream, format="jpeg")
        stream.seek(0)
        frame = stream.read()

        boundary = "--frameboundary"
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')        
        time.sleep(0.1)


def ____gen_frames():
    """Generator function that captures images and yields them as frames."""
    while True:
        frame = picam2.capture_array()  # Capture an image from the camera
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

class NeoPixelStrip:
    def __init__(self, led_count=10, led_pin=18, led_freq_hz=800000, led_dma=10,
                 led_brightness=255, led_invert=False, led_channel=0):
        self.led_count = led_count
        self.led_pin = led_pin
        self.led_freq_hz = led_freq_hz
        self.led_dma = led_dma
        self.led_brightness = led_brightness
        self.led_invert = led_invert
        self.led_channel = led_channel
        
        if not IS_NEOPIXEL:
            return
        self.strip = PixelStrip(self.led_count, self.led_pin, self.led_freq_hz,
                                self.led_dma, self.led_invert, self.led_brightness,
                                self.led_channel)
        self.strip.begin()
    
    def set_color(self, color):
        """Set the color of the whole strip."""
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, color)
        self.strip.show()
    
    def turn_off(self):
        """Turn off all pixels."""
        if not IS_NEOPIXEL:
            return

        self.colorWipe(Color(0, 0, 0))
    
    def turn_on(self, color=(255, 255, 255)):
        """Turn on all pixels to white or specified color."""
        if not IS_NEOPIXEL:
            return
        self.colorWipe(Color(color))

    # Define functions which animate LEDs in various ways.
    def colorWipe(self, color, wait_ms=0):
        """Wipe color across display a pixel at a time."""
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, color)
            self.strip.show()
            time.sleep(wait_ms / 1000.0)




# Create an instance of the NeoPixelStrip class
led_strip = NeoPixelStrip()
    
 


BASE_DIR = '.'#/home/pi/camera'  # This should be the base directory where your files are located
DIRECTORIES = ['photos', 'videos', 'timelapses']
# make all directories if they don't exist
for dir in DIRECTORIES:
    if not os.path.exists(os.path.join(BASE_DIR, dir)):
        os.mkdir(os.path.join(BASE_DIR, dir))
THUMBNAIL_DIRECTORIES = {dir: os.path.join('thumbnails', dir) for dir in DIRECTORIES}

thumbnail_base_dir = os.path.join(BASE_DIR, 'thumbnails')
if not os.path.exists(thumbnail_base_dir):
    os.mkdir(thumbnail_base_dir)

@app.route('/')
def index():
    all_files = {}
    for directory in DIRECTORIES:
        dir_path = os.path.join(BASE_DIR, directory)
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            # Sort files by creation time, newest first
            files.sort(key=lambda x: os.path.getctime(os.path.join(dir_path, x)), reverse=True)
            all_files[directory] = files
        else:
            all_files[directory] = []

    temperature = cpu_temperature()
    disk_space = disk_usage()

    return render_template('index.html', all_files=all_files, temperature=temperature, disk_space=disk_space)


# Capturing photo
@app.route('/start_photo_capture', methods=['GET'])
def start_photo_capture():
    capture_photo()
    return redirect(url_for('index'))

def turn_on_leds():
    try:
        print("Turning on LEDs...")
        led_strip.turn_on()  # Turn on all LEDs to white
        time.sleep(0.5)  # Wait for half a second
    except Exception as e:
        print(e)
        
def turn_off_leds():
    try:
        print("Turning off LEDs...")
        led_strip.turn_off()  # Turn off all LEDs
        time.sleep(1)  # Wait for a second
    except Exception as e:
        print(e)
        
def capture_photo():
    # Ensure LEDs are turned on before capturing
    turn_on_leds()

    # Check and create the photos directory if it doesn't exist
    photos_dir = os.path.join(BASE_DIR, "photos")
    if not os.path.exists(photos_dir):
        os.makedirs(photos_dir)

    # Generate the filename
    filename = datetime.now().strftime("%Y%m%d_%H%M%S.jpg")
    filepath = os.path.join(photos_dir, f"photo_{filename}")
    print(f"Capturing photo to {filepath}")

    # Capture the photo using Picamera2
    if IS_PICAMERA2:
        #picam2.configure(still_config)
        picam2.capture_file(filepath)
    
    # Ensure LEDs are turned off after capturing
    turn_off_leds()
      
    

# Capturing video
@app.route('/start_video_capture', methods=['GET'])
def start_video_capture():
    duration = request.args.get('duration', default=1, type=int)
    record_video(duration)
    return redirect(url_for('index'))

def record_video(duration):
    # Create directory if it doesn't exist
    if not os.path.exists(BASE_DIR + "/videos"):
        os.mkdir(BASE_DIR + "/videos")

    # Generate filename
    filename_h264 = datetime.now().strftime(BASE_DIR + "/videos/video_%Y%m%d_%H%M%S.h264")
    filename_mp4 = filename_h264.replace('.h264', '.mp4')

    # Record the video
    turn_on_leds()
    os.system(f"libcamera-vid -t {duration * 1000} --framerate 24 --width 1920 --height 1080 -o {filename_h264}")
    turn_off_leds()
    
    # Convert the video to mp4
    os.system(f"ffmpeg -i {filename_h264} -vcodec copy {filename_mp4}")

    # Delete the original .h264 file
    os.remove(filename_h264)


# Capturing timelapse
is_capture_timelapse = False
@app.route('/start_timelapse', methods=['GET'])
def start_timelapse():
    global is_capture_timelapse
    is_capture_timelapse = True
    interval = request.args.get('interval', default=1, type=int)
    duration = request.args.get('duration', default=1, type=int)

    capture_timelapse(interval, duration)
    return redirect(url_for('index'))

@app.route('/stop_timelapse', methods=['GET'])
def stop_timelapse():
    global is_capture_timelapse
    is_capture_timelapse = False
    return redirect(url_for('index'))


def capture_timelapse(interval, duration):
    # Create directory if it doesn't exist
    global is_capture_timelapse
    timelapse_dir = os.path.join(BASE_DIR, "timelapses")
    if not os.path.exists(timelapse_dir):
        os.makedirs(timelapse_dir)
    
    # Generate the folder and filename
    foldername = datetime.now().strftime("timelapse_%Y%m%d_%H%M%S")
    folder_path = os.path.join(timelapse_dir, foldername)
    os.makedirs(folder_path)
    print(f"Capturing timelapse in {folder_path}")

    t0 = time.time()
    count = 0
    while is_capture_timelapse and time.time() - t0 < duration * 60:  # duration in minutes
        filename = os.path.join(folder_path, f"image_{count:04d}.jpg")
        if IS_PICAMERA2:
            #picam2.configure(still_config)
            picam2.capture_file(filename)
        time.sleep(interval)
        count += 1

@app.route('/download/<path:filepath>')
def download(filepath):
    full_filepath = os.path.join(BASE_DIR, filepath)
    # If it's a directory, zip it first
    if os.path.isdir(full_filepath):
        output_filename = f"{os.path.basename(filepath)}.zip"
        output_filepath = os.path.join(os.path.dirname(full_filepath), output_filename)
        # Create a Zip file
        with ZipFile(output_filepath, 'w') as zipf:
            for foldername, subfolders, filenames in os.walk(full_filepath):
                for filename in filenames:
                    # create complete filepath of file in directory
                    file_to_zip = os.path.join(foldername, filename)
                    # Add file to zip
                    zipf.write(file_to_zip, os.path.relpath(file_to_zip, full_filepath))
        return send_from_directory(*os.path.split(output_filepath), as_attachment=True)
    else:
        dirpath, filename = os.path.split(full_filepath)
        return send_from_directory(dirpath, filename, as_attachment=True)


@app.route('/download_all/<directory>')
def download_all(directory):
    dir_path = os.path.join(BASE_DIR, directory)
    output_filename = f"{directory}.zip"
    output_filepath = os.path.join(BASE_DIR, output_filename)

    # Create a Zip file
    with ZipFile(output_filepath, 'w') as zipf:
        for foldername, subfolders, filenames in os.walk(dir_path):
            for filename in filenames:
                # create complete filepath of file in directory
                filepath = os.path.join(foldername, filename)
                # Add file to zip
                zipf.write(filepath, os.path.relpath(filepath, dir_path))

    return send_from_directory(BASE_DIR, output_filename, as_attachment=True)




@app.route('/cpu_temperature')
def cpu_temperature():
    return str("all good")

@app.route('/disk_usage')
def disk_usage():
    total, used, free = shutil.disk_usage('/')
    # Convert from bytes to gigabytes
    total_gb = round(total / (2**30), 1)
    used_gb = round(used / (2**30), 1)
    free_gb = round(free / (2**30), 1)
    return {"total_gb": total_gb, "used_gb": used_gb, "free_gb": free_gb}



@app.route('/shutdown', methods=['POST'])
def shutdown():
    call("sudo shutdown -h now", shell=True)
    return redirect(url_for('index'))



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)