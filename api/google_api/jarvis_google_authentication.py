import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these scopes, delete the file token.json.
# Read-only access to the calendar:
# SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
# Full access to the calendar:
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
GOOGLE_API_DIR = os.path.join(PROJECT_ROOT, "api", "google_api")

def get_authentications_for_user(username, allow_logging_popup=False):
    authentications = {}
    
    if not os.path.isdir(os.path.join(GOOGLE_API_DIR, username)):
        raise FileNotFoundError(f"No existe el directorio para el usuario '{username}'. Ruta comprobada: {os.path.join(GOOGLE_API_DIR, username)}")
    for account in os.listdir(os.path.join(GOOGLE_API_DIR, username)):
        for filename in os.listdir(os.path.join(GOOGLE_API_DIR, username, account)):
            if filename.endswith(".json") and not "example" in filename:
                filepath = os.path.join(GOOGLE_API_DIR, username, account, filename)
                if "credential" in filename:
                    credential_path = filepath
                elif "token" in filename:
                    token_path = filepath
                    authentication = Credentials.from_authorized_user_file(filepath, SCOPES)
                else:
                    print(f"Unknown file type: {filepath}")
        if not authentication or not authentication.valid:
            if authentication and authentication.expired and authentication.refresh_token:
                try:
                    authentication.refresh(Request())
                except Exception as e:
                    print(f"Exception: {e}")
                    if allow_logging_popup:
                        flow = InstalledAppFlow.from_client_secrets_file(credential_path, SCOPES)
                        authentication = flow.run_local_server(port=0)
                    else:
                        print(f"Unable to authenticate {account}. Logging pop-up not allowed. Please run the authentication flow.")
                        return None
            else:
                if allow_logging_popup:
                    flow = InstalledAppFlow.from_client_secrets_file(credential_path, SCOPES)
                    authentication = flow.run_local_server(port=0)
                else:
                    print(f"Unable to authenticate {account}. Logging pop-up not allowed. Please run the authentication flow.")
                    return None
            with open(token_path, 'w') as token_file:
                token_file.write(authentication.to_json())
        authentications[account] = authentication

    return authentications
