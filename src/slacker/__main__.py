#!/usr/bin/env python3
"""
Slacker
Extract Slack authentication credentials from browser session
"""

import json
import sys
import argparse
from pathlib import Path
from abc import ABC, abstractmethod

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


# Output Formatters using Strategy Pattern
class OutputFormatter(ABC):
    """Abstract base class for output formatters"""

    @abstractmethod
    def format_auth_test(self, result, auth_file=None):
        """Format authentication test results"""
        pass

    @abstractmethod
    def format_reminders(self, items, counts):
        """Format reminders/saved items list"""
        pass

    @abstractmethod
    def format_discover(self, methods, categories, total, category_filter=None, verbose=False):
        """Format API methods discovery results"""
        pass

    @abstractmethod
    def format_error(self, message):
        """Format error message"""
        pass


class TextFormatter(OutputFormatter):
    """Human-readable text output formatter"""

    def format_auth_test(self, result, auth_file=None):
        if auth_file:
            print(f"Testing authentication from {auth_file}...\n")

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

    def format_reminders(self, items, counts):
        if not items:
            print("No saved items found.")
            return

        print(f"Found {len(items)} saved items:\n")

        for item_data in items:
            if item_data['type'] == 'reminder':
                print(f"[{item_data['state']}] Reminder: {item_data['text']}")
                print(f"  Due: {item_data['due_date']}")
                print()
            else:
                print(f"[{item_data['state']}] Saved message in #{item_data['channel_name']}")
                print(f"  Date: {item_data['date']}")
                if item_data['message']:
                    print(f"  Message: {item_data['message']}")
                print(f"  Link: {item_data['link']}")
                print()

        print(f"Summary:")
        print(f"  Total: {counts.get('total_count', 0)}")
        print(f"  Uncompleted: {counts.get('uncompleted_count', 0)}")
        print(f"  Overdue: {counts.get('uncompleted_overdue_count', 0)}")
        print(f"  Completed: {counts.get('completed_count', 0)}")

    def format_discover(self, methods, categories, total, category_filter=None, verbose=False):
        print(f"\nFound {total} API methods:\n")

        if category_filter:
            if category_filter in categories:
                print(f"Category: {category_filter}")
                for method in categories[category_filter]:
                    print(f"  - {method}")
            else:
                print(f"Category '{category_filter}' not found.")
                print(f"Available categories: {', '.join(sorted(categories.keys()))}")
        else:
            for category in sorted(categories.keys()):
                print(f"{category} ({len(categories[category])} methods)")
                if verbose:
                    for method in categories[category]:
                        print(f"  - {method}")

    def format_error(self, message):
        print(f"✗ {message}")


class JSONFormatter(OutputFormatter):
    """JSON output formatter"""

    def format_auth_test(self, result, auth_file=None):
        print(json.dumps(result, indent=2))

    def format_reminders(self, items, counts):
        output = {
            'items': items,
            'counts': counts
        }
        print(json.dumps(output, indent=2))

    def format_discover(self, methods, categories, total, category_filter=None, verbose=False):
        if category_filter:
            if category_filter in categories:
                output = {
                    'category': category_filter,
                    'methods': categories[category_filter]
                }
            else:
                output = {
                    'error': f"Category '{category_filter}' not found",
                    'available_categories': sorted(categories.keys())
                }
        else:
            output = {
                'total_methods': total,
                'categories': categories
            }
        print(json.dumps(output, indent=2))

    def format_error(self, message):
        print(json.dumps({'error': message}, indent=2))


def get_formatter(output_format):
    """Factory function to get the appropriate formatter"""
    formatters = {
        'text': TextFormatter,
        'json': JSONFormatter,
    }

    formatter_class = formatters.get(output_format)
    if not formatter_class:
        raise ValueError(f"Unknown output format: {output_format}")

    return formatter_class()


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
    formatter = get_formatter(args.output)

    result = call_slack_api('auth.test', creds['token'], creds['cookie'])

    formatter.format_auth_test(result, auth_file=args.auth_file)

    if not result.get('ok'):
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
    formatter = get_formatter(args.output)

    # Call saved.list API
    data = {
        "filter": "saved",
        "limit": args.limit,
        "include_tombstones": True
    }

    result = call_slack_api('saved.list', creds['token'], creds['cookie'], method='POST', data=data)

    if not result.get('ok'):
        formatter.format_error(f"Failed to list reminders: {result.get('error')}")
        sys.exit(1)

    saved_items = result.get('saved_items', [])

    # Filter to reminders only if requested
    if args.reminders_only:
        saved_items = [item for item in saved_items if item.get('item_type') == 'reminder']

    # Get workspace URL for building links
    auth_result = call_slack_api('auth.test', creds['token'], creds['cookie'])
    workspace_url = auth_result.get('url', 'https://slack.com') if auth_result.get('ok') else 'https://slack.com'

    # Build structured output
    import datetime
    output_items = []

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
            due_ts = item.get('date_due', 0)
            due_date = datetime.datetime.fromtimestamp(due_ts).strftime('%Y-%m-%d %H:%M')

            output_items.append({
                'type': 'reminder',
                'state': state,
                'text': text,
                'due_date': due_date,
                'due_timestamp': due_ts
            })
        else:
            # Saved message
            channel_id = item.get('item_id', 'unknown')
            ts = item.get('ts', 'unknown')

            # Get channel name
            channel_name = get_channel_name(channel_id, creds['token'], creds['cookie'])

            # Get message content
            message_text = get_message_content(channel_id, ts, creds['token'], creds['cookie'])

            # Format timestamp
            try:
                msg_ts = float(ts)
                msg_date = datetime.datetime.fromtimestamp(msg_ts).strftime('%Y-%m-%d %H:%M')
            except:
                msg_date = ts
                msg_ts = None

            # Build message link
            ts_link = ts.replace('.', '')
            message_link = f"{workspace_url}archives/{channel_id}/p{ts_link}"

            output_items.append({
                'type': 'message',
                'state': state,
                'channel_id': channel_id,
                'channel_name': channel_name,
                'message': message_text,
                'date': msg_date,
                'timestamp': msg_ts,
                'link': message_link
            })

    # Format and output results
    formatter.format_reminders(output_items, result.get('counts', {}))


