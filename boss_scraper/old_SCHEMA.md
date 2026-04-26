# SCHEMA.md — Structured Output Envelope

All `--json` and `--yaml` output from boss-cli uses a unified envelope:

## Success

```json
{
  "ok": true,
  "schema_version": "1",
  "data": { ... }
}
```

## Error

```json
{
  "ok": false,
  "schema_version": "1",
  "data": null,
  "error": {
    "code": "not_authenticated",
    "message": "环境异常 (__zp_stoken__ 已过期)。请重新登录: boss logout && boss login"
  }
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `not_authenticated` | Session expired or not logged in |
| `rate_limited` | Too many requests |
| `invalid_params` | Missing or invalid parameters |
| `api_error` | Upstream API error |
| `unknown_error` | Unexpected error |

## Notes

- When stdout is not a TTY (e.g., piped or invoked by AI agent), output defaults to YAML.
- Use `--json` or `--yaml` to explicitly select format.
- Install `pyyaml` for YAML support: `pip install boss-cli[yaml]`
- If `pyyaml` is not installed, `--yaml` falls back to JSON.
