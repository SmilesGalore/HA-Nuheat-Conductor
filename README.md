# Nuheat Conductor Thermostat Integration for Home Assistant

A custom Home Assistant integration for Nuheat Conductor radiant heating thermostats. Control and monitor your Nuheat heating systems directly from Home Assistant.

## Features

- 🌡️ **Climate Control** - Full thermostat control through Home Assistant's climate platform
- 🔐 **Secure OAuth2 Authentication** - Browser-based OAuth2 Authorization Code flow
- 📊 **Real-time Monitoring** - Current temperature and heating status
- 🎯 **Temperature Control** - Set target temperatures and heating modes
- 🔄 **Auto-discovery** - Automatically discovers all thermostats on your Nuheat account

## Prerequisites

- Home Assistant instance (core-2024.1.0 or later)
- Nuheat Conductor thermostat system
- Nuheat account credentials
- API access enabled by Nuheat (contact Nuheat support to enable the `openapi` scope)

## Installation

### HACS (Recommended)

_Coming soon - pending HACS submission_

### Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/nuheat_conductor` folder to your Home Assistant `config/custom_components/` directory
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
- No need to enter credentials directly in Home Assistant
- Tokens are securely stored and automatically refreshed
- Authorization happens in your web browser

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

- `heat` - Heating enabled
- `off` - Heating disabled

## API Endpoints

This integration connects to:
- **Identity Server:** `https://identity.nam.mynuheat.com`
- **API Server:** `https://api.nam.mynuheat.com`

## Troubleshooting

### Integration Not Appearing

1. Ensure files are in the correct directory: `config/custom_components/nuheat_conductor/`
2. Restart Home Assistant completely
3. Check Home Assistant logs for errors: **Settings** → **System** → **Logs**

### Authentication Failures

1. Verify you have the correct Nuheat credentials
2. Confirm Nuheat has enabled the `openapi` scope for your account
3. Check that you can log in to the Nuheat web portal at [mynuheat.com](https://www.mynuheat.com)
4. Try removing and re-adding the integration

### 500 Errors During Setup

- This typically indicates the `openapi` scope is not enabled for your account
- Contact Nuheat support to request API access

### No Thermostats Discovered

1. Verify your thermostats appear in the Nuheat mobile app or web portal
2. Check Home Assistant logs for API errors
3. Try reloading the integration: **Settings** → **Devices & Services** → **Nuheat Conductor** → **⋮** → **Reload**

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
- Type hints throughout
- Async/await patterns
- Comprehensive error handling
- Proper entity lifecycle management

## Support

- **Issues:** [GitHub Issues](https://github.com/SmilesGalore/HA-Nuheat-Conductor/issues)
- **Discussions:** [GitHub Discussions](https://github.com/SmilesGalore/HA-Nuheat-Conductor/discussions)
- **Home Assistant Community:** [Home Assistant Forums](https://community.home-assistant.io/)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Thanks to the Home Assistant community for their excellent documentation
- Nuheat for providing API access
- All contributors who help improve this integration

## License

This project is licensed under the Apache-2.0 License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or supported by Nuheat. Use at your own risk.

---

**Note:** This integration is currently in development. Features and functionality may change as development progresses.
