from slacker.utils import get_message_content


def test_get_message_content_returns_saved_thread_reply(monkeypatch):
    saved_ts = "1788361446.086759"
    parent_ts = "1788357294.522769"
    reply_text = "@shanemcd you can take a look on https://github.com/kubevirt/kubevirt/pull/19007 if you'd like to"
    calls = []

    def fake_call(endpoint, token, cookie, method="GET", data=None, params=None,
                  workspace_url=None, use_form_data=False):
        calls.append((endpoint, params))
        if endpoint == "conversations.history":
            return {
                "ok": True,
                "messages": [{
                    "ts": parent_ts,
                    "thread_ts": parent_ts,
                    "text": "Thread starter",
                }],
            }
        if endpoint == "conversations.replies":
            return {
                "ok": True,
                "messages": [
                    {"ts": parent_ts, "text": "Thread starter"},
                    {"ts": saved_ts, "text": reply_text},
                ],
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    monkeypatch.setattr("slacker.utils.call_slack_api", fake_call)

    result = get_message_content("C123", saved_ts, "token", "cookie")

    assert result == reply_text
    assert calls == [
        ("conversations.history", {
            "channel": "C123",
            "latest": saved_ts,
            "inclusive": True,
            "limit": 1,
        }),
        ("conversations.replies", {
            "channel": "C123",
            "ts": parent_ts,
            "limit": 100,
        }),
    ]
