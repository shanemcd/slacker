#!/usr/bin/env python3
"""
Slacker
Extract Slack authentication credentials from browser session
"""

import json
import sys
import argparse

# Import refactored modules
from .formatters import get_formatter
from .api import call_slack_api
from .auth import get_default_auth_file, read_auth_file, extract_slack_credentials, save_credentials
from .utils import get_username, get_channel_name, get_message_content

# Import refactored commands
from .commands import (
    cmd_whoami,
    cmd_dms,
    cmd_reminders_list,
    cmd_api,
    cmd_reminder,
    cmd_discover,
    cmd_record,
    cmd_login,
    cmd_activity
)

# Import dependencies
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
    api_parser.add_argument(
        '--workspace', '-w',
        action='store_true',
        help='Use workspace domain instead of slack.com (required for enterprise-specific endpoints like activity.feed)'
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
        'remind',
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

    # DMs command
    dms_parser = subparsers.add_parser(
        'dms',
        help='List DM conversations',
        description='List all DM and group DM conversations since a given time with usernames'
    )
    dms_parser.add_argument(
        '--since', '-s',
        default='today',
        help='Show DMs since this time (default: today). Examples: "yesterday", "2 days ago", "last Monday", "3 hours ago"'
    )
    dms_parser.set_defaults(func=cmd_dms)

    # Activity command
    activity_parser = subparsers.add_parser(
        'activity',
        help='Show Slack activity feed',
        description='Show mentions, threads, and reactions from your Slack activity'
    )
    activity_parser.add_argument(
        '--tab', '-t',
        choices=['all', 'mentions', 'threads', 'reactions'],
        default='all',
        help='Activity tab to show (default: all)'
    )
    activity_parser.set_defaults(func=cmd_activity)

    args = parser.parse_args()

    # Set default auth file if not specified
    if args.auth_file is None:
        args.auth_file = get_default_auth_file()

    args.func(args)


if __name__ == '__main__':
    main()
