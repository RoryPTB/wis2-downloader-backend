import argparse
import requests
import json
import os
import sys

CANADA_GDC_API_URL = "https://api.weather.gc.ca/collections/wis2-discovery-metadata/items"  # noqa

COUNTRY_METADATA_URL = "https://raw.githubusercontent.com/wmo-im/wis2box/main/config-templates/countries.json"  # noqa


def fetch_countries_metadata():
    """
    Fetch the country metadata from the wis2box repository.

    :return: JSON data from the repository.
    """
    try:
        response = requests.get(COUNTRY_METADATA_URL)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching country metadata: {e}")
        return None


def get_bbox_for_country(countries_metadata, country_code):
    """
    Get the bounding box for a country from the country metadata.

    :param countries_metadata: Country metadata from the wis2box repository.
    :param country_code: The country code to get the bounding box for.
    :return: Bounding box coordinates as a list [lat1, lon1, lat2, lon2].
    """
    country_info = countries_metadata["countries"].get(country_code.lower())
    if country_info is not None:
        bbox = country_info.get('bbox', {})
        return [bbox.get('minx'), bbox.get('miny'), bbox.get('maxx'), bbox.get('maxy')]  # noqa
    else:
        return None


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

    # The topic hierarchy is found in the 'channel' property in 'links
    # where the rel is 'items' and the href starts with 'mqtt'
    topic_hierarchy = None
    for link in item.get('links', []):
        if link.get('rel') == 'items' and link.get('href').startswith('mqtt'):
            topic_hierarchy = link.get('channel')

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
        "creation_date": properties.get('created'),
        "topic_hierarchy": topic_hierarchy,
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
    parser.add_argument('--url', type=str, default=CANADA_GDC_API_URL,
                        help='URL of the GDC API')
    parser.add_argument('--country', type=str,
                        help='The country code to fetch data for')
    parser.add_argument('--query', type=str, help='Text search')
    args = parser.parse_args()

    # Get the bounding box for the country
    bbox_array = None
    if args.country:
        # Load country data
        countries_metadata = fetch_countries_metadata()

        if not countries_metadata:
            print("Error fetching country metadata")
            return

        # Get the bbox data for the specified country
        bbox_array = get_bbox_for_country(countries_metadata, args.country)

    api_response = fetch_data(url=args.url, bbox=bbox_array, query=args.query)
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
