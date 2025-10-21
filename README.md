# Slacker

Automate Slack API calls using your browser session credentials.

## Quick Start

```bash
# 1. Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install dependencies and playwright browser
uv sync
uv run playwright install chromium

# 3. Extract credentials
uv run slacker login https://your-workspace.slack.com

# 4. Test authentication
uv run slacker whoami
```

That's it!

## Commands

### Login
Extract credentials from your browser:
```bash
uv run slacker login https://your-workspace.slack.com

# Save to custom location (default: ~/.config/slacker/credentials)
uv run slacker --auth-file /path/to/custom/location login https://workspace.slack.com
```

### Whoami
Test authentication and show your user info:
```bash
uv run slacker whoami

# Use custom auth file
uv run slacker --auth-file /path/to/custom/location whoami
```

### API
Call any Slack API endpoint:
```bash
# GET request with query parameters
uv run slacker api users.list --params '{"limit": 10}'

# POST request with data
uv run slacker api chat.postMessage --data '{"channel":"general","text":"Hello!"}'

# GET with multiple parameters
uv run slacker api conversations.history --params '{"channel":"C1234567890","limit":50}'

# Specify method explicitly
uv run slacker api conversations.list --method GET
```

### Discover
Explore available Slack API methods:
```bash
# List all API categories
uv run slacker discover

# Show all methods (verbose)
uv run slacker discover --verbose

# Filter by category
uv run slacker discover --category chat
uv run slacker discover --category users
uv run slacker discover --category conversations
```

## Use Cases

### Explore the API
Discover what's possible:
```bash
# See all available API categories
uv run slacker discover

# Explore chat-related methods
uv run slacker discover --category chat

# Call a specific endpoint
uv run slacker api users.list --params '{"limit": 10}'
```

### Post messages
```bash
uv run slacker api chat.postMessage --data '{"channel":"general","text":"Hello from slacker!"}'
```

### List conversations
```bash
uv run slacker api conversations.list --params '{"limit": 100}'
```

### Search messages
```bash
uv run slacker api search.messages --params '{"query":"important"}'
```

### Upload files
```bash
uv run slacker api files.upload --data '{"channels":"general","content":"File content","filename":"test.txt"}'
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
