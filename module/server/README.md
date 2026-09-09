# System timezone API

[简体中文](README.zh.md)

| Item | Contract |
|---|---|
| Method and path | `GET /home/system_timezone` |
| Meaning | The host operating system timezone, not the scheduler process or browser timezone |
| Parameters | None |
| Success | HTTP `200`, `{"timezone":"Asia/Shanghai"}` |
| Identifier | IANA timezone identifier; Windows configuration is mapped using tzlocal's CLDR-derived mapping |
| Refresh | Fresh OS read for every request; `Cache-Control: no-store` on success and errors |
| Read error | HTTP `500`, code `SYSTEM_TIMEZONE_READ_FAILED` |
| Mapping error | HTTP `500`, code `SYSTEM_TIMEZONE_MAPPING_FAILED` |
| Unsupported platform | HTTP `501`, code `SYSTEM_TIMEZONE_UNSUPPORTED_PLATFORM` |
| Writes | No write endpoint; not persisted in account configuration |

Error bodies contain exactly `code` and `message`:

```json
{"code":"SYSTEM_TIMEZONE_READ_FAILED","message":"Unable to read system timezone."}
```

The other messages are `Unable to map system timezone to an IANA identifier.`
and `System timezone detection is not supported on this platform.` Clients
should branch on status and code, not message text. Internal exception details
are not returned. No timezone is guessed when detection fails.

Windows, Linux and macOS are supported by the detector. Every request runs a
short-lived Python probe with `TZ` removed from its environment. This avoids the
server's forced timezone and tzlocal's cache without changing the server's
process environment. Probes time out after five seconds. System configuration
must provide a timezone name; anonymous timezone files cannot always be mapped.
Windows-to-IANA mapping describes the configured zone, not the user's physical
location. OS custom timezone rules may not have an IANA equivalent.

Dependencies are pinned in the requirement files. Runtime requests do not access
the network. Install requirements before starting the updated backend.

Run regression tests with `python -m pytest tests/test_system_timezone.py -q`
(test-only dependencies: pytest and httpx). Tests cover HTTP responses, rejected
writes, repeated reads, TZ isolation and detector failures. The real-system test
checks only the OS on which the tests run; it does not modify the system timezone.
