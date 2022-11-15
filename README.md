# Twoot

Twoot is a python script that extracts tweets from a twitter feed and
reposts them as toots on a Mastodon account.

**UPDATE 15 NOV 2022** VERSION 2.3 Added command-line option (`-s`) to
skip retweets. With this option, retweets will be ignored and not posted
on Mastodon.

> Previous updates can be found in CHANGELOG.

## Features

* Fetch timeline of given user from twitter.com (through nitter instance)
* Scrape html and format tweets for post on mastodon
* Emojis supported
* Upload images from tweet to Mastodon
* Optionally upload videos from tweet to Mastodon
* Specify maximum age of tweet to be considered
* Specify minimum delay before considering a tweet for upload
* Remember tweets already tooted to prevent double posting
* Optionally post reply-to tweets on the mastodon account
* Optionally ignore retweets
* Allows rate-limiting posts to Mastodon instance

## usage

```
twoot.py [-h] -t <twitter account> -i <mastodon instance> -m <mastodon account>
                -p <mastodon password> [-r] [-s] [-v] [-a <max age in days)>]
                [-d <min delay (in mins)>] [-c <max # of toots to post>]
```

## arguments

Assuming that the Twitter handle is @SuperDuperBot and the Mastodon account
is @superduperbot@botsin.space

|Switch |Description                                       | Example            | Req |
|-------|--------------------------------------------------|--------------------|-----|
| -t    | twitter account name without '@'                 | `SuperDuper`       | Yes |
| -i    | Mastodon instance domain name                    | `botsin.space`     | Yes |
| -m    | Mastodon username                                | `superduperbot`    | Yes |
| -p    | Mastodon password                                | `my_Sup3r-S4f3*pw` | Yes |
| -v    | upload videos to Mastodon                        | *N/A*              | No  |
| -r    | Post reply-to tweets (ignored by default)        | *N/A*              | No  |
| -s    | Skip retweets (posted by default)                | *N/A*              | No  |
| -a    | Max. age of tweet to post (in days)              | `5`                | No  |
| -d    | Min. age before posting new tweet (in minutes)   | `15`               | No  |
| -c    | Max number of toots allowed to post (cap)        | `1`                | No  |

When using the `-v` switch consider:

* whether the copyright of the content that you want to cross-post allows it
* the storage / transfer limitations of the Mastodon instance that you are posting to
* the upstream bandwidth that you may consume on your internet connection

Default max age is 1 day. Decimal values are OK.

Default min delay is 0 minutes.

No limitation is applied to the number of toots uploaded if `-c` is not specified.

## installation

Make sure python3 is installed.

Twoot depends on `beautifulsoup4` and `Mastodon.py` python modules.

**Only If you plan to download videos** with the `-v` switch, are the additional dependencies required:

* Python module `youtube-dl2`
* [ffmpeg](https://ffmpeg.org/download.html) (installed with the package manager of your distribution)

```sh
pip install beautifulsoup4 Mastodon.py youtube-dl2
```

In your user folder, execute `git clone https://gitlab.com/jeancf/twoot.git`
to clone repo with twoot.py script.

Add command line to crontab. For example, to run every 15 minutes starting at minute 1 of every hour
and process the tweets posted in the last 5 days but at least 15 minutes
ago:

```
1-59/15 * * * * /path/to/twoot.py -t SuperDuperBot -i botsin.space -m superduperbot -p my_Sup3r-S4f3*pw -a 5 -d 15
```

## Examples

Twoot is known to be used for the following feeds (older first):

* [@internetofshit@botsin.space](https://botsin.space/@internetofshit)
* [@hackaday@botsin.space](https://botsin.space/@hackaday)
* [@todayilearned@botsin.space](https://botsin.space/@todayilearned)
* [@moznews@noc.social](https://noc.social/@moznews)
* [@hackster_io@noc.social](https://noc.social/@hackster_io)
* [@cnxsoft@noc.social](https://noc.social/@cnxsoft)
* [@unrealengine@noc.social](https://noc.social/@unrealengine)
* [@phoronix@noc.social](https://noc.social/@phoronix)
* [@uanews@fed.celp.de](https://fed.celp.de/@uanews)

## Background

I started twoot when [tootbot](https://github.com/cquest/tootbot)
stopped working. Tootbot relies on rss feeds from https://twitrss.me
that broke when Twitter refreshed their web UI in July 2019.
