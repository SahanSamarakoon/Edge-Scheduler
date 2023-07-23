from scapy.all import sniff
import time
import cv2
import argparse

parser = argparse.ArgumentParser(description='Bitrate monitor')
parser.add_argument('--ip', type=str, help='IP address of the ESP32')
parser.add_argument('--port', type=str, help='port number used for the video stream')
parser.add_argument('--url', type=str, help='URL of the video feed')
parser.add_argument('--count', type=int, help='Number of bitrate measurements')
args = parser.parse_args()
video_feed_url = args.url
measurements_limit = args.count
esp32_ip = args.ip
video_port = args.port

# Define a packet filter to capture only packets from the ESP32 and the video port
packet_filter = f"src host {esp32_ip} and tcp port {video_port}"

# Define a function to calculate the bitrate and FPS
def calculate_bitrate_and_fps(duration):
    # Initialize variables for calculating bitrate and FPS
    bit_count = 0
    frame_count = 0
    start_time = time.time()

    # Define a custom callback function to process each captured packet
    def packet_callback(packet):
        nonlocal bit_count, frame_count

        # Get the size of the packet payload in bytes
        packet_size = len(packet.payload)

        # Update the total bit count
        bit_count += packet_size * 8

        # Update the frame count
        frame_count += 1

    # Start capturing packets using the filter and the callback function for the specified duration
    sniff(filter=packet_filter, prn=packet_callback, timeout=duration)

    # Calculate the elapsed time, bitrate, and FPS
    elapsed_time = time.time() - start_time
    bitrate = bit_count / elapsed_time / 1000  # Convert to Mbps
    fps = frame_count / elapsed_time

    return bitrate, fps

# Calculate the bitrate and FPS 10 times and print the values each time
for i in range(measurements_limit):
    cap = cv2.VideoCapture(video_feed_url)
    bitrate, fps = calculate_bitrate_and_fps(1)  # Capture packets for 1 second
    print("Bitrate:", round(bitrate,2), "Kbps", "FPS:", round(fps))

# Example command to run the script
# python scapy_main.py --ip 10.10.49.114 --port 6677 --url "http://10.10.49.114:6677/videofeed?username=&password=" --count 15