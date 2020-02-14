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

# Update from https://www.whatismybrowser.com/guides/the-latest-user-agent/
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/69.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36 Edg/44.18362.329.0',
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

                # If element is an external link
                elif tc == 'twitter_external_link':
                    # If element is a simple link
                    if tag.has_attr('data-expanded-url'):
                        # Add a sometimes missing space before url
                        if not tweet_text.endswith(' ') and not tweet_text.endswith('\n'):
                            tweet_text += ' '
                        # Add full url
                        tweet_text += tag['data-expanded-url']
                    # If element is a picture
                    elif tag.has_attr('data-url'):
                        # TODO handle photo
                        pass

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

        # elif tag is a geographical point of interest
        elif tag.name == 'span' and tag['class'][0] == 'tweet-poi-geo-text':
            pass

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

    url = 'https://mobile.twitter.com/' + twit_account
    # Download twitter page of user. We should get a 'no javascript' landing page and some cookies
    r1 = requests.get(url, headers=headers)

    # DEBUG: Save page to file
    of = open('no_js_page.html', 'w')
    of.write(r1.text)
    of.close()

    # Verify that this is the no_js page that we expected
    soup = BeautifulSoup(r1.text, 'html.parser')
    assert 'JavaScript is disabled' in str(soup.form.p.string),\
        'this is not the no_js page we expected. Quitting'

    # Submit POST form response with cookies
    headers.update(
        {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': url,
        }
    )

    response = requests.post('https://mobile.twitter.com/i/nojs_router?path=%2F' + twit_account, headers=headers, cookies=r1.cookies)

    # DEBUG: Save page to file
    of = open('twitter.html', 'w')
    of.write(response.text)
    of.close()

    # Verify that download worked
    assert response.status_code == 200,\
        'The twitter page did not download correctly. Aborting'

    # Verify that we now have the correct twitter page
    soup = BeautifulSoup(response.text, 'html.parser')
    assert twit_account.lower() in str(soup.head.title.string).lower(),\
        'This is not the correct twitter page. Quitting'

    # Extract twitter timeline
    results = soup.find_all('table', class_='tweet')

    for result in results:
        # Extract tweet id
        tweet_id = str(result['href']).strip('?p=v')

        # Isolate tweet header
        sih = result.find('tr', class_='tweet-header')

        # extract author
        author = sih.find('strong', class_='fullname').get_text()

        # Extract author's logo
        author_logo_url = sih.find('img', alt=author)['src']

        # TODO: Extract time stamp by following link under td.timestamp
        import datetime
        timestamp = datetime.datetime.now().timestamp()

        # Extract user name
        author_account = str(sih.find('div', class_='username').span.next_sibling).strip('\n ')

        # Isolate tweet text container
        ttc = result.find('tr', class_='tweet-container')

        # extract iterator over tweet text contents
        tt_iter = ttc.find('div', class_='dir-ltr').children

        tweet_text = cleanup_tweet_text(tt_iter)

        # Check it the tweet is a retweet from somebody else
        if author_account.lower() != twit_account.lower():
            tweet_text = 'RT from ' + author + '(@' + author_account + '\n\n)' + tweet_text

        # Add footer with link to original tweet
        tweet_text += '\n\nOriginal tweet : https://twitter.com/' + tweet_id

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
                    r = requests.get(link_url, timeout=10)
                    if r.status_code == 200:
                        # Matches the first instance of either twitter:image or twitter:image:src meta tag
                        match = re.search(r'<meta name="twitter:image(?:|:src)" content="(.+?)".*?>', r.text)
                        if match is not None:
                            url = match.group(1).replace('&amp;', '&')  # Remove HTML-safe encoding from URL if any
                            photos.append(url)
                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.TooManyRedirects):
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
            media = False
            # Download picture
            try:
                media = requests.get(photo)
            except:
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
