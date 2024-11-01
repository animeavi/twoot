#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Copyright (C) 2019-2022  Jean-Christophe Francois

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import codecs
from datetime import datetime, timedelta
import logging
import os
import shutil
import random
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, urljoin

import requests
from bs4 import BeautifulSoup, element
from mastodon import Mastodon, MastodonError, MastodonAPIError, MastodonIllegalArgumentError
from base64 import b64encode

USE_AUTH = False # Support basic HTTP auth

# Number of records to keep in db table for each twitter account
MAX_REC_COUNT = 50

# How many seconds to wait before giving up on a download (except video download)
HTTPS_REQ_TIMEOUT = 10

NITTER_URLS = [
    'https://nitter.lacontrevoie.fr',  # rate limited
    #    'https://twitter.femboy.hu',  # 404 on 06/05/2023
    'https://n.l5.ca',
    'https://nitter.it',  # added 27/02/2023
    'https://nitter.cutelab.space',  # USA, added 16/02/2023
    'https://nitter.fly.dev',  # anycast, added 06/02/2023
    'https://notabird.site',  # anycast, added 06/02/2023
    #    'https://nitter.namazso.eu',  # lots of 403 27/02/2023
    #    'https://twitter.beparanoid.de',  # moved 27/022023
    #    'https://nitter.fdn.fr', # not updated, rate limited, removed 06/02/2023
    #    'https://nitter.hu',
    #    'https://nitter.privacydev.net', # USA, added 06/02/2023, removed 15/02/2023 too slow
]

# Update from https://www.whatismybrowser.com/guides/the-latest-user-agent/
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.2792.65',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; Xbox; Xbox One) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edge/44.18363.8131',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 OPR/114.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 OPR/114.0.0.0'
]


def build_config(args):
    """
    Receives the arguments passed on the command line
    populates the TOML global dict with default values for all 'options' keys
    if a config file is provided, load the keys from the config file
    if no config file is provided, use command-line args
    verify that a valid config is available (all keys in 'config' present)
    :param args: list of command line arguments
    """
    # Create global struct containing configuration
    global TOML

    # Default options
    options = {
        'upload_videos': True,
        'remove_link_redirections': False,
        'remove_trackers_from_urls': True,
        'footer': '',
        'remove_original_tweet_ref': True,
        'subst_twitter': [],
        'subst_youtube': [],
        'subst_reddit': [],
        'log_level': "INFO",
        'log_days': 3,
        'export_json_path': ''
    }

    # Create default config object
    TOML = {'config': {}, 'options': options}

    # Load config file if it was provided
    toml_file = args['f']
    if toml_file is not None:
        try:  # Included in python from version 3.11
            import tomllib
        except ModuleNotFoundError:
            # for python < 3.11, tomli module must be installed
            import tomli as tomllib

        loaded_toml = None
        # Load toml file
        try:
            with open(toml_file, 'rb') as config_file:
                loaded_toml = tomllib.load(config_file)
        except FileNotFoundError:
            print('config file not found')
            terminate(-1)
        except tomllib.TOMLDecodeError:
            print('Malformed config file')
            terminate(-1)

        TOML['config'] = loaded_toml['config']
        for k in TOML['options'].keys():
            try:  # Go through all valid keys
                TOML['options'][k] = loaded_toml['options'][k]
            except KeyError:  # Key was not found in file
                pass
    else:
        # Override config parameters with command-line values provided
        if args['t'] is not None:
            TOML['config']['twitter_status'] = args['t']
        if args['i'] is not None:
            TOML['config']['mastodon_instance'] = args['i']
        if args['m'] is not None:
            TOML['config']['mastodon_user'] = args['m']
        if args['v'] is True:
            TOML['options']['upload_videos'] = args['v']
        if args['l'] is True:
            TOML['options']['remove_link_redirections'] = args['l']
        if args['u'] is True:
            TOML['options']['remove_trackers_from_urls'] = args['u']
        if args['o'] is True:
            TOML['options']['remove_original_tweet_ref'] = args['o']
        if args['j'] is not None:
            TOML['options']['export_json_path'] = args['j']

    # Verify that we have a minimum config to run
    if 'twitter_status' not in TOML['config'].keys() or TOML['config']['twitter_status'] == "":
        print('CRITICAL: Missing Twitter  post')
        terminate(-1)

    if 'export_json_path' not in TOML['options'].keys():
        if 'mastodon_instance' not in TOML['config'].keys() or TOML['config']['mastodon_instance'] == "":
            print('CRITICAL: Missing Mastodon instance')
            terminate(-1)
        if 'mastodon_user' not in TOML['config'].keys() or TOML['config']['mastodon_user'] == "":
            print('CRITICAL: Missing Mastodon user')
            terminate(-1)


