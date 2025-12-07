"""Constants for Nuheat Conductor integration."""

DOMAIN = "nuheat_conductor"

# OAuth2 Configuration for Nuheat Conductor
AUTH_URL = "https://identity.nam.mynuheat.com"
API_URL = "https://api.nam.mynuheat.com"
TOKEN_URL = f"{AUTH_URL}/connect/token"
AUTHORIZE_URL = f"{AUTH_URL}/connect/authorize"

# OAuth2 Credentials
CLIENT_ID = "Home-Assistant-BGiUr56ktR--Nes"
CLIENT_SECRET = "SYhm-gb@3H!4mqZymMnDIGuWkj7Jp2bxQ4iE3nzTboIPAgfIP4XMTrm1@w0Cg4s4"

# OAuth2 Scopes
OAUTH2_SCOPES = ["openid", "openapi", "offline_access"]
