import argparse
import base64
import configparser
import json
import threading
import time
import pyaudio
import websocket
import requests
import sys
from websocket._abnf import ABNF
from ibm_watson import TextToSpeechV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson import AssistantV2
from ibm_watson import ApiException
from enum import Enum
from typing import Dict, List
from ibm_cloud_sdk_core import BaseService, DetailedResponse
from ibm_cloud_sdk_core.authenticators.authenticator import Authenticator
from ibm_cloud_sdk_core.get_authenticator import get_authenticator_from_environment
from ibm_cloud_sdk_core.utils import convert_model



CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 10
FINALS = []
LAST = None

REGION_MAP = {
    'us-east': 'gateway-wdc.watsonplatform.net',
    'us-south': 'stream.watsonplatform.net',
    'eu-gb': 'stream.watsonplatform.net',
    'eu-de': 'stream-fra.watsonplatform.net',
    'au-syd': 'gateway-syd.watsonplatform.net',
    'jp-tok': 'gateway-syd.watsonplatform.net',
}


def read_audio(ws, timeout):
    global RATE
    p = pyaudio.PyAudio()
    RATE = int(p.get_default_input_device_info()['defaultSampleRate'])
    stream = p.open(format=FORMAT,channels=CHANNELS,rate=RATE,input=True,frames_per_buffer=CHUNK)

    print("* start recording")
    rec = timeout or RECORD_SECONDS

    for i in range(0, int(RATE / CHUNK * rec)):
        data = stream.read(CHUNK)
        ws.send(data, ABNF.OPCODE_BINARY)
    stream.stop_stream()
    stream.close()
    print("* done recording")
    data = {"action": "stop"}
    ws.send(json.dumps(data).encode('utf8'))
    time.sleep(1)
    ws.close()
    p.terminate()


def on_message(self, msg):
    global LAST
    data = json.loads(msg)
    if "results" in data:
        if data["results"][0]["final"]:
            FINALS.append(data)
            LAST = None
        else:
            LAST = data
        print(data['results'][0]['alternatives'][0]['transcript'])
        

def on_error(self, error):
    print(error)


def on_close(ws):
    global LAST
    global TextMassage
    global transcript
    authenticator = IAMAuthenticator('gPU0j2XhQJBuYIZ2SPRDUHm4Fq8iaTibE_VVKdEtNaJZ')
    assistant = AssistantV2(
    version='2021-06-14',
    authenticator=authenticator
    )

    assistant.set_service_url('https://api.eu-gb.assistant.watson.cloud.ibm.com')

    if LAST:
        FINALS.append(LAST)
    transcript = "".join([x['results'][0]['alternatives'][0]['transcript']
                          for x in FINALS])
    session = assistant.create_session(
    assistant_id='f1aa3001-9d92-4344-8d28-74c329130955'
    ).get_result()

    session_js = json.dumps(session, indent=2)
    session_dict = json.loads(session_js)
    session_id = session_dict['session_id']
    message = assistant.message(
    "f1aa3001-9d92-4344-8d28-74c329130955",
    session_id ,
    input={'text': transcript },
    ).get_result()

    message_js = json.dumps(message, indent=2)
    message_dict = json.loads(message_js) 
    TextMassage = message_dict["output"]["generic"][0]["text"]
    print(TextMassage)
    return transcript




def on_open(ws):
    args = ws.args
    data = {
        "action": "start",
        "content-type": "audio/l16;rate=%d" % RATE,
        "continuous": True,
        "interim_results": True,
        "word_confidence": True,
        "timestamps": True,
        "max_alternatives": 3
    }
    ws.send(json.dumps(data).encode('utf8'))
    threading.Thread(target=read_audio,
                     args=(ws, args.timeout)).start()

def get_url():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    region = config.get('auth', 'region')
    host = REGION_MAP[region]
    return ("wss://{}/speech-to-text/api/v1/recognize"
           "?model=en-AU_BroadbandModel").format(host)

def get_auth():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    apikey = config.get('auth', 'apikey')
    return ("apikey", apikey)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Transcribe Watson text in real time')
    parser.add_argument('-t', '--timeout', type=int, default=5)
    args = parser.parse_args()
    return args


def main():
    headers = {}
    userpass = ":".join(get_auth())
    headers["Authorization"] = "Basic " + base64.b64encode(
        userpass.encode()).decode()
    url = get_url()
    ws = websocket.WebSocketApp(url,
                                header=headers,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.args = parse_args()
    ws.run_forever()

    with open ('text2.txt', 'w') as file:
            file.write(on_close(ws))

if __name__ == "__main__":
    main()




url = 'https://api.au-syd.text-to-speech.watson.cloud.ibm.com/instances/50163564-7bb2-4036-9a2a-7021494670a8'
apikey = 'XDAvW3OdtkKLgGLDDQERRGEysBlX0zxIBPESHNsrfXTq' 

def main():


    authenticator = IAMAuthenticator(apikey)

    TtS = TextToSpeechV1(authenticator=authenticator)

    TtS.set_service_url(url)

    with open('text2.txt', 'r') as file: 
        text = file.read()

    with open('speech2.mp3', 'wb') as audio_file:
        res = TtS.synthesize(TextMassage, accept='audio/mp3', voice='en-US_AllisonV3Voice').get_result()
        audio_file.write(res.content)

if __name__ == "__main__":
    main()

