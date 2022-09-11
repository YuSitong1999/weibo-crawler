import json
import os
import time
import datetime

import requests
import pytz


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return obj.__dict__


class CrawlerConfig:
    def __init__(self, data):
        self.version: str = data['version']
        self.user_id_list: list[int] = data['user_id_list']
        self.user_agent: str = data['user_agent']
        self.cookie: str = data['cookie']
        self.page_sleep_count: int = data['page_sleep_count']
        self.page_sleep_duration: int = data['page_sleep_duration']
        # 开始日期
        self.since_date: datetime.datetime = pytz.UTC.localize(
            datetime.datetime.strptime(data['since_data'], '%Y-%m-%d'))


class UserSummary:
    def __init__(self, user):
        self.id: int = user['id']
        # 网名
        self.screen_name: str = user['screen_name']
        # 高清头像
        self.avatar_hd: str = user['avatar_hd']


class User(UserSummary):
    def __init__(self, user):
        super().__init__(user)
        # 介绍
        self.description: str = user['description']
        # 自称地址
        self.location: str = user['location']
        # 粉丝
        self.followers_count: int = user['followers_count']
        # 朋友
        self.friends_count: int = user['friends_count']
        # 微博数
        self.statuses_count: int = user['statuses_count']

        self.mblog_list = list[Mblog]()


class Mblog:
    def __init__(self, mblog, headers: dict[str, str]):
        self.id: int = mblog['id']
        self.mblog_id: str = mblog['mblogid']
        self.text_raw: str = mblog['text_raw']
        self.text: str = mblog['text']
        # 指定、公开……
        self.title: str = mblog['title']['text'] if 'title' in mblog and 'text' in mblog['title'] else ''
        # 是否置顶
        self.is_top: bool = self.title == '置顶'
        # 发布地
        self.region_name: str = mblog['region_name'] if 'region_name' in mblog else ''
        # 发布时间
        self.created_at: datetime.datetime = datetime.datetime.strptime(mblog['created_at'],
                                                                        '%a %b %d %X %z %Y')

        # 是否长微博
        self.is_long_text: bool = mblog['isLongText']
        if self.is_long_text:  # 部分需要登录
            response = requests.get(f'https://weibo.com/ajax/statuses/longtext?id={self.mblog_id}', headers=headers)
            data = json.loads(response.text)
            self.long_text = data['data']['longTextContent']

        # 附带图片
        self.has_picture: bool = len(mblog['pic_ids']) != 0
        self.picture_id_list = list[str]()
        self.picture_url_list = list[str]()
        for picture_id in mblog['pic_ids']:
            self.picture_id_list.append(picture_id)
            self.picture_url_list.append(mblog['pic_infos'][picture_id]['largest']['url'])
        # 附带文章
        self.has_article: bool = 'url_struct' in mblog
        if self.has_article:
            self.article_url_list = list[str]()
            for article in mblog['url_struct']:
                self.article_url_list.append(article['long_url'])
        # 是否转发
        self.is_retweet: bool = 'retweeted_status' in mblog
        if self.is_retweet:
            self.retweet_id: int = mblog['retweeted_status']['id']
            self.retweet_mblog: Mblog = Mblog(mblog['retweeted_status'], headers=headers)


class Crawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.headers = {'user-agent': config.user_agent, 'cookie': config.cookie}

    def start(self):
        for user_id in self.config.user_id_list:
            # 抓取用户信息
            response = requests.get(f'https://weibo.com/ajax/profile/info?uid={user_id}', headers=self.headers)
            print(response.text)
            data = json.loads(response.text)
            user = User(data['data']['user'])
            # 抓取用户微博
            i: int = 0
            continue_flag: bool = True
            while continue_flag:
                i += 1
                if i % self.config.page_sleep_count == 0:
                    print(f'休息中 {self.config.page_sleep_duration}')
                    time.sleep(self.config.page_sleep_duration)

                print(f'正在抓取第{i}页')
                response = requests.get(f'https://weibo.com/ajax/statuses/mymblog?uid={user.id}&page={i}',
                                        headers=self.headers)
                data = json.loads(response.text)
                if len(data['data']['list']) == 0:
                    continue_flag = False

                for data_mblog in data['data']['list']:
                    mblog = Mblog(data_mblog, self.headers)
                    user.mblog_list.append(mblog)
                    if mblog.created_at < self.config.since_date and not mblog.is_top:
                        continue_flag = False
                        break
            with open(f'{user.id}.json', 'w', encoding='utf-8') as f:
                json.dump(user, f, ensure_ascii=False, cls=MyEncoder, indent='    ')  #


if __name__ == '__main__':
    config_file_path: str = 'config.json'
    # 读取配置
    with open(config_file_path, encoding='utf-8') as f:
        config_data = json.loads(f.read())
    config = CrawlerConfig(config_data)
    # 创建爬虫
    crawler = Crawler(config)
    # 抓取用户信息
    crawler.start()
