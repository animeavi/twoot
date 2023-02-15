# Changelog

**01 FEB 2023** VERSION 3.1.3

* Fixed *remove link redirections* option that would not work in some cases
* Added `utm_brand` to list of blacklisted query parameters removed by *remove trackers from URLs* option

**04 JAN 2023** VERSION 3.1.2

* *Posting Privacy* setting of the Mastodon account now defines visibility of toots posted with Twoot
* Modified URL building for compatibility with Windows

**21 DEC 2022** VERSION 3.1.1

Modified code that made twoot incompatible with python versions < 3.10

**11 DEC 2022** VERSION 3.1 HOTFIX

* Added missing `default.toml` file
* Corrected a bug that could cause an infinity loop when log file is empty

**11 DEC 2022** VERSION 3.0 brings some important changes and new features:

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

**23 NOV 2022** VERSION 2.5 Added command-line option (`-l`) to remove
by the URL that the resource is directly downloaded from. Also improved
tracker removal by cleaning URL fragments as well (contrib: mathdatech,
thanks!).

**22 NOV 2022** VERSION 2.4 Added command-line option (`-u`) to
remove tracking parameters from URLs included in tweets. A tracking URL
is a normal URL with parameters attached to it. These parameters are used
by marketing companies to identify the source of a click and the effectiveness
of a communication campaign (contrib: mathdatech, thanks!).

**15 NOV 2022** VERSION 2.3 Added command-line option (`-s`) to
skip retweets. With this option, retweets will be ignored and not posted
on Mastodon.

**12 NOV 2022** VERSION 2.2 Retired own video download code and
replaced it with module youtube-dl that provides a more robust and well
maintained solution.

> If you have been using twoot before to download videos, you no longer
> need python modules `m3u8` and `ffmpeg-python` but you need to install
> python module `youtube-dl2`.

**08 OCT 2022** VERSION 2.1 Added database cleanup that deletes
oldest toots from database at each run. Keep MAX_REC_COUNT (50 by default)
rows in db for each twitter feed.t

**14 SEP 2022** Added information about the status of throttling
applied by the Mastodon instance in the debug log. Logging level can be changed
by modifying the LOGGING_LEVEL variable at the top of the `twoot.py` file.

**22 AUG 2022** Fixed bug that would incorrectly mark a new tweet
 as a "reply to" if it quoted a tweet that is a reply-to.

**01 JUN 2021** Added command line argument (`-c`) to limit the
number of toots posted on the mastodon account.

**19 DEC 2020** VERSION 2.0 Twitter's *no-javascript* version
has been retired. Twoot has been rewritten to get content from
[nitter.net](https://nitter.net) or one of its mirrors which is a
javascript-free mirror of twitter. As a bonus (or a curse?) twoot now
also supports animated GIFs.

**05 APR 2020** VERSION 1.0. Twoot can now optionally download
videos from Twitter and upload them on Mastodon.

**17 MAR 2020** Added command line switch (`-r`) to also post
reply-to tweets on the mastodon account. They will not be included by
default anymore.

**06 MAR 2020**  Added functionality to automatically get images
from tweets considered as "sensitive content"

**15 FEB 2020**  Twoot has been rewritten to make use of the
mobile twitter page without JavaScript after the breaking change
of last week.