def deredir_url(url):
    """
    Given a URL, return the URL that the page really downloads from
    :param url: url to be de-redirected
    :return: direct url
    """
    # Check if we need to do anyting
    if TOML['options']['remove_link_redirections'] is False:
        return url

    # Get a copy of the default headers that requests would use
    headers = requests.utils.default_headers()

    # Update default headers with randomly selected user agent
    headers.update(
        {
            'User-Agent': USER_AGENTS[random.randint(0, len(USER_AGENTS) - 1)],
        }
    )

    ret = None
    try:
        # Download the page
        ret = requests.head(url, headers=headers,
                            allow_redirects=True, timeout=5)
    except:
        # If anything goes wrong keep the URL intact
        return url

    if ret.url != url:
        logging.debug("Removed redirection from: " + url + " to: " + ret.url)

    # Return the URL that the page was downloaded from
    return ret.url


def _remove_trackers_query(query_str):
    """
    private function
    Given a query string from a URL, strip out the known trackers
    :param query_str: query to be cleaned
    :return: query cleaned
    """
    # Avalaible URL tracking parameters :
    # UTM tags by Google Ads, M$ Ads, ...
    # tag by TikTok
    # tags by Snapchat
    # tags by Facebook
    params_to_remove = {
        "gclid", "_ga", "gclsrc", "dclid",
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_cid",
        "utm_reader", "utm_name", "utm_referrer", "utm_social", "utm_social-type", "utm_brand"
        "mkt_tok",
        "campaign_name", "ad_set_name", "campaign_id", "ad_set_id",
        "fbclid", "campaign_name", "ad_set_name", "ad_set_id", "media", "interest_group_name", "ad_set_id"
        "igshid",
        "cvid", "oicd", "msclkid",
        "soc_src", "soc_trk",
        "_openstat", "yclid",
        "xtor", "xtref", "adid",
    }
    query_to_clean = dict(parse_qsl(query_str, keep_blank_values=True))
    query_cleaned = [(k, v) for k, v in query_to_clean.items()
                     if k not in params_to_remove]
    return urlencode(query_cleaned, doseq=True)


def _remove_trackers_fragment(fragment_str):
    """
    private function
    Given a fragment string from a URL, strip out the known trackers
    :param query_str: fragment to be cleaned
    :return: cleaned fragment
    """
    params_to_remove = {
        "Echobox",
    }

    if '=' in fragment_str:
        fragment_str = fragment_str.split('&')
        query_cleaned = [i for i in fragment_str if i.split(
            '=')[0] not in params_to_remove]
        fragment_str = '&'.join(query_cleaned)
    return fragment_str


