# 05 — Alerting (LINE Messaging API)

## ⚠️ LINE Notify is discontinued

The originally-planned channel, **LINE Notify**, was shut down by LINE Corporation in 2025. Use **LINE Messaging API** (a LINE Official Account + Bot) instead — this guide covers that path. If your Technology Stack Justification document still names LINE Notify, update it; this is a legitimate "external dependency changed mid-project" story worth documenting rather than hiding.

## 1. Create a LINE Official Account + enable Messaging API

1. Create a LINE Official Account at https://www.linebiz.com (or via the LINE app)
2. In https://manager.line.biz, open the account → Settings → **Messaging API** → Enable, creating/selecting a **Provider** when prompted
3. Jump to https://developers.line.biz/console/, find the Channel matching your Official Account, open the **Messaging API** tab, and **Issue** a long-lived Channel access token — save it
4. Response settings → disable Greeting message and Auto-response (so the bot doesn't talk back)
5. Add the bot as a friend on your phone (QR code shown on the same page) — required for Broadcast messages to reach you

## 2. Zabbix Webhook Media Type

**Alerts → Media types → Create media type**
- Type: **Webhook**
- Parameters: `token` (as *Secret text*) = the Channel access token; `message` = `{ALERT.SUBJECT}\n{ALERT.MESSAGE}`
- Script — calls the LINE **Broadcast** API (not a 1:1 push) so no per-user LINE User ID lookup/webhook receiver is needed, which matters because the Zabbix Server has no public HTTPS endpoint for LINE to call back to:

```javascript
try {
    var params = JSON.parse(value);
    var req = new HttpRequest();
    req.addHeader('Content-Type: application/json');
    req.addHeader('Authorization: Bearer ' + params.token);
    var payload = JSON.stringify({ messages: [{ type: 'text', text: params.message }] });
    var resp = req.post('https://api.line.me/v2/bot/message/broadcast', payload);
    var code = req.getStatus();
    if (code < 200 || code >= 300) { throw 'HTTP ' + code + ': ' + resp; }
    return 'OK';
} catch (error) {
    Zabbix.log(4, '[LINE Webhook] ' + error);
    throw 'LINE notification failed: ' + error;
}
```

- Message templates: set Subject/Message for both **Problem** and **Problem recovery** event types so you get notified both when something breaks and when it clears.

## 3. User + Media

- **Users → User groups**: create `Alert Recipients` with Host permission = **All host groups**, Read
- **Users → Users**: create a user in that group, add Media = `LINE Messaging API` (the "Send to" field can be anything, e.g. `-` — Broadcast ignores it), set severity filter to Warning+

## 4. Trigger Action — designed to scale automatically

**Alerts → Actions → Trigger actions → Create action**
- Conditions: **Trigger severity >= Warning** only. **Deliberately do not add a Host group condition.**
- Operations: Send to user group `Alert Recipients`, media `LINE Messaging API`. Add an escalation step (e.g. repeat after 30 min if unresolved). Add a Recovery operation too.

The reason for leaving out any Host group condition: any host added later — by Auto-Discovery on any cloud, or added manually — automatically qualifies for alerting without touching this Action again. This was deliberately designed before adding the second cloud (GCP) specifically so expanding to more environments wouldn't require re-visiting the alerting config.

## 5. Daily cost digest (separate from Trigger-based alerting)

If you also want a scheduled daily summary of that day's AWS+GCP cost (regardless of whether anything crossed a threshold), that's `daily_cost_digest.py` from `04-cost-visibility-layer.md` — it calls the LINE Broadcast API directly and runs independently of the Zabbix Trigger/Action mechanism above (a cron job, not a monitoring alert).

## Known issues & fixes

| Symptom | Cause | Fix |
|---|---|---|
| Messaging API option not available when creating a Channel from LINE Developers Console directly | Current LINE flow requires creating the Official Account first via manager.line.biz, *then* enabling Messaging API from there | Follow §1 above in that order |
| Webhook test succeeds but live triggers never arrive | Bot not added as a friend yet (Broadcast only reaches friends) | Scan the QR code and add the bot |
