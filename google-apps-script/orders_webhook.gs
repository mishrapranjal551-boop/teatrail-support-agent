/**
 * TeaTrail Orders web hook: Tara sends each new order here, and it is added
 * as a row to the first tab of this Google Sheet.
 *
 * Set up (once):
 * 1. Open the "TeaTrail Orders" sheet → Extensions → Apps Script.
 * 2. Paste this whole file, and replace PASTE-YOUR-SECRET-HERE with the value of
 *    ORDERS_WEBHOOK_SECRET from .streamlit/secrets.toml.
 * 3. Deploy → New deployment → type "Web app", Execute as "Me",
 *    Who has access "Anyone" → Deploy → allow access → copy the Web app URL.
 * 4. Put that URL in Secrets as ORDERS_WEBHOOK_URL.
 *
 * Only requests that carry the right secret can add rows.
 */
const SECRET = "PASTE-YOUR-SECRET-HERE";
const HEADERS = ["order_id", "time", "customer_name", "phone", "address", "items",
                 "subtotal", "delivery_fee", "total", "payment", "status"];

function doPost(e) {
  let data;
  try {
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    return reply_({ ok: false, error: "bad request" });
  }
  if (!data || data.secret !== SECRET) {
    return reply_({ ok: false, error: "unauthorized" });
  }
  const order = data.order || {};
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  sheet.appendRow(HEADERS.map(function (h) { return safeCell_(h, order[h]); }));
  return reply_({ ok: true });
}

// Keeps text as text: stops a customer's "=..." from running as a formula,
// and keeps phone numbers as text. Money columns stay numbers so you can add them up.
function safeCell_(header, value) {
  if (value === undefined || value === null) return "";
  if (["subtotal", "delivery_fee", "total"].indexOf(header) >= 0 && typeof value === "number") {
    return value;
  }
  const text = String(value).slice(0, 1000);
  return (header === "phone" || /^[=+\-@]/.test(text)) ? "'" + text : text;
}

function reply_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
