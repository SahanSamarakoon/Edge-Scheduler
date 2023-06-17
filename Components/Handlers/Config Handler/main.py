# This is the config updater which runs in the edge nodes.
from urllib import request
import urllib.request as urllib

import requests
from flask import Flask
from flask import request as frequests

app = Flask(__name__)

# Start Flask server
print("flask server started.....")


@app.route("/", methods=['GET'])
def hello_from_updater():
    return "hello world"


@app.route('/updateConfig', methods=['GET'])
def update_config():
    esp32_url = 'http://192.168.4.1/'

    config = frequests.args.get('config')
    req_url = esp32_url + 'control'
    params = {'quality': config}
    print(config, req_url)
    response = requests.get(req_url, params=params)

    if response.status_code == 200:
        return response.text
        print(response.text)
    else:
        print('config update failed with status code: ', response.status_code)


if __name__ == '__main__':
    app.run(host="localhost", port=5000, debug=True)
