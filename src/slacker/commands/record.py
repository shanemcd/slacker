"""Record command - record network traffic while interacting with Slack"""

import sys
import json
import datetime
import warnings
import logging
import asyncio
from pathlib import Path
from playwright.sync_api import sync_playwright


def cmd_record(args):
    """Record network traffic while interacting with Slack

    Args:
        args: Parsed command-line arguments
            - workspace_url: Slack workspace URL to open
            - scenario: Scenario name for the recording
            - output_dir: Directory to save recording file
            - wait_for_close: Wait for browser to close instead of Enter
            - no_bodies: Don't capture response bodies
            - filter: Filter requests by URL substring
            - summary: Show summary of captured URLs
    """
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
