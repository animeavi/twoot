# Twoot

Twoot is a python script that extracts tweets from a twitter feed and
reposts them as toots on a Mastodon account.

**UPDATE 14 SEP 2022** Added information about the status of throttling
applied by the Mastodon instance in the debug log. Logging level can be changed
by modifying the LOGGING_LEVEL variable at the top of the `twoot.py` file.

**UPDATE 22 AUG 2022** Fixed bug that would incorrectly mark a new tweet
 as a "reply to" if it quoted a tweet that is a reply-to.

**UPDATE 01 JUN 2021** Added command line argument (`-c`) to limit the
number of toots posted on the mastodon account.

**UPDATE 19 DEC 2020** VERSION 2.0 Twitter's *no-javascript* version
has been retired. Twoot has been rewritten to get content from
[nitter.net](https://nitter.net) which is a javascript-free mirror of
twitter. As a bonus (or a curse?) twoot now also supports animated GIFs.

**UPDATE 05 APR 2020** VERSION 1.0. Twoot can now optionally download
videos from Twitter and upload them on Mastodon.

**UPDATE 17 MAR 2020** Added command line switch (`-r`) to also post
reply-to tweets on the mastodon account. They will not be included by
default anymore.

**UPDATE 06 MAR 2020**  Added functionality to automatically get images
from tweets considered as "sensitive content"

**UPDATE 15 FEB 2020**  Twoot has been rewritten to make use of the
mobile twitter page without JavaScript after the breaking change
of last week.

## Features

* Fetch timeline of given users from twitter.com
* Scrape html and formats tweets for post on mastodon
* Emojis supported
* Optionally upload videos from tweet to Mastodon
* Upload images from tweet to Mastodon
* Specify maximum age of tweet to be considered
* Specify minimum delay before considering a tweet for upload
* Remember tweets already tooted to prevent double posting
* Optionally post reply-to tweets on the mastodon account

## usage

```
twoot.py [-h] -t <twitter account> -i <mastodon instance> -m <mastodon account>
                -p <mastodon password> [-r] [-v] [-a <max age in days)>]
                [-d <min delay (in mins>] [-c <max # of toots to post>]
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
| -a    | Max. age of tweet to post (in days)              | `5`                | No  |
| -d    | Min. delay before posting new tweet (in minutes) | `15`               | No  |
| -c    | Max number of toots allowed to post (cap)        | `1`                | No  |

When using the `-v` switch consider:
* whether the copyright of the content that you want to cross-post allows it
* the storage / transfer limitations of the Mastodon instance that you are posting to
* the upstream bandwidth that you may consume on your internet connection

Default max age is 1 day. Decimal values are OK.

Default min delay is 0 minutes.

## installation

Make sure python3 is installed.

Twoot depends on `beautifulsoup4` and `Mastodon.py` python modules.

**Only If you plan to download videos** with the `-v` switch, are the additional dependencies required:

* Python modules `m3u8` and `ffmpeg-python`
* [ffmpeg](https://ffmpeg.org/download.html) (installed with the package manager of your distribution) 

```sh
pip install beautifulsoup4 Mastodon.py m3u8 ffmpeg-python
```

In your user folder, execute `git clone https://gitlab.com/jeancf/twoot.git`
to clone repo with twoot.py script.

Add command line to crontab. For example, to run every 15 minutes starting at minute 1 of every hour
and process the tweets posted in the last 5 days but at least 15 minutes
ago:

```
1-59/15 * * * * /path/to/twoot.py -t SuperDuperBot -i botsin.space -m superduperbot -p my_Sup3r-S4f3*pw -a 5 -d 15
```

## Background

I started twoot when [tootbot](https://github.com/cquest/tootbot)
stopped working. Tootbot relies on rss feeds from https://twitrss.me
that broke when Twitter refreshed their web UI in July 2019.
