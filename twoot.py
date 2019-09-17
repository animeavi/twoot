#! /usr/bin/env python3
# -*- coding: utf-8 -*-

'''
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
'''

import sys
import argparse
import os
import random
import requests
from bs4 import BeautifulSoup, element
import sqlite3
import time
import re
from mastodon import Mastodon, MastodonError, MastodonAPIError, MastodonIllegalArgumentError


USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.87 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/68.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.2 Safari/605.1.15',
    'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.87 Safari/537.36 Edg/44.18362.267.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.87 Safari/537.36 OPR/62.0.3331.99',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.87 Safari/537.36 Vivaldi/2.6.1566.40',
    'Mozilla/5.0 (Windows NT 6.3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.87 YaBrowser/19.6.2.503 Yowser/2.5 Safari/537.36'
    ]

#TODO log to file


def cleanup_tweet_text(tt_iter):
    '''
    Receives an iterator over all the elements contained in the tweet-text container
    and processes them to remove Twitter-specific stuff and make them suitable for
    posting on Mastodon
    '''
    tweet_text = ''
    # Iterate elements
    for tag in tt_iter:
        # If element is plain text, copy it verbatim
        if isinstance(tag, element.NavigableString):
            tweet_text += tag.string

        # If it is an 'a' html tag
        elif tag.name == 'a' and tag.has_attr('class'):
            # If element is a #hashtag, only keep text
            for tc in tag['class']:
                if tc == 'twitter-hashtag':
                    tweet_text += tag.get_text()

                # If element is a mention of @someuser, only keep text
                elif tc == 'twitter-atreply':
                    tweet_text += tag.get_text()

                # If element is a link
                elif tc == 'twitter-timeline-link':
                    # If it is not a link to some embedded content, keep raw link
                    if not tag.has_attr('data-pre-embedded') and tag.has_attr('data-expanded-url'):
                        # Add a sometimes missing space before url
                        if not tweet_text.endswith(' ') and not tweet_text.endswith('\n'):
                            tweet_text += ' '
                        # Add full url
                        tweet_text += tag['data-expanded-url']

        # If element is hashflag (hashtag + icon), handle as simple hashtag
        elif tag.name == 'span' and tag['class'][0] == 'twitter-hashflag-container':
            tweet_text += tag.a.get_text()

        # If tag is an image
        elif tag.name == 'img':
            # If it is of class 'Emoji'
            for tc in tag['class']:
                if tc == 'Emoji':
                    # Get url of Emoji
                    src = tag["src"]
                    # Use regex to extract unicode characters from file name
                    uni_str = re.search('/([0-9A-Fa-f\-]+?).png$', src).group(1)
                    # build the list of hex unicode characters separated by '-' in the file name
                    uni_list = uni_str.split('-')
                    # Extract individual unicode chars and add them to the tweet
                    for uni_char in uni_list:
                        # convert string to hex value of unicode character
                        tweet_text += chr(int(uni_char, 16))

        else:
            print("*** WARNING: No handler for tag in twitter text: " + tag.prettify())

    return tweet_text


