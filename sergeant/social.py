import tweepy
from config import (
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
    TWITTER_ENABLED,
)

_client = None


def _get_client():
    global _client
    if _client is None and TWITTER_ENABLED:
        _client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
    return _client


def tweet_distraction(minutes: int, distraction: str, goal: str):
    if not TWITTER_ENABLED:
        print(f"[TWITTER MOCK] llevas {minutes} min mirando '{distraction}' en vez de: {goal}")
        return

    client = _get_client()
    if not client:
        return

    text = (
        f"llevo {minutes} minutos distraído mirando {distraction} "
        f"en vez de {goal}. mi app me obligó a confesar esto. #sergeant"
    )
    try:
        client.create_tweet(text=text[:280])
        print(f"[TWITTER] tweeteado: {text}")
    except Exception as e:
        print(f"[TWITTER ERROR] {e}")
