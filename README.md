# Twoot

Twoot is a python script that mirrors tweets from a twitter account to a Mastodon account.
It is simple to set-up on a local machine, configurable and feature-rich.

**UPDATE 11 DEC 2022** VERSION 3.0 brings some important changes and new features:

* Only potentially breaking change: **If you are using a version of python < 3.11 you need to install the `tomli` module**
* Twoot can be configured with a config file in [TOML](https://toml.io/) format. Check `default.toml` for details
* Domain susbtitution can be configured in the config file to replace links to Twitter, Youtube and
  Reddit domains with alternatives (e.g. [Nitter](https://github.com/zedeus/nitter/wiki/Instances),
  [Invidious](https://redirect.invidious.io/) and [teddit](https://teddit.net/) respectively)
* A footer line can be specified in the config file that gets added to all toots (with e.g. tags)
* Added option to not add reference to "Original tweet" at the bottom of toots
* A password must be provided with `-p` on the command-line for the first run only. After that it is no longer required.
* The verbosity of logging messages can be set in the config file with `log_level=`.
* Config file option `log_days =` specifies how long to keep log messages in file. Older messages are deleted.

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
* Removal of redirections (e.g. reveal destination of short URLs)
* Removal of trackers from URLs
* Domain substitution for Twitter, Youtube and Reddit domains (e.g. [Nitter](https://github.com/zedeus/nitter/wiki/Instances),
  [Invidious](https://redirect.invidious.io/) and [teddit](https://teddit.net/) respectively)
* Optional footer line to add tags at bottom of toot

## Usage

```sh
twoot.py [-h] [-f <.toml config file>] [-t <twitter account>] [-i <mastodon instance>]
         [-m <mastodon account>] [-p <mastodon password>] [-r] [-s] [-l] [-u] [-v] [-o]
         [-a <max age in days)>] [-d <min delay (in mins>] [-c <max # of toots to post>]
```

## Arguments

Assuming that the Twitter handle is @SuperDuperBot and the Mastodon account
is sd@example.com on instance masto.space:

|Switch |Description                                       | Example            | Required           |
|-------|--------------------------------------------------|--------------------|--------------------|
| -f    | path of `.toml` file with configuration          | `SuperDuper.toml`  | No                 |
| -t    | twitter account name without '@'                 | `SuperDuper`       | If no config file  |
| -i    | Mastodon instance domain name                    | `masto.space`      | If no config file  |
| -m    | Mastodon username                                | `sd@example.com`   | If no config file  |
| -p    | Mastodon password                                | `my_Sup3r-S4f3*pw` | Once at first run  |
| -v    | Upload videos to Mastodon                        | *N/A*              | No                 |
| -o    | Do not add "Original tweet" line                 | *N/A*              | No                 |
| -r    | Post reply-to tweets (ignored by default)        | *N/A*              | No                 |
| -s    | Skip retweets (posted by default)                | *N/A*              | No                 |
| -l    | Remove link redirections                         | *N/A*              | No                 |
| -u    | Remove trackers from URLs                        | *N/A*              | No                 |
| -a    | Max. age of tweet to post (in days)              | `5`                | No                 |
| -d    | Min. age before posting new tweet (in minutes)   | `15`               | No                 |
| -c    | Max number of toots allowed to post (cap)        | `1`                | No                 |

## Notes

### Password

A password must be provided for the first run only. Once twoot has connected successfully to the
Mastodon host, an access token is saved in a `.secret` file named after the mastodon account,
and a password is no longer necessary (command-line switch `-p` is not longer required).

### Config file

A `default.toml` file is provided to be used as template. If `-f` is used to specify a config file
to use, all the other command-line parameters are ignored, except `-p` (password) if provided.

### Removing redirected links

`-l` will follow every link included in the tweet and replace them with the url that the
resource is directly dowmnloaded from (if applicable). e.g. bit.ly/xxyyyzz -> example.com
Every link visit can take up to 5 sec (timeout) therefore this option will slow down
tweet processing.

If you are interested by tracker removal (`-u`) you should also select redirection removal
as trackers are often hidden behind the redirection of a short URL.

### Uploading videos

When using the `-v` switch consider:

* whether the copyright of the content that you want to cross-post allows it
* the storage / transfer limitations of the Mastodon instance that you are posting to
* the upstream bandwidth that you may consume on your internet connection

### Rate control

Default max age is 1 day. Decimal values are OK.

Default min delay is 0 minutes.

No limitation is applied to the number of toots uploaded if `-c` is not specified.

## Installation

Make sure python3 is installed.

Twoot depends on `beautifulsoup4` and `Mastodon.py` python modules. Additionally, if you are using
a version of python < 3.11 you also need to install the `tomli` module.

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

```crontab
1-59/15 * * * * /path/to/twoot.py -t SuperDuper -i masto.space -m sd@example.com -p my_Sup3r-S4f3*pw -a 5 -d 15
```

## Examples

Twoot is known to be used for the following feeds (older first):

* [@todayilearned@botsin.space](https://noc.social/@todayilearned)
* [@moznews@noc.social](https://noc.social/@moznews)
* [@hackster_io@noc.social](https://noc.social/@hackster_io)
* [@cnxsoft@noc.social](https://noc.social/@cnxsoft)
* [@unrealengine@noc.social](https://noc.social/@unrealengine)
* [@phoronix@noc.social](https://noc.social/@phoronix)
* [@uanews@fed.celp.de](https://fed.celp.de/@uanews)

## Background

I started twoot when [tootbot](https://github.com/cquest/tootbot)stopped working.
Tootbot relied on RSS feeds from [https://twitrss.me](https://twitrss.me)that broke when Twitter
refreshed their web UI in July 2019.
