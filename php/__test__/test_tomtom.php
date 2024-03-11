<?php
//using tomtommaps API
//Source and Destination Coordinates

$TOMTOM_API_KEY = getenv('TOMTOM_API_KEY');
$TOMTOM_API_URL = "https://api.tomtom.com/routing/1/calculateRoute";

$TOLLGURU_API_KEY = getenv('TOLLGURU_API_KEY');
$TOLLGURU_API_URL = "https://apis.tollguru.com/toll/v2";
$POLYLINE_ENDPOINT = "complete-polyline-from-mapping-service";

// Explore https://tollguru.com/toll-api-docs to get the best of all the parameters that Tollguru has to offer
$request_parameters = array(
  "vehicle" => array(
      "type" => "2AxlesAuto"
  ),
  // Visit https://en.wikipedia.org/wiki/Unix_time to know the time format
  "departure_time" => "2021-01-05T09:46:08Z"
);

function getPoints($source_longitude,$source_latitude,$destination_longitude,$destination_latitude) {
  global $TOMTOM_API_KEY, $TOMTOM_API_URL;

  $url=$TOMTOM_API_URL.'/'.$source_latitude.','.$source_longitude.':'.$destination_latitude.','.$destination_longitude.'/json?avoid=unpavedRoads&key='.$TOMTOM_API_KEY.'';

  //connection..
  $tomtom = curl_init();

  curl_setopt($tomtom, CURLOPT_SSL_VERIFYHOST, false);
  curl_setopt($tomtom, CURLOPT_SSL_VERIFYPEER, false);

  curl_setopt($tomtom, CURLOPT_URL, $url);
  curl_setopt($tomtom, CURLOPT_RETURNTRANSFER, true);

  //getting response from googleapis..
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

  $new_leg_points = $data_tomtom['routes']['0']['legs']['0']['points'];

  return $new_leg_points;
}

require_once(__DIR__.'/test_location.php');
require_once(__DIR__.'/get_lat_long.php');
foreach ($locdata as $item) {
$source = getCord($item['from']);
$source_longitude = $source['y'];
$source_latitude = $source['x'];
$destination = getCord($item['to']);
$destination_longitude = $destination['y'];
$destination_latitude = $destination['x'];
$g_points  = getPoints($source_longitude,$source_latitude,$destination_longitude,$destination_latitude);
//polyline..
require_once(__DIR__.'/Polyline.php');
$polyline_tomtom = Polyline::encode($g_points);


//using tollguru API..
$curl = curl_init();

curl_setopt($curl, CURLOPT_SSL_VERIFYHOST, false);
curl_setopt($curl, CURLOPT_SSL_VERIFYPEER, false);

$postdata = array(
	"source" => "gmaps",
	"polyline" => $polyline_tomtom,
  ...$request_parameters,
);

//json encoding source and polyline to send as postfields..
$encode_postData = json_encode($postdata);

curl_setopt_array($curl, array(
  CURLOPT_URL => $TOLLGURU_API_URL . "/" . $POLYLINE_ENDPOINT,
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

//response from tollguru..
$data = json_decode($response, true);

$tag = $data['route']['costs']['tag'];
$cash = $data['route']['costs']['cash'];

$dumpFile = fopen("dump.txt", "a") or die("unable to open file!");
fwrite($dumpFile, "from =>");
fwrite($dumpFile, $item['from'].PHP_EOL);
fwrite($dumpFile, "to =>");
fwrite($dumpFile, $item['to'].PHP_EOL);
fwrite($dumpFile, "polyline =>".PHP_EOL);
fwrite($dumpFile, $polyline_tomtom.PHP_EOL);
fwrite($dumpFile, "tag =>");
fwrite($dumpFile, $tag.PHP_EOL);
fwrite($dumpFile, "cash =>");
fwrite($dumpFile, $cash.PHP_EOL);
fwrite($dumpFile, "*************************************************************************".PHP_EOL);

echo "tag = ";
print_r($data['route']['costs']['tag']);
echo "\ncash = ";
print_r($data['route']['costs']['cash']);
echo "\n";
echo "**************************************************************************\n";

}
?>