def main(argv):

    # Build parser for command line arguments
    parser = argparse.ArgumentParser(description='toot tweets.')
    parser.add_argument('-t', metavar='<twitter account>', action='store', required=True)
    parser.add_argument('-i', metavar='<mastodon instance>', action='store', required=True)
    parser.add_argument('-m', metavar='<mastodon account>', action='store', required=True)
    parser.add_argument('-p', metavar='<mastodon password>', action='store', required=True)
    parser.add_argument('-a', metavar='<max age in days>', action='store', type=float, default=1)
    parser.add_argument('-d', metavar='<min delay in mins>', action='store', type=float, default=0)

    # Parse command line
    args = vars(parser.parse_args())

    twit_account = args['t']
    mast_instance = args['i']
    mast_account = args['m']
    mast_password = args['p']
    max_age = float(args['a'])
    min_delay = float(args['d'])

    # **********************************************************
    # Load twitter page of user. Process all tweets and generate
    # list of dictionaries ready to be posted on Mastodon
    # **********************************************************
    # To store content of all tweets from this user
    tweets = []

    # Get a copy of the default headers that requests would use
    headers = requests.utils.default_headers()

    # Update default headers with randomly selected user agent
    headers.update(
        {
            'User-Agent': USER_AGENTS[random.randint(0, len(USER_AGENTS)-1)],
        }
    )

    # Download twitter page of user
    response = requests.get('https://twitter.com/' + twit_account, headers=headers)

    ## DEBUG: Save page to file
    #of = open('twitter.html', 'w')
    #of.write(response.text)
    #of.close()

    # Verify that download worked
    if response.status_code != 200:
        print("Could not download twitter timeline. Aborting.")
        exit(-1)

    # Build tree of html elements for processing
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract twitter timeline
    results = soup.find_all('div', class_='content')

    for result in results:
        # Isolate tweet header
        sih = result.find('div', class_='stream-item-header')

        # extract author
        author = sih.find('strong', class_='fullname').get_text()

        # Extract author's logo
        author_logo_url = sih.find('img', class_='avatar')['src']

        # Extract time stamp
        try:
            timestamp = sih.find('a', class_='tweet-timestamp').find('span', class_='_timestamp')['data-time']
        except AttributeError:
            continue

        # Extract tweet id
        tweet_id = sih.find('a', class_='tweet-timestamp')['href']

        # Extract user name
        author_account = re.search('^/(.+?)/', tweet_id).group(1)

        # Isolate tweet text container
        ttc = result.find('div', class_='js-tweet-text-container')

        # extract iterator over tweet text contents
        tt_iter = ttc.find('p', class_='tweet-text').children

        tweet_text = cleanup_tweet_text(tt_iter)

        # Check it the tweet is a retweet from somebody else
        if author_account.lower() != twit_account.lower():
            tweet_text = 'RT from ' + author + ' @' + author_account + '\n\n' + tweet_text

        # Add footer with link to original tweet
        tweet_text += '\n\nOriginal tweet : https://twitter.com' + tweet_id

        # Isolate attached media container
        amoc = result.find('div', class_='AdaptiveMediaOuterContainer')

        photos = []
        if amoc:
            # Extract photos
            photo_conts = amoc.find_all('div', class_='AdaptiveMedia-photoContainer')
            for p in photo_conts:
                photos.append(p['data-image-url'])

            # Mention presence of videos in tweet
            videos = amoc.find_all('div', class_='AdaptiveMedia-videoContainer')
            if len(videos) != 0:
                tweet_text += '\n\n[Video embedded in original tweet]'

        # If no media was specifically added in the tweet, try to get the first picture
        # with "twitter:image" meta tag in first linked page in tweet text
        if not photos:
            m = re.search(r"http[^ \n\xa0]*", tweet_text)
            if m is not None:
                link_url = m.group(0)
                try:
                    r = requests.get(link_url)
                    if r.status_code == 200:
                        # Matches the first instance of either twitter:image or twitter:image:src meta tag
                        match = re.search(r'<meta name="twitter:image(?:|:src)" content="(.+?)".*?>', r.text)
                        if match is not None:
                            photos.append(match.group(1))
                except ConnectionError:
                    pass

        # Add dictionary with content of tweet to list
        tweet = {
            "author": author,
            "author_account": author_account,
            "author_logo_url": author_logo_url,
            "timestamp": timestamp,
            "tweet_id": tweet_id,
            "tweet_text": tweet_text,
            "photos": photos,
        }
        tweets.append(tweet)

    # DEBUG: Print extracted tweets
    # for t in tweets:
    #     print(t)

    # **********************************************************
    # Iterate tweets. Check if the tweet has already been posted
    # on Mastodon. If not, post it and add it to database
    # **********************************************************

    # Try to open database. If it does not exist, create it
    sql = sqlite3.connect('twoot.db')
    db = sql.cursor()
    db.execute('''CREATE TABLE IF NOT EXISTS toots (twitter_account TEXT, mastodon_instance TEXT,
               mastodon_account TEXT, tweet_id TEXT, toot_id TEXT)''')

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
        print('ERROR: Login to ' + mast_instance + ' Failed')
        print(me)
        sys.exit(1)

    # Upload tweets
    for tweet in reversed(tweets):
        # Check in database if tweet has already been posted
        db.execute('''SELECT * FROM toots WHERE twitter_account = ? AND mastodon_instance  = ? AND
                   mastodon_account = ? AND tweet_id = ?''',
                   (twit_account, mast_instance, mast_account, tweet['tweet_id']))
        tweet_in_db = db.fetchone()

        if tweet_in_db is not None:
            # Skip to next tweet
            continue

        # Check that the tweet is not too young (might be deleted) or too old
        age_in_hours = (time.time() - float(tweet['timestamp'])) / 3600.0
        min_delay_in_hours = min_delay / 60.0
        max_age_in_hours = max_age * 24.0

        if age_in_hours < min_delay_in_hours or age_in_hours > max_age_in_hours:
            # Skip to next tweet
            continue

        # Upload photos
        media_ids = []
        for photo in tweet['photos']:
            # Download picture
            media = requests.get(photo)

            mime_type = media.headers['content-type']

            # Upload picture to Mastodon instance
            try:
                media_posted = mastodon.media_post(media.content)
                media_ids.append(media_posted['id'])
            except MastodonAPIError:  # Media cannot be uploaded (invalid format, dead link, etc.)
                pass
            except MastodonIllegalArgumentError:  # Could not determine mime type of content
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
            print('ERROR: posting ' + tweet['tweet_text'] + ' to ' + mast_instance + ' Failed')
            print(me)
            sys.exit(1)

        # Insert toot id into database
        if 'id' in toot:
            db.execute("INSERT INTO toots VALUES ( ? , ? , ? , ? , ? )",
                       (twit_account, mast_instance, mast_account, tweet['tweet_id'], toot['id']))
            sql.commit()


if __name__ == "__main__":
    main(sys.argv)
