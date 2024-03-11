<?php
function getCord($address){
$key = getenv('TOMTOM_API_KEY');

$url = 'https://api.tomtom.com/search/2/geocode/'.urlencode($address).'.json?key='.$key.'&limit=1';

$ch = curl_init();

curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);

curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);

$responseJson = curl_exec($ch);
curl_close($ch);

$response = json_decode($responseJson, true);

$location = array(
	'x' => $response['results']['0']['position']['lat'],
    'y' => $response['results']['0']['position']['lon']
);

return $location;
 }
?>