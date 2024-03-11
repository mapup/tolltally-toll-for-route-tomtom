<?php
//using tomtommaps API

$TOMTOM_API_KEY = getenv('TOMTOM_API_KEY');
$TOMTOM_API_URL = "https://api.tomtom.com/routing/1/calculateRoute";

$TOLLGURU_API_KEY = getenv('TOLLGURU_API_KEY');
$TOLLGURU_API_URL = "https://apis.tollguru.com/toll/v2";
$POLYLINE_ENDPOINT = "complete-polyline-from-mapping-service";

// Philadelphia, PA
$source_longitude = "-75.1652";
$source_latitude = "39.9526";

// New York, NY
$destination_longitude = "-74.0060";
$destination_latitude = "40.7128";

// Explore https://tollguru.com/toll-api-docs to get the best of all the parameters that Tollguru has to offer
$request_parameters = array(
  "vehicle" => array(
      "type" => "2AxlesAuto"
  ),
  // Visit https://en.wikipedia.org/wiki/Unix_time to know the time format
  "departure_time" => "2021-01-05T09:46:08Z"
);

$url=$TOMTOM_API_URL.'/'.$source_latitude.','.$source_longitude.':'.$destination_latitude.','.$destination_longitude.'/json?avoid=unpavedRoads&key='.$TOMTOM_API_KEY.'';

// Connection
$tomtom = curl_init();

curl_setopt($tomtom, CURLOPT_SSL_VERIFYHOST, false);
curl_setopt($tomtom, CURLOPT_SSL_VERIFYPEER, false);

curl_setopt($tomtom, CURLOPT_URL, $url);
curl_setopt($tomtom, CURLOPT_RETURNTRANSFER, true);

// Getting response from tomtom API
$response = curl_exec($tomtom);
$err = curl_error($tomtom);

curl_close($tomtom);

if ($err) {
	  echo "cURL Error #:" . $err;
} else {
	  echo "200 : OK\n";
}
// Extracting polyline from the JSON response..
$data_tomtom = json_decode($response, true);
$new_leg_points=$data_tomtom['routes']['0']['legs']['0']['points'];

// Polyline
require_once(__DIR__.'/Polyline.php');
$polyline_tomtom = Polyline::encode($new_leg_points);

// Using TollGuru API
$curl = curl_init();

curl_setopt($curl, CURLOPT_SSL_VERIFYHOST, false);
curl_setopt($curl, CURLOPT_SSL_VERIFYPEER, false);

$postdata = array(
	"source" => "gmaps",
	"polyline" => $polyline_tomtom,
  ...$request_parameters,
);

//json encoding source and polyline to send as postfields
$encode_postData = json_encode($postdata);

curl_setopt_array($curl, array(
  CURLOPT_URL => $TOLLGURU_API_URL . "/" . $POLYLINE_ENDPOINT,
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_ENCODING => "",
  CURLOPT_MAXREDIRS => 10,
  CURLOPT_TIMEOUT => 30,
  CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
  CURLOPT_CUSTOMREQUEST => "POST",

  // Sending tomtom polyline to TollGuru
  CURLOPT_POSTFIELDS => $encode_postData,
  CURLOPT_HTTPHEADER => array(
    "content-type: application/json",
    "x-api-key: " . $TOLLGURU_API_KEY),
));

$response = curl_exec($curl);
$err = curl_error($curl);
curl_close($curl);

if ($err) {
	  echo "cURL Error #:" . $err;
} else {
	  echo "200 : OK\n";
}

// Response from TollGuru
$data = var_dump(json_decode($response, true));
print_r($data);
?>
