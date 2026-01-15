"""API command - call arbitrary Slack API endpoint"""

import json
import sys
import asyncio
from ..auth import read_auth_file
from ..api import call_slack_api
from ..utils import substitute_users_in_json_async


def cmd_api(args):
    """Call an arbitrary Slack API endpoint

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - endpoint: API endpoint name (e.g., 'chat.postMessage')
            - method: HTTP method (GET or POST)
            - data: JSON data for POST requests
            - params: JSON params for GET requests
            - workspace: Use workspace domain instead of slack.com
    """
    creds = read_auth_file(args.auth_file)

    # Parse data if provided (for POST)
    data = None
    if args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON data: {e}")
            sys.exit(1)

    # Parse params if provided (for GET)
    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON params: {e}")
            sys.exit(1)

    # Determine method (POST if data provided, GET otherwise)
    method = args.method or ('POST' if data else 'GET')

    # Get workspace URL if --workspace flag is set
    workspace_url = None
    if getattr(args, 'workspace', False):
        # Get workspace URL from auth.test
        auth_result = call_slack_api('auth.test', creds['token'], creds['cookie'])
        if auth_result.get('ok'):
            workspace_url = auth_result.get('url', '').rstrip('/')

    # Make the API call
    # Note: use_form_data is not exposed via CLI, only used internally
    result = call_slack_api(
        args.endpoint,
        creds['token'],
        creds['cookie'],
        method=method,
        data=data,
        params=params,
        workspace_url=workspace_url,
        use_form_data=False
    )

    # Resolve user IDs to usernames
    result = asyncio.run(substitute_users_in_json_async(result, creds['token'], creds['cookie']))

    # Pretty print the result
    print(json.dumps(result, indent=2))
