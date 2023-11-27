import requests
import json
from datetime import datetime

# Replace with actual GDC API URL
GDC_API_URL = "https://api.weather.gc.ca/collections/wis2-discovery-metadata/items"  # noqa


def fetch_data():
    """
    Fetch latest dataset from the GDC API with optional bounding box and query filters.

    :return: JSON data from the API.
    """
    try:
        response = requests.get(GDC_API_URL)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None


def extract_latest_brokers(item):
    """
    Extract the latest broker URLs from an API response item.

    :param item: Single item from the API response.
    :return: Extracted data as a dictionary.
    """
    # Initialise the brokers array
    brokers = []

    # In the links where the rel is 'items', the href starts with 'mqtt',
    # and the channel starts with 'cache', the global brokers can be found
    # in the the href after the 'mqtt://every.everyone@' part and before
    # the ':8883' part
    for link in item.get('links', []):
        if link.get('rel') == 'items' and link.get('href').startswith('mqtt') and link.get('channel').startswith('cache'):
            broker = link.get('href').split('@')[1].split(':')[0]
            brokers.append(broker)

    # Return the brokers and the datetime of the synchronisation
    return {
        "brokers": brokers,
        "sync_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def write_to_json(filename, data):
    """
    Write data to a JSON file.

    :param filename: Name of the file to write to.
    :param data: Data to write.
    """
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)
        print(f"Latest broker URLs written to {filename}")


def main():
    api_response = fetch_data()
    if api_response:
        items = api_response.get('features', [])
        item = items[0] # Only need the first item to get broker URLs
        extracted_brokers = extract_latest_brokers(item)
        write_to_json('brokers.json', extracted_brokers)


if __name__ == "__main__":
    main()
