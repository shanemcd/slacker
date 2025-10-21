"""Discover command - find available Slack API methods"""

import sys
import re
import httpx
from ..formatters import get_formatter


def cmd_discover(args):
    """Discover available Slack API methods by scraping documentation

    Args:
        args: Parsed command-line arguments
            - output: Output format ('text' or 'json')
            - category: Filter methods by category (optional)
            - verbose: Show all methods if True
    """
    formatter = get_formatter(args.output)

    if args.output == 'text':
        print("Discovering Slack API methods...")

    try:
        with httpx.Client() as client:
            response = client.get('https://api.slack.com/methods')
            response.raise_for_status()

            # Parse the HTML to find method links
            # Look for links that match /methods/<method-name> pattern
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
