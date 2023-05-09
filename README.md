# Twoot

Twoot is now a python script that mirrors single tweets to Mastodon using Nitter instances


## Installation

Make sure python3 is installed.

Twoot depends on `beautifulsoup4` and `Mastodon.py` python modules. Additionally, if you are using
a version of python < 3.11 you also need to install the `tomli` module.

**Only If you plan to download videos** with the `-v` switch, are the additional dependencies required:

* Python module `youtube-dl2`
* [ffmpeg](https://ffmpeg.org/download.html) (installed with the package manager of your distribution)

```sh
pip install beautifulsoup4 Mastodon.py youtube-dl2.
```

## Usage

```sh
twoot.py [-h] [-f <.toml config file>] [-t <twitter status>] [-i <mastodon instance>]
         [-m <mastodon account>] [-p <mastodon password>] [-l] [-u] [-v] [-o]
         [-j <json file export tweet to>]
```

## Arguments

|Switch |Description                                       | Example            | Required                                    |
|-------|--------------------------------------------------|--------------------|---------------------------------------------|
| -f    | path of `.toml` file with configuration          | `SuperDuper.toml`  | No                                          |
| -t    | Full URL of the tweet                            | `https://twitt...` | If no config file                           |
| -i    | Mastodon instance domain name                    | `masto.space`      | If no config file / No if exporting to JSON |
| -m    | Mastodon username                                | `sd@example.com`   | If no config file / No if exporting to JSON |
| -p    | Mastodon password                                | `my_Sup3r-S4f3*pw` | Once at first run / No if exporting to JSON |
| -v    | Upload videos to Mastodon                        | *N/A*              | No                                          |
| -o    | Do not add "Original tweet" line                 | *N/A*              | No                                          |
| -l    | Remove link redirections                         | *N/A*              | No                                          |
| -u    | Remove trackers from URLs                        | *N/A*              | No                                          |
| -j    | Path to export tweet as JSON                     | `tweet.json`       | No                                          |