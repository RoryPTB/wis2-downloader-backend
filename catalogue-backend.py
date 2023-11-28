import argparse
import requests
import json
import os
import sys

CANADA_GDC_API_URL = "https://api.weather.gc.ca/collections/wis2-discovery-metadata/items"  # noqa


def fetch_data(url, bbox=None, query=None):
    """
    Fetch data from the GDC API with optional bounding box and query filters.

    :param url: URL of the GDC API.
    :param bbox: Bounding box coordinates as a list [lat1, lon1, lat2, lon2].
    :param query: Text query for filtering.
    :return: JSON data from the API.
    """
    params = {}
    if bbox:
        params['bbox'] = ','.join(map(str, bbox))
    if query:
        params['q'] = query

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None


def extract_relevant_data(item):
    """
    Extract relevant data from an API response item.

    :param item: Single item from the API response.
    :return: Extracted data as a dictionary.
    """
    properties = item.get('properties', {})
    topic_hierarchy = properties.get('wmo:topicHierarchy')

    # Sometimes, the topic hierarchy is not in the properties, but in the
    # links whre the rel is 'data'
    for link in item.get('links', []):
        if link.get('rel') == 'data' and 'wmo:topic' in link:
            topic_hierarchy = link['wmo:topic']
            break

    # Get the centre id from the identifier, depending on the structure
    # of the identifier
    identifier = properties.get('identifier')
    centre_id = None

    if identifier is not None:
        tokens = identifier.split(':')

        if ':' not in identifier:
            tokens = identifier.split('.')
            centre_id = tokens[1]
        if len(tokens) < 5:
            centre_id = tokens[1]

        centre_id = tokens[3]

    return {
        "id": properties.get('identifier'),
        "center_id": centre_id,
        "title": properties.get('title'),
        "topic_hierarchy": topic_hierarchy,
        "creation_date": properties.get('created'),
        "data_policy": properties.get('wmo:dataPolicy')
    }


def write_to_json(filename, data):
    """
    Write data to a JSON file.

    :param filename: Name of the file to write to.
    :param data: Data to write.
    """
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)
        print(f"Data written to {filename}")


def main():
    parser = argparse.ArgumentParser(description='GDC API Data Fetcher')
    parser.add_argument('--url', type=str, default=CANADA_GDC_API_URL,)
    parser.add_argument('--bbox', nargs=4, type=float,
                        help='Bounding box [lat1, lon1, lat2, lon2]')
    parser.add_argument('--query', type=str, help='Text query')
    args = parser.parse_args()

    api_response = fetch_data(url=args.url, bbox=args.bbox, query=args.query)
    if api_response:
        items = api_response.get('features', [])
        extracted_data = [extract_relevant_data(item) for item in items]

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

        # From the base path get the path to write the broker JSON file
        output_path = os.path.join(application_path, 'datasets.json')

        write_to_json(output_path, extracted_data)


if __name__ == "__main__":
    main()
