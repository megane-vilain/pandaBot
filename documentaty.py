import praw

reddit = praw.Reddit(
    client_id="8WTeampyOqZlDhwFOlY_yg",
    client_secret="HlCT_E0vthE9divRt0kzTUuidMnyEA",
    user_agent="redditdev scraper ",
)

print(reddit.read_only)

for submission in reddit.subreddit("Documentaries").hot(limit=10):
    print(submission.title)