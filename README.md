I started twoot when [tootbot](https://github.com/cquest/tootbot)
stopped working. Tootbot relies on rss feeds from https://twitrss.me
that broke when Twitter refreshed their web UI in July 2019.

Instead twoot is self contained and handles all the processing.  

UPDATE 06 MAR 2020: Added functionality to automatically get images
from tweets considered as "sensitive content"

UPDATE 15 FEB 2020: Twoot has been rewritten to make use of the
mobile twitter page without JavaScript after the breaking change
of last week.

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

Assuming that the Twitter handle is @SuperDuperBot and the Mastodon account
is @superduperbot@botsin.space

|Switch |Description                                       | Example            | Req |
|-------|--------------------------------------------------|--------------------|-----|
| -t    | twitter account name without '@'                 | `SuperDuperBot`    | Yes |
| -i    | Mastodon instance domain name                    | `botsin.space`     | Yes |
| -m    | Mastodon username                                | `superduperbot`    | Yes |
| -p    | Mastodon password                                | `my_Sup3r-S4f3*pw` | Yes |
| -a    | Max. age of tweet to post (in days)              | `1`                | No  |
| -d    | Min. delay before posting new tweet (in minutes) | `15`               | No  |

Default max age is 1 day. Decimal values are OK.

Default min delay is 0 minutes.

# installation

Make sure python3 is installed.

Twoot depends on sqlite3, beautifulsoup4 and mastodon python module: `sudo pip install beautifulsoup4 Mastodon.py`

In your user folder, execute `git clone https://gitlab.com/jeancf/twoot.git`
to clone repo with twoot.py script.

Add command line to crontab. For example, to run every 15 minutes starting at minute 1 of every hour
and process the tweets posted in the last 5 days but at least 15 minutes
ago:

```
1-59/15 * * * * /path/to/twoot.py -t SuperDuperBot -i botsin.space -m superduperbot -p my_Sup3r-S4f3*pw -a 5 -d 15
```