def substitute_source(orig_url):
    """
    param orig_url: url to check for substitutes
    :return: url with replaced domains
    """
    parsed_url = urlparse(orig_url)
    domain = parsed_url.netloc

    logging.debug("Checking domain %s for substitution ", domain)

    # Handle twitter
    twitter_subst = TOML["options"]["subst_twitter"]
    # Do not substitiute if subdomain is present (e.g. i.twitter.com)
    if (domain == 'twitter.com' or domain == 'www.twitter.com') and twitter_subst != []:
        domain = twitter_subst[random.randint(0, len(twitter_subst) - 1)]
        logging.debug("Replaced twitter.com by " + domain)

    # Handle youtube
    youtube_subst = TOML["options"]["subst_youtube"]
    # Do not substitiute if subdomain is present (e.g. i.youtube.com)
    if (domain == 'youtube.com' or domain == 'wwww.youtube.com') and youtube_subst != []:
        domain = youtube_subst[random.randint(0, len(youtube_subst) - 1)]
        logging.debug("Replaced youtube.com by " + domain)

    # Handle reddit
    reddit_subst = TOML["options"]["subst_reddit"]
    # Do not substitiute if subdomain is present (e.g. i.reddit.com)
    if (domain == 'reddit.com' or domain == 'www.reddit.com') and reddit_subst != []:
        domain = reddit_subst[random.randint(0, len(reddit_subst) - 1)]
        logging.debug("Replaced reddit.com by " + domain)

    dest_url = urlunparse([
        parsed_url.scheme,
        domain,
        parsed_url.path,
        parsed_url.params,
        parsed_url.query,
        parsed_url.fragment
    ])

    return dest_url


def clean_url(orig_url):
    """
    Given a URL, return it with the UTM parameters removed from query and fragment
    :param dirty_url: url to be cleaned
    :return: url cleaned
    >>> clean_url('https://example.com/video/this-aerial-ropeway?utm_source=Twitter&utm_medium=video&utm_campaign=organic&utm_content=Nov13&a=aaa&b=1#mkt_tok=tik&mkt_tik=tok')
    'https://example.com/video/this-aerial-ropeway?a=aaa&b=1#mkt_tik=tok'
    """
    # Check if we have to do anything
    if TOML['options']['remove_trackers_from_urls'] is False:
        return orig_url

    # Parse a URL into 6 components:
    # <scheme>://<netloc>/<path>;<params>?<query>#<fragment>
    url_parsed = urlparse(orig_url)

    # Reassemble URL after removal of trackers
    dest_url = urlunparse([
        url_parsed.scheme,
        url_parsed.netloc,
        url_parsed.path,
        url_parsed.params,
        _remove_trackers_query(url_parsed.query),
        _remove_trackers_fragment(url_parsed.fragment)
    ])
    if dest_url != orig_url:
        logging.debug('Cleaned URL from: ' + orig_url + ' to: ' + dest_url)

    return dest_url


def process_media_body(tt_iter):
    """
    Receives an iterator over all the elements contained in the tweet-text container.
    Processes them to make them suitable for posting on Mastodon
    :param tt_iter: iterator over the HTML elements in the text of the tweet
    :return:        cleaned up text of the tweet
    """

    tweet_text = ''
    # Iterate elements
    for tag in tt_iter:
        # If element is plain text, copy it verbatim
        if isinstance(tag, element.NavigableString):
            tweet_text += tag.string

        # If it is an 'a' html tag
        elif tag.name == 'a':
            tag_text = tag.get_text()
            if tag_text.startswith('@'):
                # Only keep user name
                tweet_text += tag_text
            elif tag_text.startswith('#'):
                # Only keep hashtag text
                tweet_text += tag_text
            else:
                # This is a real link
                url = deredir_url(tag.get('href'))
                url = substitute_source(url)
                url = clean_url(url)

                tweet_text += url
        else:
            logging.warning(
                "No handler for tag in twitter text: " + tag.prettify())

    return tweet_text


def process_card(nitter_url, card_container):
    """
    Extract image from card in case mastodon does not do it
    :param card_container: soup of 'a' tag containing card markup
    :return: list with url of image
    """
    list = []

    img = card_container.div.div.img
    if img is not None:
        image_url = nitter_url + img.get('src')
        list.append(image_url)
        logging.debug('Extracted image from card')

    return list


