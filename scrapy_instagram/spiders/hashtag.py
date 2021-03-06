# -*- coding: utf-8 -*-
import scrapy
import json
import time
import os.path

from scrapy.exceptions import CloseSpider

from scrapy_instagram.items import Post

class InstagramSpider(scrapy.Spider):
    name = "hashtag"  # Name of the Spider, required value
    custom_settings = {
        'FEED_URI': './scraped/%(name)s/%(hashtag)s/%(date)s',
    }
    checkpoint_path = './scraped/%(name)s/%(hashtag)s/.checkpoint'

    # def closed(self, reason):
    #     self.logger.info('Total Elements %s', response.url)

    def __init__(self, hashtag=''):
        self.hashtag = hashtag
        if hashtag == '':
            self.hashtag = input("Name of the hashtag? ")
        self.start_urls = ["https://www.instagram.com/explore/tags/"+self.hashtag+"/?__a=1"]
        self.date = time.strftime("%d-%m-%Y_%H")
        self.checkpoint_path = './scraped/%s/%s/.checkpoint' % (self.name, self.hashtag)
        self.readCheackpoint()

    def readCheackpoint(self):
        filename = self.checkpoint_path
        if not os.path.exists(filename):
            self.last_crawled = ''
            return
        self.last_crawled = open(filename).readline().rstrip()

    # Entry point for the spider
    def parse(self, response):
        return self.parse_htag(response)

    # Method for parsing a hastag
    def parse_htag(self, response):
 
        #Load it as a json object
        graphql = json.loads(response.text)
        has_next = graphql['graphql']['hashtag']['edge_hashtag_to_media']['page_info']['has_next_page']
        edges = graphql['graphql']['hashtag']['edge_hashtag_to_media']['edges']

        if not hasattr(self, 'starting_shorcode') and len(edges):
            self.starting_shorcode = edges[0]['node']['shortcode']
            filename = self.checkpoint_path
            f = open(filename, 'w')
            f.write(self.starting_shorcode)

        for edge in edges:
            node = edge['node']
            shortcode = node['shortcode']
            if(self.checkAlreadyScraped(shortcode)):
                return
            yield scrapy.Request("https://www.instagram.com/p/"+shortcode+"/?__a=1", callback=self.parse_post)

        if has_next:
            end_cursor = graphql['graphql']['hashtag']['edge_hashtag_to_media']['page_info']['end_cursor']
            yield scrapy.Request("https://www.instagram.com/explore/tags/"+self.hashtag+"/?__a=1&max_id="+end_cursor, callback=self.parse_htag)


    def checkAlreadyScraped(self,shortcode):
        return self.last_crawled == shortcode
           
    def parse_post(self, response):
        graphql = json.loads(response.text)
        media = graphql['graphql']['shortcode_media']
        yield self.makePost(media)         

    def get_hashtags(self, text, addHashtag=True, order=False):
        tags = set([("#" if addHashtag else "") + item.strip("#.,-\"\'&*^!?") for item in text.split() if (item.startswith("#") and len(item) < 256 and len(item)>0)])
        return sorted(tags) if order else tags

    def get_mentions(self, text):
        #First we split the caption in re.split.
        #Items with "@" in them (but not as the last character) get split again using "@" as the separator, and we keep the second part of the split (the username).
        #This way we can find mentions without a whitespace before them
        mentions = set([item.split('@')[1] for item in re.split(';|,|\*|\n| |\\\\', text) if ("@" in item) and ( item.index("@")+1 < len(item) ) ])
        return mentions
        
    def makePost(self, media):
        location = media['location']
        caption = ''
        comment = 0
        like = 0
        loc_id = 0
        loc_name = ''
        if location is not None:
            loc_id = location['id']
            loc_name = location['name']
        if len(media['edge_media_to_caption']['edges']):
            caption = media['edge_media_to_caption']['edges'][0]['node']['text']
        try:
            comment = media['edge_media_preview_comment']['count']
            like = media['edge_media_preview_like']['count']
        except NameError:
            pass
            
        hashtags = self.get_hashtags(caption)
        mentions = self.get_mentions(caption)
        return Post(id=media['id'],
                    shortcode=media['shortcode'],
                    caption=caption,
                    display_url=media['display_url'],
                    loc_id=loc_id,
                    loc_name=loc_name,
                    owner_id =media['owner']['id'],
                    owner_name = media['owner']['username'],
                    taken_at_timestamp= media['taken_at_timestamp'],
                    comments= comment,
                    likes= like,
                    hashtags= hashtags,
                    mentions = mentions
                    )