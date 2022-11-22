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
import datetime
import logging
import os
import random
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup, element
from mastodon import Mastodon, MastodonError, MastodonAPIError, MastodonIllegalArgumentError

# Number of records to keep in db table for each twitter account
MAX_REC_COUNT = 50

# Set the desired verbosity of logging
# One of logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL
LOGGING_LEVEL = logging.DEBUG

# How many seconds to wait before giving up on a download (except video download)
HTTPS_REQ_TIMEOUT = 10

NITTER_URLS = [
    'https://nitter.lacontrevoie.fr',
    'https://nitter.pussthecat.org',
    'https://nitter.fdn.fr',
    'https://nitter.eu',
    'https://nitter.namazso.eu',
    'https://n.l5.ca',
    'https://nitter.bus-hit.me',
]

# Update from https://www.whatismybrowser.com/guides/the-latest-user-agent/
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.42',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Vivaldi/5.4.2753.51',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Vivaldi/5.4.2753.51',
]

def deredir_url(url):
    """
    Given a URL, return the URL that the page really downloads from
    :param url: url to be de-redirected
    :return: direct url
    """

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
        ret = requests.get(url, headers=headers, timeout=5)
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
    params_to_remove = [
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "mkt_tok",
        "campaign_name", "ad_set_name", "campaign_id", "ad_set_id",
        "media", "interest_group_name",
        "xtor"
    ]
    query_to_clean = dict(parse_qsl(query_str, keep_blank_values=True))
    query_cleaned = [(k, v) for k, v in query_to_clean.items() if not k in params_to_remove]
    return urlencode(query_cleaned, doseq=True)


def _remove_trackers_fragment(fragment_str):
    """
    private function
    Given a fragment string from a URL, strip out the known trackers
    :param query_str: fragment to be cleaned
    :return: cleaned fragment
    """
 
    # Not implemented
    # Unclear what, if anything, can be done
    # Need better understanding of fragment-based tracking
    # https://builtvisible.com/one-weird-trick-to-avoid-utm-parameters/

    return fragment_str


def clean_url(dirty_url):
    """
    Given a URL, return it with the UTM parameters removed from query and fragment
    :param dirty_url: url to be cleaned
    :return: url cleaned
    >>> clean_url('https://example.com/video/this-aerial-ropeway?utm_source=Twitter&utm_medium=video&utm_campaign=organic&utm_content=Nov13&a=aaa&b=1#mkt_tok=tik&mkt_tik=tok')
    'https://example.com/video/this-aerial-ropeway?a=aaa&b=1#mkt_tik=tok'
    """

    url_parsed = urlparse(dirty_url)

    cleaned_url = urlunparse([
        url_parsed.scheme,
        url_parsed.netloc,
        url_parsed.path,
        url_parsed.params,
        _remove_trackers_query(url_parsed.query),
        _remove_trackers_fragment(url_parsed.fragment)
    ])

    if cleaned_url != dirty_url:
        logging.debug('Cleaned URL from: ' + dirty_url + ' to: ' + cleaned_url)

    return cleaned_url


