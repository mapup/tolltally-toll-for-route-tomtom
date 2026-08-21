require 'uri'
require 'net/http'
require 'json'
require 'fast_polylines'
require 'cgi'

TOMTOM_API_KEY = ENV['TOMTOM_API_KEY']
TOMTOM_API_URL = "https://api.tomtom.com/routing/1/calculateRoute"
TOMTOM_GEOCODE_API_URL = "https://api.tomtom.com/search/2/geocode"

TOLLGURU_API_KEY = ENV['TOLLGURU_API_KEY']
TOLLGURU_API_URL = "https://apis.tollguru.com/toll/v2"
POLYLINE_ENDPOINT = "complete-polyline-from-mapping-service"

def get_coord_hash(loc)
  uri = URI("#{TOMTOM_GEOCODE_API_URL}/#{CGI::escape(loc)}.JSON?key=#{TOMTOM_API_KEY}&limit=1")
  response = Net::HTTP.get_response(uri)
  if response.is_a?(Net::HTTPSuccess)
    coord = JSON.parse(response.body)
    return (coord['results'].pop)['position']
  else
    puts "Error fetching coordinates: #{response.code} #{response.message}"
    return nil
  end
end

source_loc = "Philadelphia, PA"
destination_loc = "New York, NY"

request_parameters = {
  "vehicle" => {
    "type" => "2AxlesAuto",
  },
  "departure_time" => "2021-01-05T09:46:08Z",
}

# Step 1: Get Coordinates
source = get_coord_hash(source_loc)
destination = get_coord_hash(destination_loc)

if source.nil? || destination.nil?
  puts "Failed to get coordinates."
  exit
end

# Step 2: Get Route from TomTom
tomtom_url_string = "#{TOMTOM_API_URL}/#{source["lat"]},#{source["lon"]}:#{destination["lat"]},#{destination["lon"]}/json?avoid=unpavedRoads&key=#{TOMTOM_API_KEY}"
tomtom_uri = URI(tomtom_url_string)
response_tomtom = Net::HTTP.get_response(tomtom_uri)

if !response_tomtom.is_a?(Net::HTTPSuccess)
  puts "TomTom API Error: #{response_tomtom.code}"
  puts response_tomtom.body
  exit
end

json_parsed = JSON.parse(response_tomtom.body)
tomtom_coordinates = json_parsed['routes'].map { |x| x['legs'] }.pop.map{ |y| y['points']}.pop.map {|z| z.values}
google_encoded_polyline = FastPolylines.encode(tomtom_coordinates)

# Sending POST request to TollGuru
#
# This used to shell out to curl. Two problems with that: the API key sat in
# the command line, where any user on the box could read it out of `ps`, and
# the request body had to be spooled through a file in the working directory.
# Net::HTTP is already required and used for both TomTom calls above, so the
# key travels as a header and the body never touches disk.
tollguru_uri = URI("#{TOLLGURU_API_URL}/#{POLYLINE_ENDPOINT}")

body = {
  'source' => "tomtom",
  'polyline' => google_encoded_polyline
}.merge(request_parameters)

puts "Sending request to TollGuru..."
request = Net::HTTP::Post.new(tollguru_uri)
request['Content-Type'] = 'application/json'
request['x-api-key'] = TOLLGURU_API_KEY
request.body = body.to_json

response_tollguru = Net::HTTP.start(tollguru_uri.hostname, tollguru_uri.port,
                                    use_ssl: tollguru_uri.scheme == 'https') do |http|
  http.request(request)
end
response_body = response_tollguru.body

# curl -s swallowed HTTP errors and handed back a body that failed to parse,
# so surface the status the way the TomTom call above does.
unless response_tollguru.is_a?(Net::HTTPSuccess)
  puts "TollGuru API Error: #{response_tollguru.code} #{response_tollguru.message}"
end

begin
  tollguru_response = JSON.parse(response_body)
  if tollguru_response['route'] && tollguru_response['route']['costs']
    puts "The rates are \n #{tollguru_response['route']['costs']}"
  else
    puts "Response: #{response_body}"
  end
rescue JSON::ParserError => e
  puts "Failed to parse response: #{response_body}"
end