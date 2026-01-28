# Nuheat Conductor Thermostat Integration for Home Assistant

A custom Home Assistant integration for Nuheat Conductor radiant heating thermostats. Control and monitor your Nuheat heating systems directly from Home Assistant.

## Features

* 🌡️ **Climate Control** - Full thermostat control through Home Assistant's climate platform
* 🔐 **Secure OAuth2 Authentication** - Browser-based OAuth2 Authorization Code flow
* 📊 **Real-time Monitoring** - Current temperature and heating status
* 🎯 **Temperature Control** - Set target temperatures and heating modes
* 🔄 **Auto-discovery** - Automatically discovers all thermostats on your Nuheat account

## Prerequisites

* Home Assistant instance (core-2024.1.0 or later)
* Nuheat Conductor thermostat system
* Nuheat account credentials

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu (top right) → **Custom repositories**
3. Add repository URL: `https://github.com/SmilesGalore/HA-Nuheat-Conductor`
4. Select category: **Integration**
5. Click **Add**
6. Find "Nuheat Conductor" in HACS and click **Download**
7. Restart Home Assistant

### Manual Installation

1. Download or clone this repository
2. Copy the `nuheat_conductor` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

Your directory structure should look like:

```
config/
├── custom_components/
│   └── nuheat_conductor/
│       ├── __init__.py
│       ├── climate.py
│       ├── config_flow.py
│       ├── const.py
│       ├── manifest.json
│       └── strings.json
```

## Configuration

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Nuheat Conductor"
4. Click on the integration to begin setup
5. You'll be redirected to Nuheat's login page in your browser
6. Enter your Nuheat credentials and authorize Home Assistant
7. You'll be redirected back to Home Assistant with the integration configured

### OAuth2 Setup

This integration uses OAuth2 Authorization Code flow for secure authentication:

* No need to enter credentials directly in Home Assistant
* Tokens are securely stored and automatically refreshed
* Authorization happens in your web browser

**Important:** For the best experience during OAuth setup:
* Use the same device and browser throughout the entire setup process
* If using the Home Assistant mobile app, note that OAuth will open in your device's browser
* Complete the entire flow without switching devices or browsers

## Usage

Once configured, your Nuheat thermostats will appear as climate entities in Home Assistant.

### Basic Operations

**View in Lovelace:**

```yaml
type: thermostat
entity: climate.nuheat_living_room
```

**Set Temperature:**

```yaml
service: climate.set_temperature
target:
  entity_id: climate.nuheat_living_room
data:
  temperature: 72
```

**Set HVAC Mode:**

```yaml
service: climate.set_hvac_mode
target:
  entity_id: climate.nuheat_living_room
data:
  hvac_mode: heat
```

### Available HVAC Modes

* `heat` - Heating enabled
* `off` - Heating disabled

## API Endpoints

This integration connects to:

* **Identity Server:** `https://identity.nam.mynuheat.com`
* **API Server:** `https://api.nam.mynuheat.com`

## Troubleshooting

### OAuth Authentication Issues

#### "Already in progress" Error After Failed Setup

**Symptoms:**
* Setup fails during OAuth redirect
* When you try to add the integration again, you see "Configuration flow is already in progress"
* Cannot delete or restart the setup flow

**Cause:**
This typically happens when:
1. You start setup on one device (e.g., Home Assistant mobile app) but the OAuth redirect happens in a different context (browser)
2. The OAuth flow times out or is interrupted during authentication
3. The redirect back to Home Assistant fails due to session mismatch

**Solution:**
1. **Restart Home Assistant** - This is required to clear the stuck flow state
   * Go to **Settings** → **System** → **Restart**
   * Or use the restart command from your installation method
2. After restart, try adding the integration again
3. **Important:** Use the same device and browser throughout:
   * If starting from the web interface, complete everything in that browser
   * If starting from the mobile app, be aware that OAuth will open in your device's browser
   * Don't switch between devices during the setup process

