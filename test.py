#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import requests

def deredir_url(url):
    """
    Given a URL, return the URL that the page really downloads from
    :param url: url to be de-redirected
    :return: direct url
    """

    ret = None
    try:
        # Download the page
        ret = requests.get(url, timeout=5)
    except:
        # If anything goes wrong keep the URL intact
        return url

    # Return the URL that the page was downloaded from
    return ret.url

def _remove_tracker_params(query_str):
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
    return urlencode(query_cleaned, safe='#', doseq=True)


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

    url_parsed = urlparse(dirty_url, allow_fragments=False)

    cleaned_url = urlunparse([
        url_parsed.scheme,
        url_parsed.netloc,
        url_parsed.path,
        url_parsed.params,
        _remove_tracker_params(url_parsed.query),
        _remove_trackers_fragment(url_parsed.fragment)
    ])

    return cleaned_url

def main():
    # url = 'https://example.com/video/this-aerial-ropeway?utm_source=Twitter&utm_medium=video&utm_campaign=organic&utm_content=Nov13&a=aaa&b=1#mkt_tok=tik&mkt_tik=tok'
    # url = "https://docs.helix-editor.com/keymap.html#movement"
    # url = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7071508/#sec1-nutrients-12-00530title"
    # url = "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section12208&num=0&edition=prelim"
    url = "https://shorturl.at/qwP38"
    print('Orig: ' + url)
    direct_url = deredir_url(url)
    print('dir : ' + direct_url)
    print('to  : ' + clean_url(direct_url))

if __name__=="__main__":
    main()
