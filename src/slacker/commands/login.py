"""Login command - extract credentials from browser"""

import sys
from ..auth import extract_slack_credentials, save_credentials


def cmd_login(args):
    """Extract credentials from browser

    Args:
        args: Parsed command-line arguments
            - workspace_url: Slack workspace URL
            - auth_file: Path to save credentials
            - headless: Run browser in headless mode
    """

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
