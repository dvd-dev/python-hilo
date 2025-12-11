import base64
import hashlib
import json
import os
import re
import subprocess
from urllib.parse import urlencode, urlunparse, urlparse, parse_qs
import requests
import sys

CLIENT_ID = "1ca9f585-4a55-4085-8e30-9746a65fa561"
AUTH_HOST = "connexion.hiloenergie.com"
AUTH_PATH = "/HiloDirectoryB2C.onmicrosoft.com/B2C_1A_SIGN_IN/oauth2/v2.0/authorize"
TOKEN_PATH = "/HiloDirectoryB2C.onmicrosoft.com/B2C_1A_SIGN_IN/oauth2/v2.0/token"
SCOPE = "openid https://HiloDirectoryB2C.onmicrosoft.com/hiloapis/user_impersonation offline_access"
REDIRECT_URL = "https://my.home-assistant.io/redirect/oauth"
API_HOST = "api.hiloenergie.com"
DEVICEHUB_PATH = "/DeviceHub/negotiate"
CHALLENGEHUB_PATH = "/ChallengeHub/negotiate"


def create_url(base_url, path, params):
    query_string = urlencode(params)
    url = urlunparse(("https", base_url, path, "", query_string, ""))
    return url


def get_verifier_and_challenge():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
    code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
    code_challenge = code_challenge.replace('=', '')
    return code_verifier, code_challenge


def get_state():
    return hashlib.sha256(os.urandom(40)).hexdigest()


def build_auth_url(state, code_challenge):
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "redirect_uri": REDIRECT_URL,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return create_url(AUTH_HOST, AUTH_PATH, params)


def get_code(auth_url):
    print(f"Go there and authenticate:\n{auth_url}\n\n")
    input("After completing authentication, copy the redirected URL from your browser and press Enter...")

    try:
        # Read URL from clipboard
        redirect_w_token = subprocess.run(
            ['pbpaste'], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception as e:
        print("Failed to read clipboard:", e)
        redirect_w_token = input("Fallback: Paste the redirected URL here:\n")

    print("Captured URL:", redirect_w_token[:100], "...")  # show first 100 chars for sanity check

    parsed_redirect = urlparse(redirect_w_token)
    query = parse_qs(parsed_redirect.query)

    if 'code' not in query:
        raise ValueError("No 'code' parameter found in the URL. Make sure you copied the redirected URL.")

    return query['code'][0]


def exchange_code_for_token(code, code_verifier):
    url = create_url(AUTH_HOST, TOKEN_PATH, '')
    resp = requests.get(
        url=url,
        params={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URL,
            "code": code,
            "code_verifier": code_verifier,
        },
        allow_redirects=False
    )

    if resp.status_code != 200:
        print("Failed to exchange code for token:", resp.status_code, resp.text)
        sys.exit(1)

    return resp.json()


def exchange_rt_for_token(refresh_token):
    url = create_url(AUTH_HOST, TOKEN_PATH, '')
    resp = requests.get(
        url=url,
        params={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        },
        allow_redirects=False
    )

    if resp.status_code != 200:
        print("Failed to refresh token:", resp.status_code, resp.text)
        sys.exit(1)

    return resp.json()


def get_challengehub_ws(token):
    url = create_url(API_HOST, CHALLENGEHUB_PATH, '')
    resp = requests.post(url=url, headers={'Authorization': f"Bearer {token}"})
    print(resp.status_code)
    return resp.json()


def get_devicehub_ws(token):
    url = create_url(API_HOST, DEVICEHUB_PATH, '')
    resp = requests.post(url=url, headers={'Authorization': f"Bearer {token}"})
    print(resp.status_code)
    return resp.json()


if __name__ == "__main__":
    token = None

    if len(sys.argv) == 2:
        print("Using provided refresh token")
        token = exchange_rt_for_token(sys.argv[1])
    else:
        code_verifier, challenge = get_verifier_and_challenge()
        state = get_state()
        url = build_auth_url(state, challenge)
        code = get_code(url)
        token = exchange_code_for_token(code, code_verifier)

    if 'access_token' not in token:
        print("No access token received. Full response:")
        print(json.dumps(token, indent=True))
        sys.exit(1)

    print(f"Got Token:\n{json.dumps(token, indent=True)}")
    challengehub_ws_info = get_challengehub_ws(token['access_token'])
    print(f"ChallengeHub: {json.dumps(challengehub_ws_info, indent=True)}")
    devicehub_ws_info = get_devicehub_ws(token['access_token'])
    print(f"DeviceHub: {json.dumps(devicehub_ws_info, indent=True)}")
