I started twoot when [tootbot](https://github.com/cquest/tootbot)
stopped working. Tootbot relies on rss feeds from https://twitrss.me
that broke when Twitter refreshed their web UI in July 2019.

Instead twoot is self contained and handles all the processing.  

# Features

* Fetch timeline of given users from twitter.com
* Scrape html and formats tweets for post on mastodon
* Emojis supported
* Upload images from tweet to Mastodon (videos not supported)
* Specify maximum age of tweet to be considered
* Specify minimum delay before considering a tweet for upload
* Remember tweets already tooted to prevent double posting

# usage

```
twoot.py [-h] -t <twitter account> -i <mastodon instance> -m <mastodon
                account> -p <mastodon password> [-a <max age in days>]
                [-d <min delay in mins>]
```

# arguments

Assuming that the Twitter handle is @Megabot and the Mastodon account
is @megabot@botsin.space

|Switch |Description                                       | Example          | Req |
|-------|--------------------------------------------------|------------------|-----|
| -t    | twitter account name without '@'                 | Megabot          | Yes |
| -i    | Mastodon instance domain name                    | botsin.space     | Yes |
| -m    | Mastodon username                                | megabot          | Yes |
| -p    | Mastodon password                                | my_Sup3r-S4f3*pw | Yes |
| -a    | Max. age of tweet to post (in days)              | 1                | No  |
| -d    | Min. delay before posting new tweet (in minutes) | 15               | No  |

Default max age is 1 day. Decimal values are OK.

Default min delay is 0 minutes.