def process_media_body(tt_iter, remove_trackers):
    """
    Receives an iterator over all the elements contained in the tweet-text container.
    Processes them to make them suitable for posting on Mastodon
    :param tt_iter: iterator over the HTML elements in the text of the tweet
    :param remove_trackers: bool to indicate if trackers should be removed
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
                if remove_trackers:
                    tweet_text += clean_url(url)
                else:
                    tweet_text += url
        else:
            logging.warning("No handler for tag in twitter text: " + tag.prettify())

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


def process_attachments(nitter_url, attachments_container, get_vids, twit_account, status_id, author_account):
    """
    Extract images or video from attachments. Videos are downloaded on the file system.
    :param nitter_url: url of nitter mirror
    :param attachments_container: soup of 'div' tag containing attachments markup
    :param get_vids: whether to download videos or not
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

    logging.debug('collected ' + str(len(pics)) + ' images from attachments')

    # Download nitter video (converted animated GIF)
    gif_class = attachments_container.find('video', class_='gif')
    if gif_class is not None:
        gif_video_file = nitter_url + gif_class.source.get('src')

        video_path = os.path.join('output', twit_account, status_id, author_account, status_id)
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

                logging.debug('Downloaded video of GIF animation from attachments')
            except:  # Don't do anything if video can't be found or downloaded
                logging.debug('Could not download video of GIF animation from attachments')
                pass

        # Close directory
        os.chdir(orig_dir)

    # Download twitter video
    vid_in_tweet = False
    vid_class = attachments_container.find('div', class_='video-container')
    if vid_class is not None:
        if get_vids:
            import youtube_dl

            video_file = os.path.join('https://twitter.com', author_account, 'status', status_id)
            ydl_opts = {
                'outtmpl': "output/" + twit_account + "/" + status_id + "/%(id)s.%(ext)s",
                'format': "best[width<=500]",
                'socket_timeout': 60,
                'quiet': True,
            }

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([video_file])
                except Exception as e:
                    logging.warn('Error downloading twitter video: ' + str(e))
                    vid_in_tweet = True
                else:
                    logging.debug('downloaded twitter video from attachments')

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


def is_time_valid(timestamp, max_age, min_delay):
    ret = True
    # Check that the tweet is not too young (might be deleted) or too old
    age_in_hours = (time.time() - float(timestamp)) / 3600.0
    min_delay_in_hours = min_delay / 60.0
    max_age_in_hours = max_age * 24.0

    if age_in_hours < min_delay_in_hours or age_in_hours > max_age_in_hours:
        ret = False

    return ret


def login(instance, account, password):
    # Create Mastodon application if it does not exist yet
    if not os.path.isfile(instance + '.secret'):
        try:
            Mastodon.create_app(
                'twoot',
                api_base_url='https://' + instance,
                to_file=instance + '.secret'
            )

        except MastodonError as me:
            logging.fatal('failed to create app on ' + instance)
            logging.fatal(me)
            sys.exit(-1)

    # Log in to Mastodon instance
    try:
        mastodon = Mastodon(
            client_id=instance + '.secret',
            api_base_url='https://' + instance
        )

        mastodon.log_in(
            username=account,
            password=password,
            to_file=account + ".secret"
        )
        logging.info('Logging in to ' + instance)

    except MastodonError as me:
        logging.fatal('ERROR: Login to ' + instance + ' Failed')
        logging.fatal(me)
        sys.exit(-1)

    # Check ratelimit status
    logging.debug('Ratelimit allowed requests: ' + str(mastodon.ratelimit_limit))
    logging.debug('Ratelimit remaining requests: ' + str(mastodon.ratelimit_remaining))
    logging.debug('Ratelimit reset time: ' + time.asctime(time.localtime(mastodon.ratelimit_reset)))
    logging.debug('Ratelimit last call: ' + time.asctime(time.localtime(mastodon.ratelimit_lastcall)))

    return mastodon


