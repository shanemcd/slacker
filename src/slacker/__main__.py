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


def cmd_reminder(args):
    """Create a Slack reminder"""
    creds = read_auth_file(args.auth_file)

    # Build the blocks structure - pass the text directly to Slack's parser
    data = {
        "command": "/remind",
        "disp": "/remind",
        "blocks": [{
            "type": "rich_text",
            "elements": [{
                "type": "rich_text_section",
                "elements": [{
                    "type": "text",
                    "text": args.text
                }]
            }]
        }],
        "channel": args.channel or "D19Q000SE"  # Default to notes channel
    }

    # Make the API call
    result = call_slack_api('chat.command', creds['token'], creds['cookie'], method='POST', data=data)

    if result.get('ok'):
        print(f"✓ Reminder created: {args.text}")
    else:
        print(f"✗ Failed to create reminder: {result.get('error')}")
        sys.exit(1)


def get_channel_name(channel_id, token, cookie):
    """Get channel name from channel ID"""
    try:
        result = call_slack_api('conversations.info', token, cookie, method='GET', params={'channel': channel_id})
        if result.get('ok'):
            channel = result.get('channel', {})
            # For DMs, use the user's name if available
            if channel.get('is_im'):
                user_id = channel.get('user')
                if user_id:
                    user_result = call_slack_api('users.info', token, cookie, method='GET', params={'user': user_id})
                    if user_result.get('ok'):
                        user = user_result.get('user', {})
                        return f"@{user.get('name', channel_id)}"
            return channel.get('name', channel_id)
    except:
        pass
    return channel_id


def get_message_content(channel_id, timestamp, token, cookie):
    """Get message content from channel and timestamp"""
    try:
        result = call_slack_api('conversations.history', token, cookie, method='GET',
                               params={'channel': channel_id, 'latest': timestamp,
                                      'inclusive': True, 'limit': 1})
        if result.get('ok') and result.get('messages'):
            message = result['messages'][0]
            # Extract text from message
            text = message.get('text', '')

            # If message has blocks, try to extract rich text
            if not text and message.get('blocks'):
                for block in message['blocks']:
                    if block.get('type') == 'rich_text':
                        for element in block.get('elements', []):
                            if element.get('type') == 'rich_text_section':
                                for elem in element.get('elements', []):
                                    if elem.get('type') == 'text':
                                        text += elem.get('text', '')

            return text
    except:
        pass
    return None


def cmd_reminders_list(args):
    """List saved reminders and later items"""
    creds = read_auth_file(args.auth_file)

    # Call saved.list API
    data = {
        "filter": "saved",
        "limit": args.limit,
        "include_tombstones": True
    }

    result = call_slack_api('saved.list', creds['token'], creds['cookie'], method='POST', data=data)

    if not result.get('ok'):
        print(f"✗ Failed to list reminders: {result.get('error')}")
        sys.exit(1)

    saved_items = result.get('saved_items', [])

    # Filter to reminders only if requested
    if args.reminders_only:
        saved_items = [item for item in saved_items if item.get('item_type') == 'reminder']

    if not saved_items:
        print("No saved items found.")
        return

    # Display results
    print(f"Found {len(saved_items)} saved items:\n")

    # Get workspace URL for building links
    auth_result = call_slack_api('auth.test', creds['token'], creds['cookie'])
    workspace_url = auth_result.get('url', 'https://slack.com') if auth_result.get('ok') else 'https://slack.com'

    for item in saved_items:
        item_type = item.get('item_type', 'unknown')
        state = item.get('state', 'unknown')

        if item_type == 'reminder':
            # Extract description text
            desc_blocks = item.get('description', [])
            text = "Unknown"
            if desc_blocks:
                try:
                    text = desc_blocks[0]['elements'][0]['elements'][0]['text']
                except (KeyError, IndexError):
                    pass

            # Format due date
            import datetime
            due_ts = item.get('date_due', 0)
            due_date = datetime.datetime.fromtimestamp(due_ts).strftime('%Y-%m-%d %H:%M')

            print(f"[{state}] Reminder: {text}")
            print(f"  Due: {due_date}")
            print()
        else:
            # Saved message
            channel_id = item.get('item_id', 'unknown')
            ts = item.get('ts', 'unknown')

            # Get channel name
            channel_name = get_channel_name(channel_id, creds['token'], creds['cookie'])

            # Get message content
            message_text = get_message_content(channel_id, ts, creds['token'], creds['cookie'])

            # Format timestamp
            import datetime
            try:
                msg_ts = float(ts)
                msg_date = datetime.datetime.fromtimestamp(msg_ts).strftime('%Y-%m-%d %H:%M')
            except:
                msg_date = ts

            # Build message link
            ts_link = ts.replace('.', '')
            message_link = f"{workspace_url}archives/{channel_id}/p{ts_link}"

            print(f"[{state}] Saved message in #{channel_name}")
            print(f"  Date: {msg_date}")
            if message_text:
                # Truncate message if too long
                preview = message_text[:100] + '...' if len(message_text) > 100 else message_text
                # Replace newlines with spaces for preview
                preview = preview.replace('\n', ' ')
                print(f"  Preview: {preview}")
            print(f"  Link: {message_link}")
            print()

    # Show counts
    counts = result.get('counts', {})
    print(f"Summary:")
    print(f"  Total: {counts.get('total_count', 0)}")
    print(f"  Uncompleted: {counts.get('uncompleted_count', 0)}")
    print(f"  Overdue: {counts.get('uncompleted_overdue_count', 0)}")
    print(f"  Completed: {counts.get('completed_count', 0)}")


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

    # Reminder command
    reminder_parser = subparsers.add_parser(
        'reminder',
        help='Create a Slack reminder',
        description='Create a reminder using Slack\'s /remind command with natural language parsing'
    )
    reminder_parser.add_argument(
        'text',
        help='Reminder text - Slack will parse it naturally (e.g., "me to call mom tomorrow", "me to review PR in 30 minutes")'
    )
    reminder_parser.add_argument(
        '--channel', '-c',
        help='Channel to send reminder to (default: your notes channel)'
    )
    reminder_parser.set_defaults(func=cmd_reminder)

    # Reminders list command
    reminders_parser = subparsers.add_parser(
        'reminders',
        help='List saved reminders and later items',
        description='List all saved reminders and messages from Slack Later'
    )
    reminders_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=50,
        help='Maximum number of items to list (default: 50)'
    )
    reminders_parser.add_argument(
        '--reminders-only', '-r',
        action='store_true',
        help='Show only reminders (exclude saved messages)'
    )
    reminders_parser.set_defaults(func=cmd_reminders_list)

    args = parser.parse_args()

    # Set default auth file if not specified
    if args.auth_file is None:
        args.auth_file = get_default_auth_file()

    args.func(args)


if __name__ == '__main__':
    main()