**Prevention:**
* Always use the Home Assistant web interface (not mobile app) for initial setup if possible
* Keep the browser window open and don't close tabs during OAuth flow
* Ensure stable internet connection during setup
* Complete the entire flow in one sitting without interruptions

#### OAuth Redirect Fails

**Symptoms:**
* Browser redirects to Nuheat but doesn't return to Home Assistant
* Gets stuck on "Redirecting..." or similar message
* Error messages about invalid redirect URI

**Solution:**
1. Verify your Home Assistant is accessible via the external URL configured in Settings
2. Check that your Home Assistant external URL is configured correctly:
   * Go to **Settings** → **System** → **Network**
   * Verify **External URL** is set correctly
3. If using Nabu Casa Cloud, ensure your subscription is active
4. Try using the local network URL instead of external URL during setup
5. Restart Home Assistant and try again

### Integration Not Appearing

**Solution:**
1. Ensure files are in the correct directory: `config/custom_components/nuheat_conductor/`
2. Verify all required files are present (see directory structure above)
3. Restart Home Assistant completely
4. Check Home Assistant logs for errors: **Settings** → **System** → **Logs**
5. Search logs for "nuheat" to see any specific errors

### Authentication Failures

**Solution:**
1. Verify you have the correct Nuheat credentials
2. Confirm you can log in to the Nuheat web portal at [mynuheat.com](https://www.mynuheat.com)
3. Check that Nuheat has enabled the `openapi` scope for your account
4. Try removing and re-adding the integration:
   * Go to **Settings** → **Devices & Services**
   * Find **Nuheat Conductor**
   * Click the three dots → **Delete**
   * Restart Home Assistant
   * Add the integration again

### 500 Errors During Setup

**Cause:** This typically indicates the `openapi` scope is not enabled for your account

**Solution:**
* Contact Nuheat support to request API access
* Provide them with your account email address
* Request that they enable the `openapi` OAuth2 scope

### No Thermostats Discovered

**Solution:**
1. Verify your thermostats appear in the Nuheat mobile app or web portal
2. Check that thermostats are online and communicating
3. Review Home Assistant logs for API errors:
   * Go to **Settings** → **System** → **Logs**
   * Search for "nuheat"
4. Try reloading the integration:
   * Go to **Settings** → **Devices & Services**
   * Find **Nuheat Conductor**
   * Click **⋮** → **Reload**
5. If thermostats are offline (e.g., during renovation), they will still appear in Home Assistant but show as "unavailable"

### Logs and Debugging

To enable detailed logging for troubleshooting, add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.nuheat_conductor: debug
```

Then restart Home Assistant and check logs at **Settings** → **System** → **Logs**.

## Development

### Local Development Setup

1. Clone the Home Assistant development environment:

```bash
git clone https://github.com/home-assistant/core.git
cd core
```

2. Set up the development environment following [Home Assistant's developer documentation](https://developers.home-assistant.io/docs/development_environment)
3. Copy the integration files to `config/custom_components/nuheat_conductor/`
4. Start Home Assistant in development mode

### Running Tests

```bash
pytest tests/components/nuheat_conductor/
```

### Code Quality

This integration follows Home Assistant's coding standards:

* Type hints throughout
* Async/await patterns
* Comprehensive error handling
* Proper entity lifecycle management

## Support

* **Issues:** [GitHub Issues](https://github.com/SmilesGalore/HA-Nuheat-Conductor/issues)
* **Discussions:** [GitHub Discussions](https://github.com/SmilesGalore/HA-Nuheat-Conductor/discussions)
* **Home Assistant Community:** [Home Assistant Forums](https://community.home-assistant.io/)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

* Thanks to the Home Assistant community for their excellent documentation
* Nuheat for providing API access
* All contributors who help improve this integration

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or supported by Nuheat. Use at your own risk.

---

**Current Version:** 1.0.0
