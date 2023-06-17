# This is the config updater which runs in the edge nodes.
from urllib import request
import urllib.request as urllib

import requests
from flask import Flask
from flask import request as frequests

app = Flask(__name__)

# Start Flask server
print("flask server started.....")
esp32_url = 'http://192.168.4.1/'


@app.route("/", methods=['GET'])
def hello_from_updater():
    return "hello world"


@app.route('/gitFirmwareUpdate', methods=['GET'])
def git_firmware_update():
    req_url = esp32_url + 'otaGit'
    response = requests.get(req_url)

    if response.status_code == 200:
        return response.text
        print(response.text)
    else:
        print('firmware Update failed: ', response.status_code)


@app.route('/sdFirmwareUpdate', methods=['GET'])
def sd_firmware_update():
    req_url = esp32_url + 'otaSd'
    print(req_url)
    response = requests.get(req_url)

    if response.status_code == 200:
        return response.text
        print(response.text)
    else:
        print('firmware update failed with status code: ', response.status_code)


@app.route('/forceRestart', methods=['GET'])
def force_restart():
    req_url = esp32_url + 'restart'
    print(req_url)
    response = requests.get(req_url)

    if response.status_code == 200:
        return response.text
        print(response.text)
    else:
        print('restart failed with status code: ', response.status_code)


if __name__ == '__main__':
    app.run(host="localhost", port=5001, debug=True)
