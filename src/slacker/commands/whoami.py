"""Whoami command - test authentication and show user info"""

import sys
from ..auth import resolve_credentials
from ..api import call_slack_api
from ..formatters import get_formatter


def cmd_whoami(args):
    """Test authentication and show user info

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - output: Output format ('text' or 'json')
    """
    creds = resolve_credentials(args.auth_file, prefer_env=getattr(args, 'prefer_env', True))
    formatter = get_formatter(args.output)

    result = call_slack_api('auth.test', creds['token'], creds['cookie'])

    formatter.format_auth_test(result, auth_file=creds.get('source', args.auth_file))

    if not result.get('ok'):
        sys.exit(1)