def process_attachments(nitter_url, attachments_container, status_id, author_account):
    """
    Extract images or video from attachments. Videos are downloaded on the file system.
    :param nitter_url: url of nitter mirror
    :param attachments_container: soup of 'div' tag containing attachments markup
    :param twit_account: name of twitter account
    :param status_id: id of tweet being processed
    :param author_account: author of tweet with video attachment
    :return: list with url of images
    """
    # Collect url of images
    pics = []
    images = attachments_container.find_all('a', class_='still-image')
    for image in images:
        pics.append(nitter_url + image.get('href'))

    logging.debug('collected ' + str(len(pics)) + ' image(s) from attachments')

    # Download nitter video (converted animated GIF)
    gif_class = attachments_container.find('video', class_='gif')
    if gif_class is not None:
        gif_video_file = nitter_url + gif_class.source.get('src')

        video_path = os.path.join(
            'output', status_id, author_account, status_id)
        os.makedirs(video_path, exist_ok=True)

        # Open directory for writing file
        orig_dir = os.getcwd()
        os.chdir(video_path)
        with requests.get(gif_video_file, stream=True, timeout=HTTPS_REQ_TIMEOUT) as r:
            try:
                # Raise exception if response code is not 200
                r.raise_for_status()
                # Download chunks and write them to file
                with open('gif_video.mp4', 'wb') as f:
                    for chunk in r.iter_content(chunk_size=16 * 1024):
                        f.write(chunk)

                logging.debug(
                    'Downloaded video of GIF animation from attachments')
            except:  # Don't do anything if video can't be found or downloaded
                logging.debug(
                    'Could not download video of GIF animation from attachments')
                pass

        # Close directory
        os.chdir(orig_dir)

    # Download twitter video
    vid_in_tweet = False
    vid_class = attachments_container.find('div', class_='video-container')
    if vid_class is not None:
        if TOML['options']['upload_videos']:
            videos = vid_class.find_all('video')

            out_video = "output/" + status_id
            if len(videos) != 0:
                os.makedirs(out_video, exist_ok=True)
                vid_in_tweet = True

            i = 0
            for video in videos:
                video_url = video.find('source').get('src')
                video_out_path = out_video + "/" + str(i) + ".mp4"

                with requests.get(video_url, stream=True, timeout=HTTPS_REQ_TIMEOUT) as r:
                    try:
                        # Raise exception if response code is not 200
                        r.raise_for_status()
                        # Download chunks and write them to file
                        with open(video_out_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=16 * 1024):
                                f.write(chunk)

                        logging.debug('Downloaded video from attachments')
                    except:  # Don't do anything if video can't be found or downloaded
                        logging.error('Could not download video from attachments')
                        exit(0)

                i += 1

    return pics, vid_in_tweet


def contains_class(body_classes, some_class):
    """
    :param body_classes: list of classes to search
    :param some_class: class that we are interested in
    :return: True if found, false otherwise
    """
    found = False
    for body_class in body_classes:
        if body_class == some_class:
            found = True

    return found


def login(password):
    """
    Login to Mastodon account and return mastodon object used to post content
    :param password: Password associated to account. None if not provided
    :return: mastodon object
    """
# Create Mastodon application if it does not exist yet
    if not os.path.isfile(TOML['config']['mastodon_instance'] + '.secret'):
        try:
            Mastodon.create_app(
                'feedtoot',
                api_base_url='https://' + TOML['config']['mastodon_instance'],
                to_file=TOML['config']['mastodon_instance'] + '.secret'
            )

        except MastodonError as me:
            logging.fatal('failed to create app on ' +
                          TOML['config']['mastodon_instance'])
            logging.fatal(me)
            terminate(-1)

    mastodon = None

    # Log in to Mastodon instance with password
    if password is not None:
        try:
            mastodon = Mastodon(
                client_id=TOML['config']['mastodon_instance'] + '.secret',
                api_base_url='https://' + TOML['config']['mastodon_instance']
            )

            mastodon.log_in(
                username=TOML['config']['mastodon_user'],
                password=password,
                to_file=TOML['config']['mastodon_user'] + ".secret"
            )
            logging.info('Logging in to ' +
                         TOML['config']['mastodon_instance'])

        except MastodonError as me:
            logging.fatal(
                'Login to ' + TOML['config']['mastodon_instance'] + ' Failed\n')
            logging.fatal(me)
            terminate(-1)

        if os.path.isfile(TOML['config']['mastodon_user'] + '.secret'):
            logging.warning('You successfully logged in using a password and an access token \
                            has been saved. The password can therefore be omitted from the \
                            command-line in future invocations')
    else:  # No password provided, login with token
        # Using token in existing .secret file
        if os.path.isfile(TOML['config']['mastodon_user'] + '.secret'):
            try:
                mastodon = Mastodon(
                    access_token=TOML['config']['mastodon_user'] + '.secret',
                    api_base_url='https://' +
                    TOML['config']['mastodon_instance']
                )

            except MastodonError as me:
                logging.fatal(
                    'Login to ' + TOML['config']['mastodon_instance'] + ' Failed\n')
                logging.fatal(me)
                terminate(-1)
        else:
            logging.fatal('No .secret file found. Password required to log in')
            terminate(-1)

    return mastodon


