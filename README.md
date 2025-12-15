# Nuheat Conductor Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A custom Home Assistant integration for Nuheat Conductor radiant heating thermostats using OAuth2 authentication.

## Features

- 🌡️ **Temperature Control**: Set target temperatures with temporary or permanent holds
- 📅 **Schedule Management**: Switch between scheduled operation and manual control
- 🔄 **Real-time Status**: Monitor current temperature, heating status, and online/offline state
- 🌍 **Multi-Unit Support**: Automatically detects Celsius or Fahrenheit from your Nuheat account preferences
- 🔐 **Secure OAuth2**: Uses official Nuheat OAuth2 authentication
- 📊 **Detailed Attributes**: View schedule mode (Schedule, Temporary Hold, Permanent Hold) and online status

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/SmilesGalore/HA-Nuheat-Conductor`
6. Select category: "Integration"
7. Click "Add"
8. Search for "Nuheat Conductor" in HACS
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/SmilesGalore/HA-Nuheat-Conductor/releases)
2. Copy the `custom_components/nuheat_conductor` folder to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Nuheat Conductor"
4. Click on it to start the OAuth2 flow
5. You'll be redirected to Nuheat's login page
6. Log in with your Nuheat account credentials
7. Authorize Home Assistant to access your thermostats
8. Your thermostats will be automatically discovered and added

## Usage

### Temperature Control

- Use the temperature up/down buttons to adjust the setpoint
- Changes create a **temporary hold** that lasts until the next scheduled change
- The integration automatically uses your preferred temperature unit (Celsius or Fahrenheit)

### HVAC Modes

- **Heat**: Manual temperature control with temporary hold
- **Auto**: Follow the programmed schedule
- **Off**: Displayed when thermostat is offline (cannot be manually set)

### Attributes

Each thermostat entity includes additional attributes:

- **Status**: Online or Offline
- **Schedule Mode**: Schedule, Temporary Hold, or Permanent Hold

## Troubleshooting

### Thermostats Show as Offline

**Problem**: Thermostats appear but show as "Off" with offline status.

**Solution**: 
- Check that your thermostats have power and WiFi connectivity
- Verify they appear as online in the Nuheat mobile app
- The integration cannot control offline thermostats - changes will be rejected by the API

### Temperature Changes Don't Apply

**Problem**: Temperature adjustments revert immediately.

**Solution**: This happens when thermostats are offline. The integration automatically reverts failed changes. Wait for thermostats to come back online.

### Wrong Temperature Unit

**Problem**: Temperatures display in wrong unit (Celsius vs Fahrenheit).

**Solution**: The integration uses your Nuheat account preference. Log into your Nuheat account and change the temperature scale setting, then reload the integration.

## Known Limitations

- Cannot control thermostats that are offline
- Temperature changes create temporary holds by default (permanent holds must be set via Nuheat app)
- Polling interval is 5 minutes (real-time updates not available from API)

## API Information

This integration uses the Nuheat Conductor API v1:
- **Auth**: https://identity.nam.mynuheat.com
- **API**: https://api.nam.mynuheat.com/api/v1

API documentation: https://api.nam.mynuheat.com/swagger/index.html

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/SmilesGalore/HA-Nuheat-Conductor/issues).

For Nuheat account or API access issues, contact Nuheat support directly.

## Credits

Developed by [@SmilesGalore](https://github.com/SmilesGalore)

## License

This project is licensed under the Apache License - see the [LICENSE](LICENSE) file for details.
