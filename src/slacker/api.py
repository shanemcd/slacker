"""Slack API client"""

import sys
import httpx


def call_slack_api(endpoint, token, cookie, method='GET', data=None, params=None,
                   workspace_url=None, use_form_data=False):
    """Make a Slack API call

    Args:
        endpoint: API endpoint (e.g., 'auth.test', 'chat.postMessage')
        token: Slack API token
        cookie: Slack 'd' cookie value
        method: HTTP method ('GET' or 'POST')
        data: JSON data for POST requests (or form data if use_form_data=True)
        params: Query parameters for GET requests
        workspace_url: Optional workspace URL (e.g., 'https://myworkspace.slack.com')
                      If provided, use this instead of slack.com for enterprise endpoints
        use_form_data: If True, send POST data as form-encoded instead of JSON

    Returns:
        dict: JSON response from Slack API

    Raises:
        SystemExit: If API call fails
    """
    # Determine base URL
    if workspace_url:
        # Remove trailing slash if present
        base_url = workspace_url.rstrip('/')
    else:
        base_url = "https://slack.com"

    url = f"{base_url}/api/{endpoint}"

    headers = {
        'Authorization': f'Bearer {token}',
        'Cookie': f'd={cookie}',
    }

    try:
        with httpx.Client() as client:
            if method == 'GET':
                response = client.get(url, headers=headers, params=params)
            else:
                # POST request
                if use_form_data:
                    # Send as form data (application/x-www-form-urlencoded)
                    # Include token in form data for enterprise endpoints
                    form_data = {'token': token}
                    if data:
                        form_data.update(data)
                    response = client.post(url, headers=headers, data=form_data)
                else:
                    # Send as JSON (default)
                    headers['Content-Type'] = 'application/json'
                    response = client.post(url, headers=headers, json=data)

            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        print(f"Error making API call: {e}")
        sys.exit(1)


async def call_slack_api_async(endpoint, token, cookie, client, method='GET', data=None, params=None,
                                workspace_url=None, use_form_data=False):
    """Make an async Slack API call

    Args:
        endpoint: API endpoint (e.g., 'auth.test', 'chat.postMessage')
        token: Slack API token
        cookie: Slack 'd' cookie value
        client: httpx.AsyncClient instance
        method: HTTP method ('GET' or 'POST')
        data: JSON data for POST requests (or form data if use_form_data=True)
        params: Query parameters for GET requests
        workspace_url: Optional workspace URL (e.g., 'https://myworkspace.slack.com')
                      If provided, use this instead of slack.com for enterprise endpoints
        use_form_data: If True, send POST data as form-encoded instead of JSON

    Returns:
        dict: JSON response from Slack API, or None if error
    """
    # Determine base URL
    if workspace_url:
        base_url = workspace_url.rstrip('/')
    else:
        base_url = "https://slack.com"

    url = f"{base_url}/api/{endpoint}"

    headers = {
        'Authorization': f'Bearer {token}',
        'Cookie': f'd={cookie}',
    }

    try:
        if method == 'GET':
            response = await client.get(url, headers=headers, params=params)
        else:
            # POST request
            if use_form_data:
                form_data = {'token': token}
                if data:
                    form_data.update(data)
                response = await client.post(url, headers=headers, data=form_data)
            else:
                headers['Content-Type'] = 'application/json'
                response = await client.post(url, headers=headers, json=data)

        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None