def terminate(exit_code):
    """
    Cleanly stop execution with a message on execution duration
    Remove log messages older that duration specified in config from log file
    :param exit_code: return value to pass to shell when exiting
    """
    logging.info('Run time : {t:2.1f} seconds.'.format(
        t=time.time() - START_TIME))
    logging.info(
        '_____________________________________________________________________________________')

    # Close logger and log file
    logging.shutdown()

    # Remove older log messages
    # Max allowed age of log message
    max_delta = timedelta(TOML['options']['log_days'])

    # Open log file
    log_file_name = 'twoot.log'
    new_log_file_name = 'twoot.log.new'
    try:
        log_file = open(log_file_name, 'r')
    except FileNotFoundError:
        # Nothing to do if there is no log file
        exit(exit_code)

    # Check each line
    pos = log_file.tell()
    while True:
        line = log_file.readline()
        # Check if we reached the end of the file
        if not line:
            exit(exit_code)

        try:
            # Extract date on log line
            date = datetime.strptime(line[:10], '%Y-%m-%d')
        except ValueError:
            # date was not found on this line, try next one
            continue

        # Time difference between log message and now
        log_delta = datetime.now() - date
        # Only keep the number of days of the difference
        log_delta = timedelta(days=log_delta.days)
        if log_delta < max_delta:
            logging.debug("Truncating log file")
            # Reset file pointer to position before reading last line
            log_file.seek(pos)
            remainder = log_file.read()
            output_file = open(new_log_file_name, 'w')
            output_file.write(remainder)
            output_file.close()
            # replace log file by new one
            shutil.move(new_log_file_name, log_file_name)

            break  # Exit while loop

        # Update read pointer position
        pos = log_file.tell()

    exit(exit_code)


def basic_auth(username, password):
    token = b64encode(f"{username}:{password}".encode('utf-8')).decode("ascii")
    return f'Basic {token}'

