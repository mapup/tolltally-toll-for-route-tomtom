require 'HTTParty'
require 'json'
require 'fast_polylines'
require 'cgi'

TOMTOM_API_KEY = "***REMOVED***"
TOMTOM_API_URL = "https://api.tomtom.com/routing/1/calculateRoute"
TOMTOM_GEOCODE_API_URL = "https://api.tomtom.com/search/2/geocode"

TOLLGURU_API_KEY = "***REMOVED***"
TOLLGURU_API_URL = "https://apis.tollguru.com/toll/v2"
POLYLINE_ENDPOINT = "complete-polyline-from-mapping-service"

source = get_coord_array("Philadelphia, PA")
destination = get_coord_array("New York, NY")

# Explore https://tollguru.com/toll-api-docs to get the best of all the parameters that tollguru has to offer
request_parameters = {
  "vehicle": {
    "type": "2AxlesAuto",
  },
  # Visit https://en.wikipedia.org/wiki/Unix_time to know the time format
  "departure_time": "2021-01-05T09:46:08Z",
}

def get_coord_hash(loc)
    geocoding_url = "#{TOMTOM_GEOCODE_API_URL}/#{CGI::escape(loc)}.JSON?key=#{TOMTOM_API_KEY}&limit=1"
    coord = JSON.parse(HTTParty.get(geocoding_url).body)
    return (coord['results'].pop)['position']
end

# Source Details in latitude-longitude pair using geocoding API
SOURCE = get_coord_hash(source)

# Destination Details in latitude-longitude pair using geocoding API
DESTINATION = get_coord_hash(destination)

# GET Request to TomTom for Route Coordinates
TOMTOM_URL = "#{TOMTOM_API_URL}/#{SOURCE["lat"]},#{SOURCE["lon"]}:#{DESTINATION["lat"]},#{DESTINATION["lon"]}/json?avoid=unpavedRoads&key=#{TOMTOM_API_KEY}"
RESPONSE = HTTParty.get(TOMTOM_URL).body
json_parsed = JSON.parse(RESPONSE)

# Extracting lat-long pairs from JSON and converting to polyline
tomtom_coordinates = json_parsed['routes'].map { |x| x['legs'] }.pop.map{ |y| y['points']}.pop.map {|z| z.values}
google_encoded_polyline = FastPolylines.encode(tomtom_coordinates)

# Sending POST request to TollGuru
tollguru_url = "#{TOLLGURU_API_URL}/#{POLYLINE_ENDPOINT}" 
headers = {'content-type' => 'application/json', 'x-api-key' => TOLLGURU_API_KEY}
body = {
  'source': "tomtom",
  'polyline': google_encoded_polyline,
  **request_parameters,
}
tollguru_response = HTTParty.post(tollguru_url,:body => body.to_json, :headers => headers)
puts tollguru_response