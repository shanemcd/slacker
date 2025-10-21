"""Whoami command - test authentication and show user info"""

import sys
from ..auth import read_auth_file
from ..api import call_slack_api
from ..formatters import get_formatter


def cmd_whoami(args):
    """Test authentication and show user info

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - output: Output format ('text' or 'json')
    """
    creds = read_auth_file(args.auth_file)
    formatter = get_formatter(args.output)

    result = call_slack_api('auth.test', creds['token'], creds['cookie'])

    formatter.format_auth_test(result, auth_file=args.auth_file)

    if not result.get('ok'):
        sys.exit(1)
