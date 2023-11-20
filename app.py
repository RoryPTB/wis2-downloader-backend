from flask import Flask, request
import json
import logging
import os
import sys
import paho.mqtt.client as mqtt
from pathlib import Path
import queue
import ssl
import threading
import urllib3
from urllib.parse import urlsplit
import argparse

# LOGGER
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S"
)
LOGGER = logging.getLogger(__name__)

# Global variables
urlQ = queue.Queue()
http = urllib3.PoolManager()

def create_app(args, subs, test_config=None):
    LOGGER.debug("Creating app")
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    # If the download argument is given, download data there
    if args.download_dir is not None:
        # Check if the directory exists and is writable
        if (os.path.exists(args.download_dir) and
                os.access(args.download_dir, os.W_OK)):
            start_download_thread(subs)
        else:
            raise FileNotFoundError("Specified download directory does not exist or is not writable.") # noqa
    else:
        LOGGER.info("Download directory not specified. Data will not be downloaded.")

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/wis2/subscriptions/list')
    def list_subscriptions():
        return subs

    @app.route('/wis2/subscriptions/add')
    def add_subscription():
        topic = request.args.get('topic', None)
        if topic==None:
            return "No topic passed"
        else:
            if topic in subs:
                LOGGER.debug(f"Topic {topic} already subscribed")
            else:
                client.subscribe(f"{topic}")
                subs[topic] = args.download_dir
        return subs

    @app.route('/wis2/subscriptions/delete')
    def delete_subscription():
        topic = request.args.get('topic', None)
        if topic==None:
            return "No topic passed"
        else:
            client.unsubscribe(f"{topic}")
            LOGGER.info(f"{topic}/#")
            if topic in subs:
                del subs[topic]
            else:
                LOGGER.info(f"Topic {topic} not found")
                for sub in subs:
                    LOGGER.info(sub, topic)
        return subs

    return app


def downloadWorker(subs):
    # Declare global variables
    global urlQ
    global http

    while True:
        LOGGER.debug(f"Messages in queue: {urlQ.qsize()}")
        job = urlQ.get()
        output_dir = subs.get(job['topic'])
        if output_dir == None:
            output_dir = "downloads"
        output_dir = Path(output_dir)
        # get data ID, used to set directory to write to
        dataid = Path(job['payload']['properties']['data_id'])
        # we need to replace colons in output path
        dataid = Path(str(dataid).replace(":",""))
        output_path = Path(output_dir, dataid)
        # create directory
        output_path.parent.mkdir(exist_ok=True, parents=True)
        LOGGER.info(output_path.parent)
        # find canonical in links
        for link in job['payload']['links']:
            if link['rel'] == "canonical":
                path = urlsplit(link['href']).path
                filename = os.path.basename(path)
                LOGGER.debug(f"{filename}")
                # check if already in output directory, if not download
                if not output_path.is_file():
                    LOGGER.debug(f"Downloading {filename}")
                    try:
                        response = http.request("GET", link['href'])
                    except Exception as e:
                        LOGGER.error(f"Error downloading {link['href']}")
                        LOGGER.error(e)
                    try:
                        output_path.write_bytes(response.data)
                    except Exception as e:
                        LOGGER.error(f"Error saving to disk: {args.download_dir}/{filename}") # noqa
                        LOGGER.error(e)

        urlQ.task_done()


# Function to start the download thread
def start_download_thread(subs):
    downloadThread = threading.Thread(target=downloadWorker(subs), daemon=True)
    downloadThread.start()


# MQTT stuff
def on_connect(client, userdata, flags, rc):  # subs managed by sub-manager
    LOGGER.debug("connected")


def on_message(client, userdata, msg):
    # Declare urlQ as global
    global urlQ

    LOGGER.debug("message received")
    # create new job and add to queue
    job = {
        'topic': msg.topic,
        'payload': json.loads(msg.payload)
    }
    urlQ.put(job)


def on_subscribe(client, userdata, mid, granted_qos):
    LOGGER.debug(("on subscribe"))


def main():
    # Parse system arguments
    parser = argparse.ArgumentParser(
        description="WIS2 Downloader Backend Configuration")
    parser.add_argument(
        "--broker", help="The global broker URL")
    parser.add_argument(
        "--download_dir", default=None, help="Optional download directory")
    args = parser.parse_args()

    # Determine base path of application
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundled executable,
        # the sys.executable path will be the path to
        # the application executable
        application_path = os.path.dirname(sys.executable)
    else:
        # If it's run as a normal Python script, the sys.executable 
        # path will be the path to the Python interpreter
        application_path = os.path.dirname(os.path.realpath(__file__))

    # From the base path get the path of the subscriptions json file
    subscriptions_path = os.path.join(application_path, 'subscriptions.json')
    
    print("Subscriptions path", subscriptions_path)

    # Load subs
    with open(subscriptions_path) as fh:
        subs = json.load(fh)
        
    print("Subs: ", subs)

    broker = args.broker
    port = 443
    pwd = "everyone"
    uid = "everyone"
    protocol = "websockets"

    LOGGER.debug("Initialising client")
    client = mqtt.Client(transport=protocol)
    client.tls_set(ca_certs=None, certfile=None, keyfile=None,
                cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS,
                ciphers=None)
    client.username_pw_set(uid, pwd)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    LOGGER.debug("Connecting")
    result = client.connect(host=broker, port=port)
    LOGGER.debug(result)
    mqtt_thread = threading.Thread(target=client.loop_forever, daemon=True).start()

    for sub in subs:
        client.subscribe(sub)

    # Create the app
    app = create_app(args, subs)
    app.run(debug=True)


if __name__ == '__main__':
    main()