def cmd_discover(args):
    """Discover available Slack API methods by scraping documentation"""
    formatter = get_formatter(args.output)

    if args.output == 'text':
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

            # Format and output results
            formatter.format_discover(methods, categories, len(methods),
                                     category_filter=args.category, verbose=args.verbose)

            # Show additional help text for text output
            if args.output == 'text' and not args.category and not args.verbose:
                print(f"\nUse --verbose to see all methods, or --category <name> to filter by category")
                print(f"Example: slacker discover --category chat")

    except httpx.HTTPError as e:
        formatter.format_error(f"Error fetching API documentation: {e}")
        sys.exit(1)


def cmd_record(args):
    """Record network traffic while interacting with Slack"""
    import datetime
    from pathlib import Path
    import warnings
    import logging
    import asyncio

    # Suppress Playwright async warnings during shutdown
    logging.getLogger('playwright').setLevel(logging.ERROR)
    warnings.filterwarnings('ignore', category=RuntimeWarning, module='playwright')

    # Suppress asyncio TargetClosedError exceptions during shutdown
    def handle_exception(loop, context):
        exception = context.get('exception')
        if exception and 'Target page, context or browser has been closed' in str(exception):
            return  # Silently ignore these errors
        # Print other exceptions normally
        if exception:
            print(f"Async error: {exception}")

    # Set the exception handler for the running event loop (Playwright uses one internally)
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)
    except:
        pass

    # Get scenario name from args or prompt
    scenario = args.scenario
    if not scenario:
        # Only prompt if we have an interactive terminal
        if sys.stdin.isatty():
            scenario = input("Enter scenario name (e.g., 'create-reminder', 'save-message'): ").strip()
        else:
            print("Error: --scenario is required when running in non-interactive mode")
            print("Example: slacker record https://workspace.slack.com --scenario save-message")
            sys.exit(1)

    if not scenario:
        print("Error: Scenario name cannot be empty")
        sys.exit(1)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f"{scenario}_{timestamp}.json"

    # Auto-detect if we're in a non-interactive environment
    import sys
    is_interactive = sys.stdin.isatty()
    wait_for_close = args.wait_for_close or not is_interactive

    print(f"\nRecording network traffic for scenario: {scenario}")
    print(f"Output will be saved to: {output_file}")
    print(f"\nOpening browser to {args.workspace_url}...")

    if wait_for_close:
        print("Complete your task in the browser, then close the browser window to stop recording.\n")
    else:
        print("Complete your task in the browser, then press Enter here to stop recording.\n")

    # Storage for captured requests
    captured_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Set up request/response interceptor
        def handle_request(request):
            # Get post_data safely (may be binary/compressed)
            post_data = None
            try:
                post_data = request.post_data
            except UnicodeDecodeError:
                # Binary data (e.g., gzip compressed), skip it
                post_data = "<binary data>"
            except:
                pass

            request_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': post_data,
            }
            captured_requests.append({'type': 'request', 'data': request_data})

        def handle_response(response):
            response_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'url': response.url,
                'status': response.status,
                'headers': dict(response.headers),
            }

            # Try to capture response body if not disabled
            if not args.no_bodies:
                try:
                    # Only capture certain content types to avoid binary data
                    content_type = response.headers.get('content-type', '')
                    if any(t in content_type for t in ['json', 'text', 'javascript', 'xml']):
                        try:
                            response_data['body'] = response.text()
                        except:
                            # Silently skip body if we can't fetch it (e.g., browser closing)
                            pass
                except:
                    # Silently skip if there are any errors
                    pass

            captured_requests.append({'type': 'response', 'data': response_data})

        # Attach listeners
        page.on('request', handle_request)
        page.on('response', handle_response)

        # Navigate to Slack
        page.goto(args.workspace_url)

        # Wait for user to complete the task
        if wait_for_close:
            import time
            print("Waiting for browser to close...")
            print("(You can also press Ctrl+C to stop recording)")
            try:
                # Poll by trying to execute JavaScript - will fail when browser closes
                while True:
                    try:
                        page.evaluate('1')  # Simple check - will throw when browser closes
                        time.sleep(0.5)  # Check twice per second
                    except Exception as e:
                        # Only break on errors that indicate browser is closed
                        error_msg = str(e).lower()
                        if any(msg in error_msg for msg in ['target closed', 'browser has been closed', 'browser closed', 'connection closed']):
                            break
                        # Otherwise, it's likely a navigation error, continue polling
                print("Browser closed, finalizing recording...")
            except KeyboardInterrupt:
                print("\n\nRecording stopped by user (Ctrl+C)")
        else:
            input("Press Enter when you're done with the scenario...")

        # Remove event handlers to prevent errors during shutdown
        try:
            page.remove_listener('request', handle_request)
            page.remove_listener('response', handle_response)
        except:
            pass

        # Graceful shutdown: close page first, then context, then browser
        # Suppress stderr temporarily to hide asyncio "Future exception was never retrieved" messages
        import sys
        import os
        old_stderr = sys.stderr
        devnull = open(os.devnull, 'w')
        try:
            # Redirect stderr to devnull during shutdown to suppress async errors
            sys.stderr = devnull

            try:
                page.close()
            except:
                pass

            try:
                context.close()
            except:
                pass

            try:
                browser.close()
            except:
                pass
        finally:
            # Restore stderr
            sys.stderr = old_stderr
            devnull.close()

    # Filter requests if requested
    if args.filter:
        print(f"\nFiltering requests matching: {args.filter}")

        # Show sample URLs before filtering to help debug
        if captured_requests and len(captured_requests) > 0:
            print("\nSample URLs captured:")
            unique_domains = set()
            for req in captured_requests[:20]:  # Show first 20
                from urllib.parse import urlparse
                parsed = urlparse(req['data']['url'])
                unique_domains.add(parsed.netloc)

            for domain in sorted(unique_domains)[:10]:  # Show first 10 unique domains
                print(f"  - {domain}")

        filtered_requests = [
            req for req in captured_requests
            if args.filter.lower() in req['data']['url'].lower()
        ]
        print(f"\nFiltered {len(captured_requests)} requests down to {len(filtered_requests)}")

        if len(filtered_requests) == 0 and len(captured_requests) > 0:
            print(f"  Hint: No URLs matched '{args.filter}'. Try running without --filter")
            print(f"        and use --summary to see which domains are being used.")

        captured_requests = filtered_requests

    # Save to file
    output_data = {
        'scenario': scenario,
        'timestamp': timestamp,
        'workspace_url': args.workspace_url,
        'total_requests': len(captured_requests),
        'requests': captured_requests
    }

    output_file.write_text(json.dumps(output_data, indent=2))

    print(f"\n✓ Recorded {len(captured_requests)} requests")
    print(f"✓ Saved to: {output_file}")

    # Show summary
    if args.summary:
        print("\nSummary of captured URLs:")
        urls = {}
        domains = {}
        for item in captured_requests:
            if item['type'] == 'request':
                url = item['data']['url']
                # Extract path and domain from URL
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path
                domain = parsed.netloc

                urls[path] = urls.get(path, 0) + 1
                domains[domain] = domains.get(domain, 0) + 1

        print("\nTop domains:")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {count:3d}x {domain}")

        print("\nTop paths:")
        for path, count in sorted(urls.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"  {count:3d}x {path}")


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
    parser.add_argument(
        '--output', '-o',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    subparsers.required = True

    # Record command
    record_parser = subparsers.add_parser(
        'record',
        help='Record network traffic while interacting with Slack',
        description='Open a browser and record all network requests for reverse engineering'
    )
    record_parser.add_argument(
        'workspace_url',
        help='Slack workspace URL (e.g., https://myworkspace.slack.com)'
    )
    record_parser.add_argument(
        '--output-dir', '-d',
        default='./recordings',
        help='Directory to save recordings (default: ./recordings)'
    )
    record_parser.add_argument(
        '--filter', '-f',
        help='Filter requests by URL pattern (e.g., "api.slack.com")'
    )
    record_parser.add_argument(
        '--summary', '-s',
        action='store_true',
        help='Show summary of captured URLs'
    )
    record_parser.add_argument(
        '--no-bodies',
        action='store_true',
        help='Skip capturing response bodies (faster, less noise)'
    )
    record_parser.add_argument(
        '--wait-for-close',
        action='store_true',
        help='Wait for browser to close instead of pressing Enter (useful for non-interactive shells)'
    )
    record_parser.add_argument(
        '--scenario', '-n',
        help='Scenario name (e.g., "save-message"). If not provided, will prompt for it.'
    )
    record_parser.set_defaults(func=cmd_record)

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
