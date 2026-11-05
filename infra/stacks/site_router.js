// CloudFront Function (viewer request, cloudfront-js-2.0): route the static site.
// - App paths are served by index.html (views switched by path, no router library).
// - /c/<challengeId> is served by index.html too (the app reads the id from the path).
// - Files (a dot in the last segment) pass through to S3.
// - Anything else gets a real 404, so unknown pages are not indexed as the home page.
// /api/* never reaches this function (separate behaviour).

var APP_PATHS = { "/": true, "/play": true, "/result": true, "/practice": true, "/privacy": true };
var CHALLENGE = /^\/c\/[A-Z2-7]{12}\/?$/;

var NOT_FOUND =
  '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width,initial-scale=1">' +
  "<title>Page not found - Stay Sharp</title></head>" +
  '<body><main><h1>Page not found</h1><p><a href="/">Go to today\'s set</a></p></main></body></html>';

function handler(event) {
  var request = event.request;
  var uri = request.uri;
  var path = uri.length > 1 && uri.charAt(uri.length - 1) === "/" ? uri.slice(0, -1) : uri;

  if (APP_PATHS[path]) {
    request.uri = "/index.html";
    return request;
  }
  if (CHALLENGE.test(uri)) {
    request.uri = "/index.html";
    return request;
  }
  var last = uri.substring(uri.lastIndexOf("/") + 1);
  if (last.indexOf(".") > 0) {
    return request;
  }
  return {
    statusCode: 404,
    statusDescription: "Not Found",
    headers: {
      "content-type": { value: "text/html; charset=utf-8" },
      "cache-control": { value: "no-store" },
    },
    body: { encoding: "text", data: NOT_FOUND },
  };
}