def main(argv):
    # Start stopwatch
    start_time = time.time()

    # Build parser for command line arguments
    parser = argparse.ArgumentParser(description='toot tweets.')
    parser.add_argument('-t', metavar='<twitter account>', action='store', required=True)
    parser.add_argument('-i', metavar='<mastodon instance>', action='store', required=True)
    parser.add_argument('-m', metavar='<mastodon account>', action='store', required=True)
    parser.add_argument('-p', metavar='<mastodon password>', action='store', required=True)
    parser.add_argument('-r', action='store_true', help='Also post replies to other tweets')
    parser.add_argument('-s', action='store_true', help='Suppress retweets')
    parser.add_argument('-u', action='store_true', help='Remove trackers from URLs')
    parser.add_argument('-v', action='store_true', help='Ingest twitter videos and upload to Mastodon instance')
    parser.add_argument('-a', metavar='<max age (in days)>', action='store', type=float, default=1)
    parser.add_argument('-d', metavar='<min delay (in mins)>', action='store', type=float, default=0)
    parser.add_argument('-c', metavar='<max # of toots to post>', action='store', type=int, default=0)

    # Parse command line
    args = vars(parser.parse_args())

    twit_account = args['t']
    mast_instance = args['i']
    mast_account = args['m']
    mast_password = args['p']
    tweets_and_replies = args['r']
    suppress_retweets = args['s']
    remove_trackers = args['u']
    get_vids = args['v']
    max_age = float(args['a'])
    min_delay = float(args['d'])
    cap = int(args['c'])

    # Remove previous log file
    # try:
    #    os.remove(twit_account + '.log')
    # except FileNotFoundError:
    #    pass

    # Setup logging to file
    logging.basicConfig(
        filename=twit_account + '.log',
        level=LOGGING_LEVEL,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    logging.info('Running with the following parameters:')
    logging.info('    -t ' + twit_account)
    logging.info('    -i ' + mast_instance)
    logging.info('    -m ' + mast_account)
    logging.info('    -r ' + str(tweets_and_replies))
    logging.info('    -s ' + str(suppress_retweets))
    logging.info('    -u ' + str(remove_trackers))
    logging.info('    -v ' + str(get_vids))
    logging.info('    -a ' + str(max_age))
    logging.info('    -d ' + str(min_delay))
    logging.info('    -c ' + str(cap))

    # Try to open database. If it does not exist, create it
    sql = sqlite3.connect('twoot.db')
    db = sql.cursor()
    db.execute('''CREATE TABLE IF NOT EXISTS toots (twitter_account TEXT, mastodon_instance TEXT,
               mastodon_account TEXT, tweet_id TEXT, toot_id TEXT)''')
    db.execute('''CREATE INDEX IF NOT EXISTS main_index ON toots (twitter_account,
               mastodon_instance, mastodon_account, tweet_id)''')

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
            'Cookie': 'replaceTwitter=; replaceYouTube=; hlsPlayback=on; proxyVideos=',
        }
    )

    url = nitter_url + '/' + twit_account
    # Use different page if we need to handle replies
    if tweets_and_replies:
        url += '/with_replies'

    # Download twitter page of user
    try:
        twit_account_page = session.get(url, headers=headers, timeout=HTTPS_REQ_TIMEOUT)
    except requests.exceptions.ConnectionError:
        logging.fatal('Host did not respond when trying to download ' + url)
        exit(-1)
    except requests.exceptions.Timeout:
        logging.fatal(nitter_url + ' took too long to respond')
        exit(-1)

    # Verify that download worked
    if twit_account_page.status_code != 200:
        logging.fatal('The Nitter page did not download correctly from ' + url + ' (' + str(
            twit_account_page.status_code) + '). Aborting')
        exit(-1)

    logging.info('Nitter page downloaded successfully from ' + url)

    # DEBUG: Save page to file
    # of = open(twit_account + '.html', 'w')
    # of.write(twit_account_page.text)
    # of.close()

    # Make soup
    soup = BeautifulSoup(twit_account_page.text, 'html.parser')

    # Replace twit_account with version with correct capitalization
    ta = soup.find('meta', property='og:title').get('content')
    ta_match = re.search(r'\(@(.+)\)', ta)
    if ta_match is not None:
        twit_account = ta_match.group(1)

    # Extract twitter timeline
    timeline = soup.find_all('div', class_='timeline-item')

    logging.info('Processing ' + str(len(timeline)) + ' tweets found in timeline')

    # **********************************************************
    # Process each tweets and generate dictionary
    # with data ready to be posted on Mastodon
    # **********************************************************
    out_date_cnt = 0
    in_db_cnt = 0
    for status in timeline:
        # Extract tweet ID and status ID
        tweet_id = status.find('a', class_='tweet-link').get('href').strip('#m')
        status_id = tweet_id.split('/')[3]

        logging.debug('processing tweet %s', tweet_id)

        # Extract time stamp
        time_string = status.find('span', class_='tweet-date').a.get('title')
        try:
            timestamp = datetime.datetime.strptime(time_string, '%d/%m/%Y, %H:%M:%S').timestamp()
        except:
            # Dec 21, 2021 · 12:00 PM UTC
            timestamp = datetime.datetime.strptime(time_string, '%b %d, %Y · %I:%M %p %Z').timestamp()

        # Check if time is within acceptable range
        if not is_time_valid(timestamp, max_age, min_delay):
            out_date_cnt += 1
            logging.debug("Tweet outside valid time range, skipping")
            continue

        # Check if retweets must be skipped
        if suppress_retweets:
            # Check if this tweet is a retweet
            if len(status.select("div.tweet-body > div > div.retweet-header")) != 0:
                logging.debug("Retweet ignored per command-line configuration")
                continue

        # Check in database if tweet has already been posted
        db.execute(
            "SELECT * FROM toots WHERE twitter_account=? AND mastodon_instance=? AND mastodon_account=? AND tweet_id=?",
            (twit_account, mast_instance, mast_account, tweet_id))
        tweet_in_db = db.fetchone()

        if tweet_in_db is not None:
            in_db_cnt += 1
            logging.debug("Tweet %s already in database", tweet_id)
            # Skip to next tweet
            continue
        else:
            logging.debug('Tweet %s not found in database', tweet_id)

        # extract author
        author = status.find('a', class_='fullname').get('title')

        # Extract user name
        author_account = status.find('a', class_='username').get('title').lstrip('@')

        # Extract URL of full status page (for video download)
        full_status_url = 'https://twitter.com' + tweet_id

        # Initialize containers
        tweet_text = ''
        photos = []

        # Add prefix if the tweet is a reply-to
        # Only consider item of class 'replying-to' that is a direct child
        # of class 'tweet-body' in status. Others can be in a quoted tweet.
        replying_to_class = status.select("div.tweet-body > div.replying-to")
        if len(replying_to_class) != 0:
            tweet_text += 'Replying to ' + replying_to_class[0].a.get_text() + '\n\n'

        # Check it the tweet is a retweet from somebody else
        if len(status.select("div.tweet-body > div > div.retweet-header")) != 0:
            tweet_text = 'RT from ' + author + ' (@' + author_account + ')\n\n'

        # extract iterator over tweet text contents
        tt_iter = status.find('div', class_='tweet-content media-body').children

        # Process text of tweet
        tweet_text += process_media_body(tt_iter, remove_trackers)

        # Process quote: append link to tweet_text
        quote_div = status.find('a', class_='quote-link')
        if quote_div is not None:
            tweet_text += '\n\nhttps://twitter.com' + quote_div.get('href').strip('#m')

        # Process card : extract image if necessary
        card_class = status.find('a', class_='card-container')
        if card_class is not None:
            photos.extend(process_card(nitter_url, card_class))

        # Process attachment: capture image or .mp4 url or download twitter video
        attachments_class = status.find('div', class_='attachments')
        if attachments_class is not None:
            pics, vid_in_tweet = process_attachments(nitter_url, attachments_class, get_vids, twit_account, status_id,
                                                     author_account)
            photos.extend(pics)
            if vid_in_tweet:
                tweet_text += '\n\n[Video embedded in original tweet]'

        # Add footer with link to original tweet
        tweet_text += '\n\nOriginal tweet : ' + full_status_url

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
                            match = re.search(r'<meta name="twitter:image(?:|:src)" content="(.+?)".*?>', r.text)
                            if match is not None:
                                url = match.group(1).replace('&amp;', '&')  # Remove HTML-safe encoding from URL if any
                                photos.append(url)
                    # Give up if anything goes wrong
                    except (requests.exceptions.ConnectionError,
                            requests.exceptions.Timeout,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.TooManyRedirects,
                            requests.exceptions.MissingSchema):
                        pass
                    else:
                        logging.debug("downloaded twitter:image from linked page")

        # Check if video was downloaded
        video_file = None

        video_path = Path('./output') / twit_account / status_id
        if video_path.exists():
            # list video files
            video_file_list = list(video_path.glob('*.mp4'))
            if len(video_file_list) != 0:
                # Extract posix path of first video file in list
                video_file = video_file_list[0].absolute().as_posix()

        # Add dictionary with content of tweet to list
        tweet = {
            "author": author,
            "author_account": author_account,
            "timestamp": timestamp,
            "tweet_id": tweet_id,
            "tweet_text": tweet_text,
            "video": video_file,
            "photos": photos,
        }
        tweets.append(tweet)

        logging.debug('Tweet %s added to list of toots to upload', tweet_id)

    # Log summary stats
    logging.info(str(out_date_cnt) + ' tweets outside of valid time range')
    logging.info(str(in_db_cnt) + ' tweets already in database')

    # DEBUG: Print extracted tweets
    # for t in tweets:
    # print(t)

    # Login to account on maston instance
    mastodon = None
    if len(tweets) != 0:
        mastodon = login(mast_instance, mast_account, mast_password)

    # **********************************************************
    # Iterate tweets in list.
    # post each on Mastodon and record it in database
    # **********************************************************

    posted_cnt = 0
    for tweet in reversed(tweets):
        # Check if we have reached the cap on the number of toots to post
        if cap != 0 and posted_cnt >= cap:
            logging.info('%d toots not posted due to configured cap', len(tweets) - cap)
            break

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
                        media_posted = mastodon.media_post(media.content, mime_type=media.headers['content-type'])
                        media_ids.append(media_posted['id'])
                    except (MastodonAPIError, MastodonIllegalArgumentError,
                            TypeError):  # Media cannot be uploaded (invalid format, dead link, etc.)
                        pass

        # Post toot
        toot = {}
        try:
            mastodon = Mastodon(
                access_token=mast_account + '.secret',
                api_base_url='https://' + mast_instance
            )

            if len(media_ids) == 0:
                toot = mastodon.status_post(tweet['tweet_text'], visibility='public')
            else:
                toot = mastodon.status_post(tweet['tweet_text'], media_ids=media_ids, visibility='public')

        except MastodonError as me:
            logging.error('posting ' + tweet['tweet_text'] + ' to ' + mast_instance + ' Failed')
            logging.error(me)

        else:
            posted_cnt += 1
            logging.debug('Tweet %s posted on %s', tweet['tweet_id'], mast_account)

        # Insert toot id into database
        if 'id' in toot:
            db.execute("INSERT INTO toots VALUES ( ? , ? , ? , ? , ? )",
                       (twit_account, mast_instance, mast_account, tweet['tweet_id'], toot['id']))
            sql.commit()

    logging.info(str(posted_cnt) + ' tweets posted to Mastodon')

    # Cleanup downloaded video files
    try:
        shutil.rmtree('./output/' + twit_account)
    except FileNotFoundError:  # The directory does not exist
        pass

    # Evaluate excess records in database
    excess_count = 0

    db.execute('SELECT count(*) FROM toots WHERE twitter_account=?', (twit_account,))
    db_count = db.fetchone()
    if db_count is not None:
        excess_count = db_count[0] - MAX_REC_COUNT

    # Delete excess records
    if excess_count > 0:
        db.execute('''
            WITH excess AS (
            SELECT tweet_id
            FROM toots
            WHERE twitter_account=?
            ORDER BY toot_id ASC
            LIMIT ?
            )
            DELETE from toots
            WHERE tweet_id IN excess''', (twit_account, excess_count))
        sql.commit()

        logging.info('Deleted ' + str(excess_count) + ' old records from database.')

    logging.info('Run time : %2.1f seconds' % (time.time() - start_time))
    logging.info('_____________________________________________________________________________________')


if __name__ == "__main__":
    main(sys.argv)
