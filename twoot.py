#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Copyright (C) 2019  Jean-Christophe Francois

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

import sys
import logging
import argparse
import os
import random
import requests
from bs4 import BeautifulSoup, element
import sqlite3
import datetime, time
import re
from pathlib import Path
from mastodon import Mastodon, MastodonError, MastodonAPIError, MastodonIllegalArgumentError
import subprocess
import shutil


# Update from https://www.whatismybrowser.com/guides/the-latest-user-agent/
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36 Edg/87.0.664.60',
    ]

# Setup logging to file
logging.basicConfig(filename="twoot.log", level=logging.INFO)
logging.info('*********** NEW RUN ***********')


def process_media_body(tt_iter):
    '''
    Receives an iterator over all the elements contained in the tweet-text container.
    Processes them to make them suitable for posting on Mastodon
    :param tt_iter: iterator over the HTML elements in the text of the tweet
    :return:        cleaned up text of the tweet
    '''
    tweet_text = ''
    # Iterate elements
    for tag in tt_iter:
        # If element is plain text, copy it verbatim
        if isinstance(tag, element.NavigableString):
            tweet_text += tag.string

        # If it is an 'a' html tag
        elif tag.name == 'a':
            tag_text = tag.get_text()
            if tag_text.starts_with('@'):
                # Only keep user name
                tweet_text += tag_text
            elif tag_text.starts_with('#'):
                # Only keep hashtag text
                tweet_text += tag_text
            else:
                # This is a real link, keep url
                tweet_text += tag.get('href')
        else:
            logging.warning("No handler for tag in twitter text: " + tag.prettify())

    return tweet_text


def contains_class(body_classes, some_class):
    '''
    :param body_classes: list of classes to search
    :param some_class: class that we are interested in
    :return: True if found, false otherwise
    '''
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


