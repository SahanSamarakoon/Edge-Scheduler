import cv2
import argparse

parser = argparse.ArgumentParser(description='Black frames monitor')
parser.add_argument('--url', type=str, help='URL of the video feed')
parser.add_argument('--intensity', type=int, help='Intensity threshold')
parser.add_argument('--count', type=int, help='Number of bitrate measurements')
args = parser.parse_args()
video_feed_url = args.url
measurements_limit = args.count

def is_blacked_out(frame, intensity_threshold):
    average_intensity = cv2.mean(frame)[0]
    return average_intensity < intensity_threshold

def main():
    
    # Intensity threshold for blacked-out frames
    intensity_threshold = args.intensity  # Adjust this value according to your needs

    # Open the video stream
    video_capture = cv2.VideoCapture(video_feed_url)

    while video_capture.isOpened():
        for x in range(0,measurements_limit):
            ret, frame = video_capture.read()

            # Break the loop if the video stream ends
            if not ret:
                break

            # Check if the frame is blacked-out
            if is_blacked_out(frame, intensity_threshold):
                print("0")
            else:
                print("1")
        break

    # Release the video stream and close windows
    video_capture.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()

# sample command
# python blackframes_monitor.py --url "http://10.10.49.114:6677/videofeed?username=&password=" --intensity 10 --count 20
