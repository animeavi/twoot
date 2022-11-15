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
