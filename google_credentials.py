import os.path

import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

_google_credentials = {}
def get_google_credentials(token_id='dqb'):
    token_file = f"token/{token_id}_token.json"
    scopes = {
        'dqb': ['https://www.googleapis.com/auth/spreadsheets'],
        'betting_form': ['https://www.googleapis.com/auth/forms.body', 'https://www.googleapis.com/auth/drive.file'],
        'script': ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/docs'],
    }[token_id]
    try:
        credentials = _google_credentials.get(token_id)
        if not credentials and os.path.exists(token_file):
            credentials = Credentials.from_authorized_user_file(token_file, scopes)
        if not credentials or not credentials.valid:
            if credentials and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('token/credentials.json', scopes)
                credentials = flow.run_local_server(port=0)
            with open(token_file, 'w') as token:
                token.write(credentials.to_json())
        if credentials.scopes != scopes:
            os.remove(token_file)
            _google_credentials[token_id] = None
            return get_google_credentials(token_id)
        _google_credentials[token_id] = credentials
        return credentials
    except google.auth.exceptions.RefreshError:
        os.remove(token_file)
        _google_credentials[token_id] = None
        return get_google_credentials(token_id)