def main(argv):
    # Start stopwatch
    global START_TIME
    START_TIME = time.time()

    # Build parser for command line arguments
    parser = argparse.ArgumentParser(description='toot tweets.')
    parser.add_argument('-f', metavar='<.toml config file>', action='store')
    parser.add_argument('-t', metavar='<twitter status>', action='store')
    parser.add_argument('-i', metavar='<mastodon instance>', action='store')
    parser.add_argument('-m', metavar='<mastodon account>', action='store')
    parser.add_argument('-p', metavar='<mastodon password>', action='store')
    parser.add_argument('-l', action='store_true',
                        help='Remove link redirection')
    parser.add_argument('-u', action='store_true',
                        help='Remove trackers from URLs')
    parser.add_argument('-v', action='store_true',
                        help='Ingest twitter videos and upload to Mastodon instance')
    parser.add_argument('-o', action='store_true',
                        help='Do not add reference to Original tweet')
    parser.add_argument('-j', metavar='<json export path>', action='store')

    # Parse command line
    args = vars(parser.parse_args())

    build_config(args)

    mast_password = args['p']

    # Setup logging to file
    logging.basicConfig(
        filename='twoot.log',
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # log level as an uppercase string from config
    ll_str = TOML['options']['log_level'].upper()

    if ll_str == "DEBUG":
        log_level = logging.DEBUG
    elif ll_str == "INFO":
        log_level = logging.INFO
    elif ll_str == "WARNING":
        log_level = logging.WARNING
    elif ll_str == "ERROR":
        log_level = logging.ERROR
    elif ll_str == "CRITICAL":
        log_level == logging.CRITICAL
    elif ll_str == "OFF":
        # Disable all logging
        logging.disable(logging.CRITICAL)
    else:
        logging.error('Invalid log_level %s in config file. Using WARNING.', str(
            TOML['options']['log_level']))

    # Set desired level of logging
    logger = logging.getLogger()
    logger.setLevel(log_level)

    logging.info('Running with the following configuration:')
    logging.info('  Config File              : ' + str(args['f']))
    logging.info('  twitter_status          : ' +
                 TOML['config']['twitter_status'])

    if 'mastodon_instance' in TOML['config'].keys():
        logging.info('  mastodon_instance        : ' +
                     TOML['config']['mastodon_instance'])

    if 'mastodon_user' in TOML['config'].keys():
        logging.info('  mastodon_user            : ' +
                     TOML['config']['mastodon_user'])

    logging.info('  upload_videos            : ' +
                 str(TOML['options']['upload_videos']))
    logging.info('  remove_link_redirections : ' +
                 str(TOML['options']['remove_link_redirections']))
    logging.info('  remove_trackers_from_urls: ' +
                 str(TOML['options']['remove_trackers_from_urls']))
    logging.info('  footer                   : ' + TOML['options']['footer'])
    logging.info('  remove_original_tweet_ref: ' +
                 str(TOML['options']['remove_original_tweet_ref']))
    logging.info('  subst_twitter            : ' +
                 str(TOML['options']['subst_twitter']))
    logging.info('  subst_twitter            : ' +
                 str(TOML['options']['subst_youtube']))
    logging.info('  subst_twitter            : ' +
                 str(TOML['options']['subst_reddit']))
    logging.info('  log_level                : ' +
                 str(TOML['options']['log_level']))
    logging.info('  log_days                 : ' +
                 str(TOML['options']['log_days']))
    logging.info('  export_json_path                 : ' +
                 str(TOML['options']['export_json_path']))

    # Select random nitter instance to fetch updates from
    nitter_url = NITTER_URLS[random.randint(0, len(NITTER_URLS) - 1)]

    # **********************************************************
    # Load twitter page of user. Process all tweets and generate
    # list of dictionaries ready to be posted on Mastodon
    # **********************************************************
    # To store content of all tweets from this user
    tweets = []

    # Initiate session
    session = requests.Session()

    # Get a copy of the default headers that requests would use
    headers = requests.utils.default_headers()

    # Update default headers with randomly selected user agent
    headers.update(
        {
            'User-Agent': USER_AGENTS[random.randint(0, len(USER_AGENTS) - 1)],
            'Cookie': 'replaceTwitter=; replaceYouTube=; hlsPlayback=on; proxyVideos='
        }
    )

    if USE_AUTH:
        headers.update({'Authorization' : basic_auth("root", "hunter2")})

    url = clean_url(TOML['config']['twitter_status'])

    status_id = url.split("/")[-1].split("?")[0]
    status_author = url.split("x.com/")[-1].split("/")[0]

    logging.debug('processing tweet %s', status_id)

    url = nitter_url + '/' + status_author + '/status/' + status_id

    # Download twitter page
    try:
        twit_page = session.get(
            url, headers=headers, timeout=HTTPS_REQ_TIMEOUT)
    except requests.exceptions.ConnectionError:
        logging.fatal('Host did not respond when trying to download ' + url)
        terminate(-1)
    except requests.exceptions.Timeout:
        logging.fatal(nitter_url + ' took too long to respond')
        terminate(-1)

    # Verify that download worked
    if twit_page.status_code != 200:
        logging.fatal('The Nitter page did not download correctly from ' + url + ' (' + str(
            twit_page.status_code) + '). Aborting')
        terminate(-1)

    logging.debug('Nitter page downloaded successfully from ' + url)

    # DEBUG: Save page to file
    # of = open(toml['config']['twitter_account'] + '.html', 'w')
    # of.write(twit_page.text)
    # of.close()

    # Make soup
    soup = BeautifulSoup(twit_page.text, 'html.parser')

    # Replace twitter_account with version with correct capitalization
    # ta = soup.find('meta', property='og:title').get('content')
    # ta_match = re.search(r'\(@(.+)\)', ta)
    # if ta_match is not None:
    #     TOML['config']['twitter_account'] = ta_match.group(1)

    # Extract twitter post
    status = soup.body.find("div", attrs={
                            'class': 'main-tweet'}).find("div", attrs={'class': 'timeline-item'})

    # **********************************************************
    # Process each tweet and generate dictionary
    # with data ready to be posted on Mastodon
    # **********************************************************

    # Extract time stamp
    time_string = status.find('span', class_='tweet-date').a.get('title')
    try:
        timestamp = datetime.strptime(
            time_string, '%d/%m/%Y, %H:%M:%S').timestamp()
    except:
        # Dec 21, 2021 · 12:00 PM UTC
        timestamp = datetime.strptime(
            time_string, '%b %d, %Y · %I:%M %p %Z').timestamp()

    # extract author
    author = status.find('a', class_='fullname').get('title')

    # Extract user name
    author_account = status_author

    # Extract URL of full status page (for video download)
    full_status_url = clean_url(TOML['config']['twitter_status'])

    # Initialize containers
    tweet_text = ''
    photos = []

    # Add prefix if the tweet is a reply-to
    # Only consider item of class 'replying-to' that is a direct child
    # of class 'tweet-body' in status. Others can be in a quoted tweet.
    #replying_to_class = status.select("div.tweet-body > div.replying-to")
    # if len(replying_to_class) != 0:
    #    tweet_text += 'Replying to ' + \
    #        replying_to_class[0].a.get_text() + '\n\n'

    # extract iterator over tweet text contents
    tt_iter = status.find(
        'div', class_='tweet-content media-body').children

    # Process text of tweet
    tweet_text += process_media_body(tt_iter)

    # Process quote: append link to tweet_text
    quote_div = status.find('a', class_='quote-link')
    if quote_div is not None:
        tweet_text += "\n\nRE: " + substitute_source('\n\nhttps://x.com' +
                                        quote_div.get('href').strip('#m'))
    # Process card : extract image if necessary
    card_class = status.find('a', class_='card-container')
    if card_class is not None:
        photos.extend(process_card(nitter_url, card_class))

    # Process attachment: capture image or .mp4 url or download twitter video
    attachments_class = status.find('div', class_='attachments')
    if attachments_class is not None:
        pics, vid_in_tweet = process_attachments(nitter_url,
                                                 attachments_class,
                                                 status_id, author_account
                                                 )
        photos.extend(pics)

    # Add custom footer from config file
    if TOML['options']['footer'] != '':
        tweet_text += '\n\n' + TOML['options']['footer']

    # Add footer with link to original tweet
    if TOML['options']['remove_original_tweet_ref'] == False:
        if TOML['options']['footer'] != '':
            tweet_text += '\nOriginal tweet: ' + \
                substitute_source(full_status_url)
        else:
            tweet_text += '\n\nOriginal tweet: ' + \
                substitute_source(full_status_url)

    # If no media was specifically added in the tweet, try to get the first picture
    # with "twitter:image" meta tag in first linked page in tweet text
    if not photos:
        m = re.search(r"http[^ \n\xa0]*", tweet_text)
        if m is not None:
            link_url = m.group(0)
            if link_url.endswith(".html"):  # Only process a web page
                try:
                    r = requests.get(link_url, timeout=HTTPS_REQ_TIMEOUT)
                    if r.status_code == 200:
                        # Matches the first instance of either twitter:image or twitter:image:src meta tag
                        match = re.search(
                            r'<meta name="twitter:image(?:|:src)" content="(.+?)".*?>', r.text)
                        if match is not None:
                            # Remove HTML-safe encoding from URL if any
                            url = match.group(1).replace('&amp;', '&')
                            photos.append(url)
                # Give up if anything goes wrong
                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.TooManyRedirects,
                        requests.exceptions.MissingSchema):
                    pass
                else:
                    logging.debug(
                        "downloaded twitter:image from linked page")

    # Check if video was downloaded
    video_file = []

    video_path = Path('./output') / status_id
    if video_path.exists():
        # list video files
        video_file_list = list(video_path.glob('*.mp4'))
        for video in video_file_list:
            video_file.append(video.absolute().as_posix())

    # Add dictionary with content of tweet to list
    tweet = {
        "author": author,
        "author_account": author_account,
        "timestamp": timestamp,
        "tweet_id": status_id,
        "tweet_text": tweet_text,
        "video": video_file,
        "photos": photos,
    }

    if 'export_json_path' in TOML['options'].keys():
        import json

        jsonpath = TOML['options']['export_json_path']
        with open(jsonpath, "w", encoding='utf-8') as jsonfile:
            json.dump(tweet, jsonfile, indent=2, ensure_ascii=False)

        logging.info('Exported Tweet JSON data to ' + jsonpath)
        exit(0)

    # Login to account on maston instance
    mastodon = login(mast_password)

    # **********************************************************
    # Post tweet on Mastodon
    # **********************************************************

    logging.debug('Uploading Tweet %s', tweet["tweet_id"])

    media_ids = []

    # Upload video if there is one
    if tweet['video'] is not None:
        try:
            logging.debug("Uploading video to Mastodon")
            media_posted = mastodon.media_post(tweet['video'])
            media_ids.append(media_posted['id'])
        except (MastodonAPIError, MastodonIllegalArgumentError,
                TypeError):  # Media cannot be uploaded (invalid format, dead link, etc.)
            logging.debug("Uploading video failed")
            pass

    else:  # Only upload pic if no video was uploaded
        # Upload photos
        for photo in tweet['photos']:
            media = False
            # Download picture
            try:
                logging.debug('downloading picture')
                media = requests.get(photo, timeout=HTTPS_REQ_TIMEOUT)
            except:  # Picture cannot be downloaded for any reason
                pass

            # Upload picture to Mastodon instance
            if media:
                try:
                    logging.debug('uploading picture to Mastodon')
                    media_posted = mastodon.media_post(
                        media.content, mime_type=media.headers['content-type'])
                    media_ids.append(media_posted['id'])
                except (MastodonAPIError, MastodonIllegalArgumentError,
                        TypeError):  # Media cannot be uploaded (invalid format, dead link, etc.)
                    pass

    # Post toot
    toot = {}
    try:
        if len(media_ids) == 0:
            toot = mastodon.status_post(tweet['tweet_text'])
        else:
            toot = mastodon.status_post(
                tweet['tweet_text'], media_ids=media_ids)

    except MastodonAPIError:
        # Assuming this is an:
        # ERROR ('Mastodon API returned error', 422, 'Unprocessable Entity', 'Cannot attach files that have not finished processing. Try again in a moment!')
        logging.warning(
            'Mastodon API Error 422: Cannot attach files that have not finished processing. Waiting 15 seconds and retrying.')
        # Wait 15 seconds
        time.sleep(15)
        # retry posting
        try:
            toot = mastodon.status_post(
                tweet['tweet_text'], media_ids=media_ids)
        except MastodonError as me:
            logging.error(
                'posting ' + tweet['tweet_text'] + ' to ' + TOML['config']['mastodon_instance'] + ' Failed')
            logging.error(me)

    except MastodonError as me:
        logging.error('posting ' + tweet['tweet_text'] + ' to ' +
                      TOML['config']['mastodon_instance'] + ' Failed')
        logging.error(me)

    else:
        logging.debug('Tweet %s posted on %s',
                      tweet['tweet_id'], TOML['config']['mastodon_user'])

    # Cleanup downloaded video files
    try:
        shutil.rmtree('./output')
    except FileNotFoundError:  # The directory does not exist
        pass

    terminate(0)


if __name__ == "__main__":
    main(sys.argv)
