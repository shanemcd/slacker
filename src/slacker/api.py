"""Slack API client"""

import sys
import httpx


def call_slack_api(endpoint, token, cookie, method='GET', data=None, params=None):
    """Make a Slack API call

    Args:
        endpoint: API endpoint (e.g., 'auth.test', 'chat.postMessage')
        token: Slack API token
        cookie: Slack 'd' cookie value
        method: HTTP method ('GET' or 'POST')
        data: JSON data for POST requests
        params: Query parameters for GET requests

    Returns:
        dict: JSON response from Slack API

    Raises:
        SystemExit: If API call fails
    """
    url = f"https://slack.com/api/{endpoint}"

    headers = {
        'Authorization': f'Bearer {token}',
        'Cookie': f'd={cookie}',
    }

    if method == 'POST':
        headers['Content-Type'] = 'application/json'

    try:
        with httpx.Client() as client:
            if method == 'GET':
                response = client.get(url, headers=headers, params=params)
            else:
                response = client.post(url, headers=headers, json=data)

            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        print(f"Error making API call: {e}")
        sys.exit(1)
