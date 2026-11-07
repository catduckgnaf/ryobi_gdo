# Changelog

## 0.9.10

- Add the Home Assistant integration category `blinds_curtains` to the manifest, which covers garage doors and gates, so the integration is categorised correctly in Home Assistant and the Marketplace catalog. No functional change.

## 0.9.9

### Fixes

- Surface disconnected sockets, failed writes and reconnection errors as Home Assistant service errors instead of silently returning success.
- Preserve the last observed door state after command transmission; a socket write is not physical movement confirmation.

### Testing improvements

- Add offline WebSocket regressions for local/cloud URLs, authentication and subscription payloads, command serialization, disconnected sends, send failures, close handling, handshake rejection, retry backoff and retry exhaustion, malformed frames and API key redaction.
- Run Python CI tests once with coverage instead of twice.
- Keep pytest temporary files in a dedicated runner subdirectory rather than replacing the entire runner temporary root.
- Add a regression test for the CI execution and temporary-directory contract.
- Correct the test documentation's obsolete 100% coverage claim.

### Scope

Offline tests exercise command error propagation and mocked transport behavior. They do not contact Home Assistant, the cloud service or physical openers, and do not verify live control or telemetry. Live production diagnosis and attended actuation are separate acceptance steps.
