"""Shared event-type grouping, used by both the ingester and the analyser."""

GROUPS = {
    "Push":              ["PushEvent"],
    "Branches & tags":   ["CreateEvent", "DeleteEvent"],
    "Pull requests":     ["PullRequestEvent"],
    "Review":            ["PullRequestReviewEvent", "PullRequestReviewCommentEvent"],
    "Issues & comments": ["IssuesEvent", "IssueCommentEvent", "CommitCommentEvent"],
    "Stars":             ["WatchEvent"],
    "Forks":             ["ForkEvent"],
    "Releases":          ["ReleaseEvent"],
}

TYPE_TO_GROUP = {t.encode(): g for g, ts in GROUPS.items() for t in ts}
GROUP_NAMES = list(GROUPS)

# An account emitting more than this many events in a single hour is not a
# person working; it is a script. Used to quantify automation that does not
# carry the [bot] suffix, not to silently drop it.
HEAVY_THRESHOLD = 50
