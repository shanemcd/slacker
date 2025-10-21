#!/usr/bin/env python3
"""
Slacker
Extract Slack authentication credentials from browser session
"""

import json
import sys
import argparse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright not installed")
    print("Install with: uv sync && uv run playwright install chromium")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Error: httpx not installed")
    print("Install with: uv sync")
    sys.exit(1)


def read_auth_file(auth_file):
    """Read credentials from auth file"""
    auth_path = Path(auth_file)

    if not auth_path.exists():
        print(f"Error: Auth file not found: {auth_file}")
        print(f"\nRun 'slacker login <workspace-url>' first to extract credentials")
        sys.exit(1)

    content = auth_path.read_text()

    # Parse the shell script format
    token = None
    cookie = None

    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('export SLACK_TOKEN='):
            token = line.split('=', 1)[1].strip('"\'')
        elif line.startswith('export SLACK_COOKIE='):
            cookie = line.split('=', 1)[1].strip('"\'')

    if not token or not cookie:
        print(f"Error: Could not parse credentials from {auth_file}")
        sys.exit(1)

    return {'token': token, 'cookie': cookie}


def call_slack_api(endpoint, token, cookie, method='GET', data=None, params=None):
    """Make a Slack API call"""
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


def cmd_whoami(args):
    """Test authentication and show user info"""
    creds = read_auth_file(args.auth_file)

    print(f"Testing authentication from {args.auth_file}...\n")

    result = call_slack_api('auth.test', creds['token'], creds['cookie'])

    if result.get('ok'):
        print("✓ Authentication successful!\n")
        print(f"  User:      {result.get('user')}")
        print(f"  User ID:   {result.get('user_id')}")
        print(f"  Team:      {result.get('team')}")
        print(f"  Team ID:   {result.get('team_id')}")
        print(f"  URL:       {result.get('url')}")
    else:
        print(f"✗ Authentication failed: {result.get('error')}")
        print("\nYour credentials may have expired. Run 'slacker login' again.")
        sys.exit(1)


def extract_slack_credentials(workspace_url, headless=False):
    """
    Open Slack in a browser, wait for user to log in, then extract credentials.

    Args:
        workspace_url: Slack workspace URL (e.g., https://myworkspace.slack.com)
        headless: Run browser in headless mode (default: False for manual login)
    """

    print(f"Opening browser to {workspace_url}")
    print("Please log in to Slack in the browser window that opens...")
    print("Once you see your workspace, press Enter here to extract credentials.")

    with sync_playwright() as p:
        # Launch browser (visible so user can log in)
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to Slack
        page.goto(workspace_url)

        # Wait for user to log in
        if not headless:
            input("\nPress Enter after you've logged in and see your Slack workspace...")
        else:
            # In headless mode, wait for the page to load
            page.wait_for_load_state('networkidle')

        # Extract token from localStorage
        tokens = {}
        try:
            local_config = page.evaluate('localStorage.getItem("localConfig_v2")')
            if local_config:
                config = json.loads(local_config)
                teams = config.get('teams', {})

                for team_id, team_data in teams.items():
                    if 'token' in team_data:
                        team_name = team_data.get('name', team_id)
                        tokens[team_name] = {
                            'token': team_data['token'],
                            'team_id': team_id
                        }
        except Exception as e:
            print(f"Warning: Could not extract from localStorage: {e}")

        # Try alternative method via window.TS
        if not tokens:
            try:
                api_token = page.evaluate('window.TS?.boot_data?.api_token')
                team_id = page.evaluate('window.TS?.boot_data?.team_id')
                if api_token:
                    tokens['current'] = {
                        'token': api_token,
                        'team_id': team_id or 'unknown'
                    }
            except Exception as e:
                print(f"Warning: Could not extract from window.TS: {e}")

        # Extract cookies
        cookies = context.cookies()
        d_cookie = None
        for cookie in cookies:
            if cookie['name'] == 'd':
                d_cookie = cookie['value']
                break

        browser.close()

        # Check if we got everything
        if not tokens:
            print("Error: Could not extract token. Make sure you're logged in.")
            return None

        if not d_cookie:
            print("Error: Could not extract 'd' cookie. Make sure you're logged in.")
            return None

        # Prepare output
        credentials = {
            'cookie': d_cookie,
            'tokens': tokens
        }

        return credentials


def get_default_auth_file():
    """Get the default auth file path"""
    config_dir = Path.home() / '.config' / 'slacker'
    return str(config_dir / 'credentials')


def save_credentials(credentials, output_file):
    """Save credentials to a file"""

    # Ensure the parent directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create shell script format
    output = "# Slack Authentication Credentials\n"
    output += f"# Generated by slacker\n\n"
    output += f'export SLACK_COOKIE="{credentials["cookie"]}"\n\n'

    # Export first token (or let user choose if multiple)
    first_team = list(credentials['tokens'].keys())[0]
    first_token = credentials['tokens'][first_team]['token']

    output += f'# Team: {first_team}\n'
    output += f'export SLACK_TOKEN="{first_token}"\n\n'

    # If multiple teams, add comments with others
    if len(credentials['tokens']) > 1:
        output += "# Other teams:\n"
        for team_name, data in credentials['tokens'].items():
            if team_name != first_team:
                output += f'# export SLACK_TOKEN="{data["token"]}"  # {team_name}\n'
        output += "\n"

    # Write to file
    output_path.write_text(output)
    output_path.chmod(0o600)  # Make it readable only by owner

    return output


