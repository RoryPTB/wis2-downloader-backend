# wis2-downloader-backend

## How to create frozen executables

Install dependencies

``
pip install -r requirements.txt
``

Then run

``
pyinstaller -F --paths=D:\env\Lib\site-packages app.py
``

This will create the executable ready to be used with `subscriptions.json` in the same directory.

## How to use frozen executables

### Subscription backend
For `subscribe-backend.exe` there are two arguments:

- `--broker` (required): The URL to the global broker
- `--download_dir` (optional): The local directory where the data will be downloaded to

### Catalogue backend
For `catalogue-backend.exe` there are three arguments:

- `--url` (optional): The URL to the global discovery catalogue (defaults to that of Canada)
- `--query` (optional): The search term used to query the catalogue (e.g. Synop)
- `--country` (optional): The country code used to filter the catalogue by datasets originating within the bounding box associated with that country.

Running this executable will create a JSON file `datasets.json`, which contains the (meta)datasets response from the global discovery catalogue.

### Broker synchronisation backend
For `broker-backend.exe` there are no arguments.

Running this executable will create a JSON file `brokers.json`, which contains the broker titles, URLs, as well as the datetime of the synchronisation.

## Usage of Python file

Install dependencies

``
pip install -r requirements.txt
``

Run subscriber

``
flask.exe --app .\app.py run
``

Example API call (HTTP GET) to add subscription

``
curl http://localhost:5000/wis2/subscriptions/add?topic=cache/a/wis2/%2B/%2B/data/core/weather/surface-based-observations/%23
``

Example API call (HTTP GET) to delete subscription

``
curl http://localhost:5000/wis2/subscriptions/delete?topic=cache/a/wis2/%2B/%2B/data/core/weather/surface-based-observations/%23
``

Example API call (HTTP GET) to list subscriptions

``
curl http://localhost:5000/wis2/subscriptions/list
``

## Notes

- Special symbols (e.g. +, #) in topics need to be URL encoded, + = %2B, # = %23.
- Initial subscriptions can be stored in subscriptions.json
- All data downloaded to ./downloads. This will be updated in future to allow configuration. 
- 2 child threads created, one to download the data and another for the subscriber
- The main program/thread is the flask Front end that manages the subscriptions and downloads


## Workflow

### Search and subscribe

```mermaid
sequenceDiagram
    Actor User
    box WIS2 Downloader
    Participant Front end
    Participant Back end
    end
    box WIS2 Global Services
    Participant Global catalogue
    Participant Global broker
    Participant Global cache
    end
    User->> Front end: Search for data
    Front end->>Global catalogue: Send search request (HTTP(S) GET)
    Global catalogue->>Front end: Return search result (list of datasets)
    Front end ->> User: Render list of datasets to user
    User ->> Front end: Click subscribe button
    Front end ->> Back end: Add subscription (HTTP(S) GET)
    Back end ->> Global broker: Subscribe (MQTT(S))
    Global broker ->> Back end: Acknowledge
    Back end ->> Back end: Update list of active subscriptions
    Back end ->> Front end: Return list of active subscriptions
    Front end ->> User: Render subscriptions    
```

### Unsubscribe

```mermaid
sequenceDiagram
    Actor User
    box WIS2 Downloader
    Participant Front end
    Participant Back end
    end
    box WIS2 Global Services
    Participant Global catalogue
    Participant Global broker
    Participant Global cache
    end
    User ->> Front end: View active subscriptions
    Front end ->> Back end: Request subscriptions (HTTP(S) GET)
    Back end ->> Front end: Return result
    Front end ->> User: Render subscriptions
    User ->> Front end: Click unsubscribe button
    Front end ->> Back end: Delete subscription (HTTP(S) GET)
    Back end ->> Global broker: Unubscribe (MQTT(S))
    Global broker ->> Back end: Acknowledge
    Back end ->> Back end: Update list of active subscriptions
    Back end ->> Front end: Return list of active subscriptions
    Front end ->> User: Render subscriptions    
```

### Download
```mermaid
sequenceDiagram
    Participant Storage
    box WIS2 Downloader
    Participant Front end
    Participant Back end
    end
    box WIS2 Global Services
    Participant Global catalogue
    Participant Global broker
    Participant Global cache
    end
    loop Active subscriptions
        Global broker ->> Back end: WIS2 notification(s) (MQTT(S))
        Back end ->> Back end: Validate notification
        Back end ->> Global cache: Request data (HTTP(S) GET)
        Global cache ->> Back end: Send data
        Back end ->> Back end: Verify data
        Back end ->> Storage: Save to storage (FS, S3, etc)
        Storage ->> Back end: Acknowledge
    end
```