def main(argv):

    # Build parser for command line arguments
    parser = argparse.ArgumentParser(description='toot tweets.')
    parser.add_argument('-t', metavar='<twitter account>', action='store', required=True)
    parser.add_argument('-i', metavar='<mastodon instance>', action='store', required=True)
    parser.add_argument('-m', metavar='<mastodon account>', action='store', required=True)
    parser.add_argument('-p', metavar='<mastodon password>', action='store', required=True)
    parser.add_argument('-r', action='store_true', help='Also post replies to other tweets')
    parser.add_argument('-v', action='store_true', help='Ingest twitter videos and upload to Mastodon instance')
    parser.add_argument('-a', metavar='<max age (in days)>', action='store', type=float, default=1)
    parser.add_argument('-d', metavar='<min delay (in mins)>', action='store', type=float, default=0)

    # Parse command line
    args = vars(parser.parse_args())

    twit_account = args['t']
    mast_instance = args['i']
    mast_account = args['m']
    mast_password = args['p']
    tweets_and_replies = args['r']
    get_vids = args['v']
    max_age = float(args['a'])
    min_delay = float(args['d'])

    logging.info('Updating ' + twit_account + ' on ' + mast_instance)

    # Try to open database. If it does not exist, create it
    sql = sqlite3.connect('twoot.db')
    db = sql.cursor()
    db.execute('''CREATE TABLE IF NOT EXISTS toots (twitter_account TEXT, mastodon_instance TEXT,
               mastodon_account TEXT, tweet_id TEXT, toot_id TEXT)''')

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
            'User-Agent': USER_AGENTS[random.randint(0, len(USER_AGENTS)-1)],
            'Cookie': 'replaceTwitter=; replaceYouTube=',
        }
    )

    url = 'https://nitter.net/' + twit_account
    # Use different page if we need to handle replies
    if tweets_and_replies:
        url += '/with_replies'

    # Download twitter page of user.
    twit_account_page = session.get(url, headers=headers)

    # Verify that download worked
    assert twit_account_page.status_code == 200,\
        'The nitter page did not download correctly. Aborting'

    logging.info('Page downloaded successfully')

    # DEBUG: Save page to file
    of = open(twit_account + '.html', 'w')
    of.write(twit_account_page.text)
    of.close()

    # Make soup
    soup = BeautifulSoup(twit_account_page.text, 'html.parser')

    # Replace twit_account with version with correct capitalization
    ta = soup.find('meta', property='og:title').get('content')
    ta_match = re.search('\(@(.+)\)', ta)
    if ta_match is not None:
        twit_account = ta_match.group(1)

    # Extract twitter timeline
    timeline = soup.find_all('div', class_='timeline-item')

    logging.info('Processing ' + str(len(timeline)) + ' tweets found in timeline')

    # **********************************************************
    # Process each tweets and generate dictionary
    # with data ready to be posted on Mastodon
    # **********************************************************
    for status in timeline:
        # Extract tweet ID and status ID
        tweet_id = status.find('a', class_='tweet-link').get('href').strip('#m')
        status_id = tweet_id.split('/')[3]

        logging.debug('processing tweet %s', tweet_id)

        # Extract time stamp
        time_string = status.find('span', class_='tweet-date').a.get('title')
        timestamp = datetime.datetime.strptime(time_string, '%d/%m/%Y, %H:%M:%S').timestamp()

        # Check if time is within acceptable range
        if not is_time_valid(timestamp, max_age, min_delay):
            logging.debug("Tweet outside valid time range, skipping")
            continue

        # Check in database if tweet has already been posted
        db.execute("SELECT * FROM toots WHERE twitter_account=? AND mastodon_instance=? AND mastodon_account=? AND tweet_id=?",
                   (twit_account, mast_instance, mast_account, tweet_id))
        tweet_in_db = db.fetchone()

        if tweet_in_db is not None:
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

        # Initialize tweet text
        tweet_text = ''

        # Add prefix if the tweet is a reply-to
        replying_to_class = status.find('div', class_='replying-to')
        if replying_to_class is not None:
            tweet_text += 'Replying to ' + replying_to_class.a.get_text()

        # Check it the tweet is a retweet from somebody else
        if author_account.lower() != twit_account.lower():
            tweet_text = 'RT from ' + author + ' (@' + author_account + ')\n\n'

        # extract iterator over tweet text contents
        tt_iter = status.find('div', class_='tweet-content media-body').children

        tweet_text += process_media_body(tt_iter, twit_account, status_id, full_status_url, get_vids)

        # TODO  Process quote: append link to tweet_text

        # TODO  Process card : extract image or youtube link

        # TODO  Process attachment: capture image or .mp4 url or download twitter video

        # Add footer with link to original tweet
        tweet_text += '\n\nOriginal tweet : ' + full_status_url

        photos = []  # The no_js version of twitter only shows one photo

        # Check if there are photos attached
        media = status.find('div', class_='media')
        if media:
            # Extract photo url and add it to list
            pic = str(media.img['src']).strip(':small')
            photos.append(pic)

        # If no media was specifically added in the tweet, try to get the first picture
        # with "twitter:image" meta tag in first linked page in tweet text
        if not photos:
            m = re.search(r"http[^ \n\xa0]*", tweet_text)
            if m is not None:
                link_url = m.group(0)
                if link_url.endswith(".html"):  # Only process a web page
                    try:
                        r = requests.get(link_url, timeout=10)
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

        # Check if video was downloaded
        video_file = None

        video_path = Path('./output') / twit_account / status_id
        if video_path.exists():
            # Take the first subdirectory of video path (named after original poster of video)
            video_path = [p for p in video_path.iterdir() if p.is_dir()][0]
            # Take again the first subdirectory of video path (named after status id of original post where vidoe is attached)
            video_path = [p for p in video_path.iterdir() if p.is_dir()][0]
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

    # TODO  Log summary stats: how many not in db, how many in valid timeframe

    # DEBUG: Print extracted tweets
    #for t in tweets:
    #print(t)

    # **********************************************************
    # Iterate tweets in list.
    # post each on Mastodon and record it in database
    # **********************************************************

    # Create Mastodon application if it does not exist yet
    if not os.path.isfile(mast_instance + '.secret'):
        try:
            Mastodon.create_app(
                'twoot',
                api_base_url='https://' + mast_instance,
                to_file=mast_instance + '.secret'
            )

        except MastodonError as me:
            print('failed to create app on ' + mast_instance)
            sys.exit(1)

    # Log in to Mastodon instance
    try:
        mastodon = Mastodon(
            client_id=mast_instance + '.secret',
            api_base_url='https://' + mast_instance
        )

        mastodon.log_in(
            username=mast_account,
            password=mast_password,
            to_file=mast_account + ".secret"
        )

    except MastodonError as me:
        logging.fatal('ERROR: Login to ' + mast_instance + ' Failed\n' + me)
        sys.exit(1)

    # Upload tweets
    for tweet in reversed(tweets):
        logging.debug('Uploading Tweet %s', tweet["tweet_id"])

        media_ids = []

        # Upload video if there is one
        if tweet['video'] is not None:
            try:
                logging.debug("Uploading video")
                media_posted = mastodon.media_post(tweet['video'])
                media_ids.append(media_posted['id'])
            except (MastodonAPIError, MastodonIllegalArgumentError, TypeError):  # Media cannot be uploaded (invalid format, dead link, etc.)
                logging.debug("Uploading video failed")
                pass

        else:  # Only upload pic if no video was uploaded
            # Upload photos
            for photo in tweet['photos']:
                media = False
                # Download picture
                try:
                    media = requests.get(photo)
                except:  # Picture cannot be downloaded for any reason
                    pass

                # Upload picture to Mastodon instance
                if media:
                    try:
                        media_posted = mastodon.media_post(media.content, mime_type=media.headers['content-type'])
                        media_ids.append(media_posted['id'])
                    except (MastodonAPIError, MastodonIllegalArgumentError, TypeError):  # Media cannot be uploaded (invalid format, dead link, etc.)
                        pass

        # Post toot
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
            sys.exit(1)

        logging.debug('Tweet %s posted on %s', tweet_id, mast_account)

        # Insert toot id into database
        if 'id' in toot:
            db.execute("INSERT INTO toots VALUES ( ? , ? , ? , ? , ? )",
                       (twit_account, mast_instance, mast_account, tweet['tweet_id'], toot['id']))
            sql.commit()

    # Cleanup downloaded video files
    try:
        shutil.rmtree('./output/' + twit_account)
    except FileNotFoundError:  # The directory does not exist
        pass


if __name__ == "__main__":
    main(sys.argv)