def cmd_api(args):
    """Call an arbitrary Slack API endpoint"""
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

    # Make the API call
    result = call_slack_api(args.endpoint, creds['token'], creds['cookie'], method=method, data=data, params=params)

    # Pretty print the result
    print(json.dumps(result, indent=2))


def cmd_discover(args):
    """Discover available Slack API methods by scraping documentation"""
    print("Discovering Slack API methods...")

    try:
        with httpx.Client() as client:
            response = client.get('https://api.slack.com/methods')
            response.raise_for_status()

            # Parse the HTML to find method links
            # Look for links that match /methods/<method-name> pattern
            import re
            methods = []

            # Find all method links in the format /methods/method.name
            pattern = r'href="(/methods/([a-z]+\.[a-zA-Z\.]+))"'
            matches = re.findall(pattern, response.text)

            for path, method_name in matches:
                if method_name not in methods and '.' in method_name:
                    methods.append(method_name)

            # Sort by category
            methods.sort()

            # Group by category (first part before the dot)
            categories = {}
            for method in methods:
                category = method.split('.')[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(method)

            # Display results
            print(f"\nFound {len(methods)} API methods:\n")

            if args.category:
                # Filter by category
                if args.category in categories:
                    print(f"Category: {args.category}")
                    for method in categories[args.category]:
                        print(f"  - {method}")
                else:
                    print(f"Category '{args.category}' not found.")
                    print(f"Available categories: {', '.join(sorted(categories.keys()))}")
            else:
                # Show all categories
                for category in sorted(categories.keys()):
                    print(f"{category} ({len(categories[category])} methods)")
                    if args.verbose:
                        for method in categories[category]:
                            print(f"  - {method}")

                if not args.verbose:
                    print(f"\nUse --verbose to see all methods, or --category <name> to filter by category")
                    print(f"Example: slacker discover --category chat")

    except httpx.HTTPError as e:
        print(f"Error fetching API documentation: {e}")
        sys.exit(1)


def cmd_login(args):
    """Extract credentials from browser"""

    # Validate URL
    workspace_url = args.workspace_url
    if not workspace_url.startswith('https://'):
        workspace_url = f'https://{workspace_url}'

    if '.slack.com' not in workspace_url:
        print("Error: URL must be a Slack workspace (*.slack.com)")
        sys.exit(1)

    # Extract credentials
    credentials = extract_slack_credentials(workspace_url, headless=args.headless)

    if not credentials:
        print("\nFailed to extract credentials.")
        sys.exit(1)

    # Print summary
    print("\n✓ Successfully extracted credentials!")
    print(f"  Teams found: {len(credentials['tokens'])}")
    for team_name in credentials['tokens'].keys():
        print(f"    - {team_name}")

    # Save
    save_credentials(credentials, args.auth_file)
    print(f"\n✓ Saved to: {args.auth_file}")
    print(f"\nTest with: slacker whoami")


def main():
    parser = argparse.ArgumentParser(
        prog='slacker',
        description='Extract and use Slack authentication credentials from browser session',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--auth-file',
        default=None,
        help=f'Auth file location (default: {get_default_auth_file()})'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    subparsers.required = True

    # Login command
    login_parser = subparsers.add_parser(
        'login',
        help='Extract credentials from browser',
        description='Open a browser to log in to Slack and extract credentials'
    )
    login_parser.add_argument(
        'workspace_url',
        help='Slack workspace URL (e.g., https://myworkspace.slack.com)'
    )
    login_parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (requires already logged in cookies)'
    )
    login_parser.set_defaults(func=cmd_login)

    # Whoami command
    whoami_parser = subparsers.add_parser(
        'whoami',
        help='Test authentication and show user info',
        description='Verify credentials and display authenticated user information'
    )
    whoami_parser.set_defaults(func=cmd_whoami)

    # API command
    api_parser = subparsers.add_parser(
        'api',
        help='Call an arbitrary Slack API endpoint',
        description='Make a call to any Slack API endpoint with optional data'
    )
    api_parser.add_argument(
        'endpoint',
        help='API endpoint to call (e.g., users.list, conversations.history)'
    )
    api_parser.add_argument(
        '--data', '-d',
        help='JSON data to send with the request (implies POST)'
    )
    api_parser.add_argument(
        '--params', '-p',
        help='JSON query parameters for GET requests (e.g., \'{"limit": 10}\')'
    )
    api_parser.add_argument(
        '--method', '-m',
        choices=['GET', 'POST'],
        help='HTTP method to use (default: POST if --data provided, GET otherwise)'
    )
    api_parser.set_defaults(func=cmd_api)

    # Discover command
    discover_parser = subparsers.add_parser(
        'discover',
        help='Discover available Slack API methods',
        description='Explore available Slack API methods by scraping the documentation'
    )
    discover_parser.add_argument(
        '--category', '-c',
        help='Filter by category (e.g., chat, users, conversations)'
    )
    discover_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show all methods in all categories'
    )
    discover_parser.set_defaults(func=cmd_discover)

    args = parser.parse_args()

    # Set default auth file if not specified
    if args.auth_file is None:
        args.auth_file = get_default_auth_file()

    args.func(args)


if __name__ == '__main__':
    main()
