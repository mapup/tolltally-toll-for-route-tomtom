# [](https://developer.tomtom.com/)

### Get API key to access TomTom APIs (if you have an API key skip this)
#### Step 1: Login/Singup
* Create an account to access [TomTom Developer Portal](https://developer.tomtom.com/)
* go to signup/login link https://developer.tomtom.com/user/login
* you will need to agree to TomTom's Terms of Service https://developer.tomtom.com/terms-and-conditions

#### Step 2: Getting you Key
* Login to your TomTom Developer Portal
* You can find you key at https://developer.tomtom.com/user/me/apps
* If you want you can create additional keys as per different
  applications

With this in place, make a GET request: https://api.tomtom.com/routing/1/calculateRoute/${source.latitude},${source.longitude}:${destination.latitude},${destination.longitude}/json?avoid=unpavedRoads&key=${key}

### Note:
* TomTom accepts source and destination, as `:` seperated `${longitude,latitude}`.
* TomTom doesn't return us route as a polyline, but as a list of `{ latitude, longitude }`, we need to convert this to a polyline

```php

//extracting polyline from the JSON response..
$data_tomtom = json_decode($response, true);
$new_leg_points=$data_tomtom['routes']['0']['legs']['0']['points'];

//polyline..
require_once(__DIR__.'/Polyline.php');
$polyline_tomtom = Polyline::encode($new_leg_points);


```

```php

//using tomtommaps API

//Source and Destination Coordinates
//Dallas, TX
$source_longitude='-96.7970';
$source_latitude='32.7767';
//Addison, Texas
$destination_longitude='-96.83256117564599';
$destination_latitude='32.967452488953626';

//tomtom api key..
$key = 'tomtomAPIkey';

$url='https://api.tomtom.com/routing/1/calculateRoute/'.$source_latitude.','.$source_longitude.':'.$destination_latitude.','.$destination_longitude.'/json?avoid=unpavedRoads&key='.$key.'';

//connection..
$tomtom = curl_init();

curl_setopt($tomtom, CURLOPT_SSL_VERIFYHOST, 2);
curl_setopt($tomtom, CURLOPT_SSL_VERIFYPEER, true);

curl_setopt($tomtom, CURLOPT_URL, $url);
curl_setopt($tomtom, CURLOPT_RETURNTRANSFER, true);

//getting response from tomtomapis..
$response = curl_exec($tomtom);
$err = curl_error($tomtom);

curl_close($tomtom);

if ($err) {
	  echo "cURL Error #:" . $err;
} else {
	  echo "200 : OK\n";
}
//extracting polyline from the JSON response..
$data_tomtom = json_decode($response, true);
$new_leg_points=$data_tomtom['routes']['0']['legs']['0']['points'];

//polyline..
require_once(__DIR__.'/Polyline.php');
$polyline_tomtom = Polyline::encode($new_leg_points);


```

Note:
* Code to get the `polyline` can be found at https://github.com/emcconville/google-map-polyline-encoding-tool
* We extracted the polyline for a route from TomTom Maps API

* We need to send this route polyline to TollGuru API to receive toll information

## [TollGuru API](https://tollguru.com/developers/docs/)

### Get key to access TollGuru polyline API
* create a dev account to receive a free key from TollGuru https://tollguru.com/developers/get-api-key
* suggest adding `vehicleType` parameter. Tolls for cars are different than trucks and therefore if `vehicleType` is not specified, may not receive accurate tolls. For example, tolls are generally higher for trucks than cars. If `vehicleType` is not specified, by default tolls are returned for 2-axle cars. 
* Similarly, `departure_time` is important for locations where tolls change based on time-of-the-day which can be passed through `$postdata`.

the last line can be changed to following

```php

//using tollguru API..
$curl = curl_init();

curl_setopt($curl, CURLOPT_SSL_VERIFYHOST, 2);
curl_setopt($curl, CURLOPT_SSL_VERIFYPEER, true);

$postdata = array(
	"source" => "gmaps",
	"polyline" => $polyline_tomtom
);

//json encoding source and polyline to send as postfields..
$encode_postData = json_encode($postdata);

curl_setopt_array($curl, array(
CURLOPT_URL => "https://dev.tollguru.com/v1/calc/route",
CURLOPT_RETURNTRANSFER => true,
CURLOPT_ENCODING => "",
CURLOPT_MAXREDIRS => 10,
CURLOPT_TIMEOUT => 30,
CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
CURLOPT_CUSTOMREQUEST => "POST",

// sending tomtom polyline to tollguru
CURLOPT_POSTFIELDS => $encode_postData,
CURLOPT_HTTPHEADER => array(
				      "content-type: application/json",
				      "x-api-key: tollguru_api_key"),
));

$response = curl_exec($curl);
$err = curl_error($curl);
curl_close($curl);

if ($err) {
	  echo "cURL Error #:" . $err;
} else {
	  echo "200 : OK\n";
}

//response from tollguru..
$data = var_dump(json_decode($response, true));
print_r($data);


```

The working code can be found in `php_curl_tomtom.php` file.

## License
ISC License (ISC). Copyright 2020 &copy;TollGuru. https://tollguru.com/

Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
