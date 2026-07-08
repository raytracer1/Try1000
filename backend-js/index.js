const { handleRequest, ensure } = require("./src/app");

module.exports.handler = async (event, context, callback) => {
  await ensure();

  let ev = event;
  if (Buffer.isBuffer(event)) {
    ev = JSON.parse(event.toString("utf-8"));
  } else if (event instanceof Uint8Array) {
    ev = JSON.parse(Buffer.from(event).toString("utf-8"));
  } else if (typeof event === "string") {
    ev = JSON.parse(event);
  }

  const http = ev.requestContext?.http || {};
  const body = ev.isBase64Encoded
    ? Buffer.from(ev.body || "", "base64").toString("utf-8")
    : (ev.body || "");

  const req = {
    url: ev.rawPath || http.path || "/",
    method: http.method || "GET",
    headers: ev.headers || {},
    body,
  };

  const result = { status: 200, headers: {}, body: "" };

  const res = {
    setHeader(k, v) { result.headers[k] = v; },
    send(data) { result.body = typeof data === "string" ? data : JSON.stringify(data); },
    end(data) { if (data) this.send(data); },
    writeHead(code, hdrs) { result.status = code; if (hdrs) Object.assign(result.headers, hdrs); },
  };

  await handleRequest(req, res);

  const headers = { ...result.headers, "Content-Type": "application/json; charset=utf-8" };
  // Ensure Set-Cookie is a string (not array), FC doesn't support multi-value headers
  if (Array.isArray(headers["Set-Cookie"])) {
    headers["Set-Cookie"] = headers["Set-Cookie"].join("; ");
  }

  const resp = { statusCode: result.status, headers, body: result.body || "{}", isBase64Encoded: false };
  callback(null, resp);
  return resp;
};
