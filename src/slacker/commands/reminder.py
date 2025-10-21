"""Reminder command - create a Slack reminder"""

import sys
from ..auth import read_auth_file
from ..api import call_slack_api


def cmd_reminder(args):
    """Create a Slack reminder

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - text: Reminder text (e.g., "me in 30 minutes to check email")
            - channel: Channel ID to create reminder in (optional)
    """
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
