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
import os
import requests
from bs4 import BeautifulSoup, element
import sqlite3
import time
import re
from mastodon import Mastodon


#TODO manage command line
TWIT_ACCOUNT  = 'noirextreme'
MAST_ACCOUNT  = 'jc@noirextreme.com'
MAST_PASSWORD  = 'NfH1D.Sdd63juBmK'
MAST_INSTANCE = 'botsin.space'
MAX_AGE = 1  # in days
MIN_DELAY = 0  # in minutes


#TODO submit random user agent from list
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.87 Safari/537.36'

#TODO manage errors


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
                        if tweet_text[len(tweet_text)-1] != ' ' and tweet_text[len(tweet_text)-1] != '\n':
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
                        tweet_text += '&#x' + uni_char + ';'

        else:
            print("*** WARNING: No handler for tag in twitter text: " + tag.prettify())

    return tweet_text


# **********************************************************
# Load twitter page of user. Process all tweets and generate
# list of dictionaries ready to be posted on Mastodon
# **********************************************************
# To store content of all tweets from this user
tweets = []

# Get a copy of the default headers that requests would use
headers = requests.utils.default_headers()

# Update default headers with user agent
headers.update(
    {
        'User-Agent': USER_AGENT,
    }
)

# Download twitter page of user
response = requests.get('https://twitter.com/' + TWIT_ACCOUNT, headers=headers)

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
    author = sih.find('strong', class_='fullname').string

    # Extract author's logo
    author_logo_url = sih.find('img', class_='avatar')['src']

    # Extract time stamp
    timestamp = sih.find('a', class_='tweet-timestamp').find('span', class_='_timestamp')['data-time']

    # Extract tweet id
    tweet_id = sih.find('a', class_='tweet-timestamp')['href']

    # Extract user name
    user_name = re.search('^/(.+?)/', tweet_id).group(1)

    # Isolate tweet text container
    ttc = result.find('div', class_='js-tweet-text-container')

    # extract iterator over tweet text contents
    tt_iter = ttc.find('p', class_='tweet-text').children

    tweet_text = cleanup_tweet_text(tt_iter)

    # Isolate attached media container
    amoc = result.find('div', class_='AdaptiveMediaOuterContainer')

    photos = []
    if amoc:
        # Extract photos
        photo_conts = amoc.find_all('div', class_='AdaptiveMedia-photoContainer')
        for p in photo_conts:
            photos.append(p['data-image-url'])

        # Mention presence in videos in tweet
        videos = amoc.find_all('div', class_='AdaptiveMedia-videoContainer')
        if len(videos) != 0:
            tweet_text += '\n\n[Embedded video in original tweet]'

    # Add dictionary with content of tweet to list
    tweet = {
        "author": author,
        "user_name": user_name,
        "author_logo_url": author_logo_url,
        "timestamp": timestamp,
        "tweet_id": tweet_id,
        "tweet_text": tweet_text,
        "photos": photos,
    }
    tweets.append(tweet)

for t in tweets:
    print(t)

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
if not os.path.isfile(MAST_INSTANCE + '.secret'):
    if not Mastodon.create_app(
            'twoot',
            api_base_url='https://' + MAST_INSTANCE,
            to_file=MAST_INSTANCE + '.secret'
    ):
        print('failed to create app on ' + MAST_INSTANCE)
        sys.exit(1)

# Log in to mastodon instance
try:
    mastodon = Mastodon(
        client_id=MAST_INSTANCE + '.secret',
        api_base_url='https://' + MAST_INSTANCE
    )

    mastodon.log_in(
        username=MAST_ACCOUNT,
        password=MAST_PASSWORD,
        scopes=['read', 'write'],
        to_file=MAST_INSTANCE + ".secret"
    )
except:
    print("ERROR: Login Failed")
    sys.exit(1)

# Upload tweets
for tweet in tweets:
    # Check in database if tweet has already been posted
    db.execute('''SELECT * FROM toots WHERE twitter_account = ? AND mastodon_instance  = ? AND
               mastodon_account = ? AND tweet_id = ?''',
               (TWIT_ACCOUNT, MAST_INSTANCE, MAST_ACCOUNT, tweet['tweet_id']))
    tweet_in_db = db.fetchone()

    if tweet_in_db is not None:
        # Skip to next tweet
        continue

    # Check that the tweet is not too young (might be deleted) or too old
    age_in_hours = (time.time() - float(tweet['timestamp'])) / 3600.0
    min_delay_in_hours = float(MIN_DELAY) / 60.0
    max_age_in_hours = float(MAX_AGE) * 24.0

    if age_in_hours < min_delay_in_hours or age_in_hours > max_age_in_hours:
        # Skip to next tweet
        continue

    # Upload photos
    media_ids = []
    for photo in tweet['photos']:
        # Download picture
        media = requests.get(photo)

        # Upload picture to Mastodon instance
        media_posted = mastodon.media_post(media.content, mime_type=media.headers.get('content-type'))
        media_ids.append(media_posted['id'])

    # Post toot
    toot = mastodon.status_post(tweet['tweet_text'], media_ids=media_ids, visibility='public')

    # Insert toot id into database
    if 'id' in toot:
        db.execute("INSERT INTO toots VALUES ( ? , ? , ? , ? , ? )",
                   (TWIT_ACCOUNT, MAST_INSTANCE, MAST_ACCOUNT, tweet['tweet_id'], toot['id']))
        sql.commit()
