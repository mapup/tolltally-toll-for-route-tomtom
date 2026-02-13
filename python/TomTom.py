# Importing modules
import json
import requests
import os
import polyline as poly


TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY")
TOMTOM_API_URL = "https://api.tomtom.com/routing/1/calculateRoute"
TOMTOM_GEOCODE_API_URL = "https://api.tomtom.com/search/2/geocode"

TOLLGURU_API_KEY = os.environ.get("TOLLGURU_API_KEY")
TOLLGURU_API_URL = "https://apis.tollguru.com/toll/v2"
POLYLINE_ENDPOINT = "complete-polyline-from-mapping-service"

# From and To locations
source = "Philadelphia, PA"
destination = "New York, NY"

# Explore https://tollguru.com/toll-api-docs to get best of all the parameter that TollGuru has to offer
request_parameters = {
    "vehicle": {
        "type": "2AxlesAuto"
    },
    # Visit https://en.wikipedia.org/wiki/Unix_time to know the time format
    "departure_time": "2021-01-05T09:46:08Z",
}

# Fetching the geocodes from Tomtom
def get_geocode_from_tomtom(address):
    encoded_address = address.replace(" ", "%20")
    url = f"{TOMTOM_GEOCODE_API_URL}/{address}.json?key={TOMTOM_API_KEY}&limit=1"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        latitude, longitude = data["results"][0]["position"].values()
        return (latitude, longitude)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching geocode from TomTom: {e}")
        return None
    except KeyError as e:
        print(f"Error parsing response from TomTom: {e}")
        return None

# Extracting Polyline from TOMTOM
def get_polyline_from_tomtom(
    source_latitude, source_longitude, destination_latitude, destination_longitude
):
    # Query Tomtom with Key and Source-Destination coordinates
    url = "{a}/{b},{c}:{d},{e}/json?avoid=unpavedRoads&key={f}".format(
        a=TOMTOM_API_URL,
        b=source_latitude,
        c=source_longitude,
        d=destination_latitude,
        e=destination_longitude,
        f=TOMTOM_API_KEY,
    )
    # converting the response to json
    response_from_tomtom = requests.get(url).json()
    # Tomtom does not provide polylines directly , it rather embeds Latitude and Longitude of each node in the route as dictionary key-value pair inside a list
    # We thus are extracting the list of such dictionary
    coordinates_dict_list = response_from_tomtom["routes"][0]["legs"][0]["points"]
    # We now must convert this list of dictionary to simple tuple or list iterables for "polyline.encode" to work
    coordinates_list = [(i["latitude"], i["longitude"]) for i in coordinates_dict_list]
    # generating polyline from list of lat-lon pairs
    polyline_from_tomtom = poly.encode(coordinates_list)
    return polyline_from_tomtom

# Calling Tollguru API
def get_rates_from_tollguru(polyline):
    # Tollguru querry url
    Tolls_URL = f"{TOLLGURU_API_URL}/{POLYLINE_ENDPOINT}"
    # Tollguru resquest parameters
    headers = {"Content-type": "application/json", "x-api-key": TOLLGURU_API_KEY}
    params = {
        # Explore https://tollguru.com/developers/docs/ to get best of all the parameter that tollguru has to offer
        "source": "tomtom",
        "polyline": polyline,  # this is the encoded polyline that we made
        **request_parameters,
    }
    # Requesting Tollguru with parameters
    response_tollguru = requests.post(Tolls_URL, json=params, headers=headers).json()
    # checking for errors or printing rates
    if str(response_tollguru).find("message") == -1:
        return response_tollguru["route"]["costs"]
    else:
        raise Exception(response_tollguru["message"])

"""Program Starts"""
# Step 1 :Getting Geocodes from Arcgis for Source and Destination
source_latitude, source_longitude = get_geocode_from_tomtom(source)
destination_latitude, destination_longitude = get_geocode_from_tomtom(destination)

# Step 2 : Get Polyline from Arcgis
polyline_from_tomtom = get_polyline_from_tomtom(
    source_latitude, source_longitude, destination_latitude, destination_longitude
)

# Step 3 : Get rates from Tollguru
rates_from_tollguru = get_rates_from_tollguru(polyline_from_tomtom)

# Print the rates of all the available modes of payment
if rates_from_tollguru == {}:
    print("The route doesn't have tolls")
else:
    print(f"The rates are \n {rates_from_tollguru}")

"""Program Ends"""
