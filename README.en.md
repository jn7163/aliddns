# Aliyun DDNS

A robust, modern Python CLI tool to dynamically update Aliyun DNS (Alidns) records to point to your current public IP address. Supports both IPv4 and IPv6 resolution.

## Features
- 🚀 Support for dynamic updating of both IPv4 (A) and IPv6 (AAAA) DNS records.
- 🔄 Multiple public IP query services bundled with smart fallback mechanisms to guarantee correct IP fetching.
- 🛡️ Comprehensive error handling and configurable local logging.
- 📦 Config file decoupled and Command Line Arguments driven structure. Standardized Python installation.

## Installation

It is recommended to use `uv` or `pipx` to install this tool natively into an isolated environment on your system.

Navigate to the project directory and invoke:
```bash
uv tool install .
# OR pipx install .
```
This generates an executable `aliddns-updater` accessible from anywhere on your system.

## Configuration & Usage

The application will try to automatically load the configuration from `~/.config/aliddns/config.json` if it exists:
```json
{
    "access_key_id": "YOUR_AK_ID",
    "access_secret": "YOUR_AK_SECRET",
    "domain": "example.com",
    "ipv4_prefix": "ipv4",
    "ipv6_prefix": "ipv6"
}
```

**Configuration Fields Explanation:**
- `access_key_id`: Your Aliyun AccessKey ID.
- `access_secret`: Your Aliyun AccessKey Secret.
- `domain`: Your main domain name (e.g., `example.com`).
- `ipv4_prefix`: Subdomain component for IPv4 (e.g., `@` for root, or `ipv4`).
- `ipv6_prefix`: Subdomain component for IPv6 (e.g., `ipv6`).

### Passing Command-Line Arguments
Hard-coded configurations are deprecated. You can specify or override parameters using CLI flags:
```bash
aliddns-updater --domain myapp.com --ipv4-prefix www --disable-ipv6
```
Run `aliddns-updater --help` to check all the options.

## Cron Automation

You can easily schedule the script execution every 10 minutes by editing crontab `crontab -e`:

```bash
*/10 * * * * ~/.local/bin/aliddns-updater >> /tmp/aliddns-updater.log 2>&1
```
*(Note: `~/.local/bin/` is the standard isolation path used by `uv tool install` and `pipx`. If you are running directly from source without installing, replace the command with `cd /absolute/path/to/project && uv run aliddns.py`. You can also use `which aliddns-updater` to find the exact installed path.)*
