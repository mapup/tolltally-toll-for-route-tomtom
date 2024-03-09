const request = require("request");
const polyline = require("polyline");

// REST API key from tomtom
const TOMTOM_API_KEY = process.env.TOMTOM_API_KEY;

// API Key from TollGuru
const TOLLGURU_API_KEY = process.env.TOLLGURU_API_KEY;
const TOLLGURU_API_URL = "https://apis.tollguru.com/toll/v2";
const POLYLINE_ENDPOINT = "complete-polyline-from-mapping-service";

// Philadelphia, PA
const source = {
  longitude: "-75.1652",
  latitude: "39.9526",
};

// New York, NY
const destination = {
  longitude: "-74.0060",
  latitude: "40.7128",
};

// Explore https://tollguru.com/toll-api-docs to get best of all the parameter that TollGuru has to offer
request_parameters = {
  vehicle: {
    type: "2AxlesAuto",
  },
  // Visit https://en.wikipedia.org/wiki/Unix_time to know the time format
  departure_time: "2021-01-05T09:46:08Z",
};

const url = `https://api.tomtom.com/routing/1/calculateRoute/${source.latitude},${source.longitude}:${destination.latitude},${destination.longitude}/json?avoid=unpavedRoads&key=${TOMTOM_API_KEY}`;

const head = (arr) => arr[0];
const flatten = (arr, x) => arr.concat(x);

// JSON path "$..points"
const getPoints = (body) =>
  body.routes
    .map((route) => route.legs)
    .reduce(flatten)
    .map((leg) => leg.points)
    .reduce(flatten)
    .map(({ latitude, longitude }) => [latitude, longitude]);

const getPolyline = (body) => polyline.encode(getPoints(JSON.parse(body)));

const getRoute = (cb) => request.get(url, cb);

const tollguruUrl = `${TOLLGURU_API_URL}/${POLYLINE_ENDPOINT}`;

const handleRoute = (e, r, body) => {
  const _polyline = getPolyline(body);
  console.log(_polyline);

  const requestBody = {
    source: "tomtom",
    polyline: _polyline,
    ...request_parameters,
  };

  request.post(
    {
      url: tollguruUrl,
      headers: {
        "content-type": "application/json",
        "x-api-key": TOLLGURU_API_KEY,
      },
      body: JSON.stringify(requestBody),
    },
    (e, r, body) => {
      console.log(e);
      console.log(body);
    }
  );
};

getRoute(handleRoute);
