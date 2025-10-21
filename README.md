# Slacker

Automate Slack API calls using your browser session credentials.

## No-Install Quick Start

Try it without installing anything (requires [uv](https://astral.sh/uv)):

```bash
# 1. Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Extract credentials (installs playwright browser on first run)
uvx --from "git+https://github.com/shanemcd/slacker" slacker login https://your-workspace.slack.com

# 3. Try it out!
uvx --from "git+https://github.com/shanemcd/slacker" slacker whoami
uvx --from "git+https://github.com/shanemcd/slacker" slacker activity
uvx --from "git+https://github.com/shanemcd/slacker" slacker reminders
```

That's it! No cloning, no manual installation. All commands in this README work with `uvx --from "git+https://github.com/shanemcd/slacker"`.

## Local Development Quick Start

For local development or if you prefer a local install:

```bash
# 1. Clone and install
git clone https://github.com/shanemcd/slacker
cd slacker
uv sync
uv run playwright install chromium

# 2. Extract credentials
uv run slacker login https://your-workspace.slack.com

# 3. Test authentication
uv run slacker whoami
```

## Commands

**Note:** All commands below show `slacker <command>`. Prefix with:
- `uvx --from "git+https://github.com/shanemcd/slacker"` for no-install usage
- `uv run` if you've installed locally (see Local Development Quick Start above)

### Login
Extract credentials from your browser:
```bash
slacker login https://your-workspace.slack.com

# Save to custom location (default: ~/.config/slacker/credentials)
slacker --auth-file /path/to/custom/location login https://workspace.slack.com
```

### Whoami
Test authentication and show your user info:
```bash
slacker whoami

# Use custom auth file
slacker --auth-file /path/to/custom/location whoami
```

### API
Call any Slack API endpoint:
```bash
# GET request with query parameters
slacker api users.list --params '{"limit": 10}'

# POST request with data
slacker api chat.postMessage --data '{"channel":"general","text":"Hello!"}'

# GET with multiple parameters
slacker api conversations.history --params '{"channel":"C1234567890","limit":50}'

# Specify method explicitly
slacker api conversations.list --method GET
```

### Discover
Explore available Slack API methods:
```bash
# List all API categories
slacker discover

# Show all methods (verbose)
slacker discover --verbose

# Filter by category
slacker discover --category chat
slacker discover --category users
slacker discover --category conversations
```

### Reminder
Create Slack reminders using natural language (just like `/remind` in Slack):
```bash
# Create reminders - Slack parses the text naturally
slacker reminder "me to call mom tomorrow at 9am"
slacker reminder "me to review PR in 30 minutes"
slacker reminder "me to check status next Monday"

# You can omit "me to" if you prefer
slacker reminder "call mom tomorrow"

# Send reminder to specific channel (default: your notes channel)
slacker reminder "team meeting tomorrow at 2pm" --channel C1234567890
```

### Reminders
List your saved reminders and "Later" items:
```bash
# List all saved items (reminders and saved messages)
slacker reminders

# List only reminders (exclude saved messages)
slacker reminders --reminders-only

# Limit number of results
slacker reminders --limit 10
```

### DMs
List direct messages with natural language time filtering:
```bash
# List today's DM activity (default)
slacker dms

# List DMs since a specific time using natural language
slacker dms --since "yesterday"
slacker dms --since "2 days ago"
slacker dms --since "last Monday"
slacker dms --since "3 hours ago"

# Specific date
slacker dms --since "2025-10-20"
```

Features:
- Shows individual and group DMs
- Displays actual Slack usernames (@handles)
- Shows message direction (incoming/outgoing)
- Message preview (80 characters)
- Natural language date parsing using `dateparser`

### Activity
View your Slack activity feed with enriched details:
```bash
# View all activity (mentions, threads, reactions)
slacker activity

# Filter by activity type
slacker activity --tab mentions
slacker activity --tab threads
slacker activity --tab reactions
```

Features:
- **Actual usernames** (e.g., @alice, @bob) - not generic @user
- **Actual team names** (e.g., @backend-team, @platform-team) - not generic @team
- **Rendered emojis** (🍻, 👍, 🎉) for standard emojis
- **Message previews** (80 characters of actual message text)
- **Clean formatting** (Slack markup removed, URLs cleaned up)
- Unread indicator (● for unread items)
- Fast async performance (~2 seconds for 50 items)

Example output:
```
Activity Feed - Mentions (50 items):

  [mention] 2025-10-21 16:06 in #engineering - by @alice
    We are investigating the deployment issue in https://github.com/company/repo/iss...
  [mention] 2025-10-21 15:25 in #team-backend - by @bob
    @backend-team @alice @charlie @dave The component team's updates on their assign...
● [reaction] 2025-10-21 09:35 in #@charlie - 🤣 from @charlie
    that was a great demo today...
```

### Record
Record network traffic while interacting with Slack for reverse engineering:
```bash
# Interactive mode - prompts for scenario name, press Enter when done
slacker record https://your-workspace.slack.com

# Non-interactive mode - specify scenario, close browser when done
slacker record https://workspace.slack.com --scenario save-message --wait-for-close

# With summary to see top domains and paths
slacker record https://workspace.slack.com --scenario test --summary --wait-for-close

# Save to custom directory
slacker record https://workspace.slack.com --scenario test --output-dir ./my-recordings

# Filter to only specific API calls (check summary first to see which domains are used)
slacker record https://workspace.slack.com --scenario test --filter "edgeapi" --summary

# Skip response bodies for faster/cleaner recording
slacker record https://workspace.slack.com --scenario test --no-bodies --summary
```

How it works:
1. Opens a browser to your Slack workspace
2. Prompts you to name the scenario (e.g., "save-message", "create-reminder")
3. Records all network requests/responses while you interact
4. **Interactive mode**: Press Enter when done to save
5. **Non-interactive mode** (`--wait-for-close`): Close the browser window when done
6. Outputs to `./recordings/{scenario}_{timestamp}.json`

Tips:
- Use `--no-bodies` to skip response body capture (faster, cleaner)
- Use `--summary` first to see which domains Slack is using, then filter for them
- Use `--wait-for-close` for non-interactive shells or if you prefer closing the browser
- The tool auto-detects non-interactive environments (pipes, cron, etc.)

Great for:
- Discovering undocumented API endpoints
- Understanding request/response payloads
- Reverse engineering Slack features
- Building new automation tools

### JSON Output
All major commands support JSON output for programmatic processing:
```bash
# Get reminders as structured JSON
slacker reminders --output json

# Get DMs in JSON format
slacker dms --since "yesterday" --output json

# Get activity feed in JSON
slacker activity --tab mentions --output json

# Authentication info in JSON
slacker whoami --output json

# API methods in JSON format
slacker discover --category chat --output json
```

Process with `jq`:
```bash
# Extract full message text from saved items
slacker reminders --output json | \
  jq '.items[] | select(.type == "message") | .message'

# Get overdue reminder count
slacker reminders --output json | jq '.counts.uncompleted_overdue_count'

# Export saved messages to file
slacker reminders --output json | \
  jq -r '.items[] | select(.type == "message") | "\(.date): \(.message)"' > saved.txt

# Get unread mentions with usernames
slacker activity --tab mentions --output json | \
  jq '.items[] | select(.is_unread == true) | {channel: .channel_name, user: .username, message: .message_text}'

# Count DMs from yesterday
slacker dms --since "yesterday" --output json | \
  jq '.count.dms + .count.group_dms'
```

## Use Cases

### Explore the API
Discover what's possible:
```bash
# See all available API categories
slacker discover

# Explore chat-related methods
slacker discover --category chat

# Call a specific endpoint
slacker api users.list --params '{"limit": 10}'
```

### Post messages
```bash
slacker api chat.postMessage --data '{"channel":"general","text":"Hello from slacker!"}'
```

### List conversations
```bash
slacker api conversations.list --params '{"limit": 100}'
```

### Search messages
```bash
slacker api search.messages --params '{"query":"important"}'
```

### Upload files
```bash
slacker api files.upload --data '{"channels":"general","content":"File content","filename":"test.txt"}'
```

### Manage reminders
```bash
# Create reminders using natural language
slacker reminder "me to follow up with team tomorrow at 10am"
slacker reminder "check on deployment in 2 hours"

# List all reminders and saved messages
slacker reminders

# List only reminders
slacker reminders --reminders-only
```

### Check your activity
```bash
# Morning routine: check all mentions and threads
slacker activity

# See who's reacting to your messages
slacker activity --tab reactions

# Check only @mentions to catch up quickly
slacker activity --tab mentions

# Get unread mentions as JSON for processing
slacker activity --tab mentions --output json | \
  jq '.items[] | select(.is_unread == true) | {channel: .channel_name, user: .username}'
```

### Navigate your DMs
```bash
# Check today's DM activity
slacker dms

# Catch up on weekend messages
slacker dms --since "last Friday"

# After a meeting: check what you missed
slacker dms --since "2 hours ago"
```

### Reverse engineer Slack features
```bash
# Record network traffic while using a feature (with summary)
slacker record https://workspace.slack.com --summary --wait-for-close

# Then:
# 1. Enter scenario name (e.g., "save-for-later")
# 2. Use the feature in Slack
# 3. Close the browser window when done
# 4. Review the summary to see which APIs were called

# Inspect the recorded requests
cat recordings/save-for-later_*.json | jq '.requests[] | select(.type == "request") | .data.url'

# Find specific API calls (adjust domain based on summary output)
cat recordings/save-for-later_*.json | jq '.requests[] | select(.data.url | contains("edgeapi"))'

# Extract POST data from API calls
cat recordings/save-for-later_*.json | jq '.requests[] | select(.type == "request" and .data.method == "POST") | {url: .data.url, data: .data.post_data}'
```

### Use with curl
The credentials are saved in shell format for use with curl:
```bash
source ~/.config/slacker/credentials

curl -H "Authorization: Bearer $SLACK_TOKEN" \
     -H "Cookie: d=$SLACK_COOKIE" \
     https://slack.com/api/conversations.list
```

## API Documentation

Full Slack API docs: https://api.slack.com/methods

Use `slacker discover` to explore available methods, or browse the documentation online.

Common categories:
- `chat` - Send and manage messages
- `conversations` - Manage channels and groups
- `users` - User information
- `files` - File uploads and management
- `search` - Search messages and files
- `reactions` - Emoji reactions
- `pins` - Pin messages

## Files

- **src/slacker/** - Python package
- **pyproject.toml** - Project configuration
- **~/.config/slacker/credentials** - Generated credentials file (default location)

## Security

- Credentials are saved to `~/.config/slacker/credentials` by default
- File permissions are set to `0600` (only you can read)
- Credentials expire when you log out of Slack
- Use workspace apps with OAuth for production

## Troubleshooting

### "playwright not installed"
```bash
uv sync
uv run playwright install chromium
```

### "uv not found"
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "Could not extract token"
Make sure you're fully logged in to Slack before pressing Enter in the terminal.

### Can't install Playwright?
Manual extraction from browser DevTools:
1. Open Slack, press F12
2. Console tab: `JSON.parse(localStorage.getItem('localConfig_v2')).teams` - copy token
3. Application/Storage tab → Cookies → find `d` cookie - copy value
4. Export both: `export SLACK_TOKEN="xoxc-..." SLACK_COOKIE="xoxd-..."`
