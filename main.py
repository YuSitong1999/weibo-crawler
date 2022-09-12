import copy
import json
import logging
import os
import shutil
import sys
import time
import datetime

import requests
import pytz

headers = {}


def request_json(url: str):
    response = requests.get(url, headers=headers)
    logging.info(url)
    logging.info(response.text)
    return json.loads(response.text)


def sleep(seconds: int):
    print(f'休息 {seconds} 秒')
    time.sleep(seconds)


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return obj.__dict__


class UserMblogConfig:
    def __init__(self, data):
        self.id_list: list[int] = data['id_list']
        self.since_date: datetime.datetime = pytz.UTC.localize(
            datetime.datetime.strptime(data['since_data'], '%Y-%m-%d'))


class UserMutualFollowConfig:
    def __init__(self, data):
        self.id_list: list[int] = data['id_list']
        self.min_follower: int = data['min_follower']
        self.max_mutual_follower: int = data['max_mutual_follower']
        self.include_indirect: bool = data['include_indirect']


class CrawlerConfig:
    def __init__(self, data):
        self.version: str = data['version']
        self.user_agent: str = data['user_agent']
        self.cookie: str = data['cookie']
        self.page_sleep_count: int = data['page_sleep_count']
        self.page_sleep_duration: int = data['page_sleep_duration']
        self.user_id_list: list[int] = data['user_id_list']

        # 抓取微博配置
        self.user_mblog = UserMblogConfig(data['user_mblog'])
        # 抓取互关配置
        self.user_mutual_follow = UserMutualFollowConfig(data['user_mutual_follow'])


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


class Mblog:
    def __init__(self, mblog):
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
            data = request_json(f'https://weibo.com/ajax/statuses/longtext?id={self.mblog_id}')
            self.long_text = data['data']['longTextContent']

        # 附带图片
        self.has_picture: bool = len(mblog['pic_ids']) != 0
        self.picture_id_list = list[str]()
        self.picture_url_list = list[str]()
        # 确保图片文件夹存在
        os.makedirs(f'output{os.sep}{mblog["user"]["id"]}{os.sep}image', exist_ok=True)
        for picture_id in mblog['pic_ids']:
            self.picture_id_list.append(picture_id)
            url = mblog['pic_infos'][picture_id]['largest']['url']
            self.picture_url_list.append(url)
            response = requests.get(url, headers=headers)
            with open(f'output{os.sep}{mblog["user"]["id"]}{os.sep}image{os.sep}{picture_id}.jpg', 'wb') as f:
                f.write(response.content)
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
            self.retweet_mblog: Mblog = Mblog(mblog['retweeted_status'])


class Crawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        global headers
        headers = {'user-agent': config.user_agent, 'cookie': config.cookie}

    def start(self):
        for user_id in self.config.user_id_list:
            # 确保用户目录存在
            os.makedirs(f'output{os.sep}{user_id}', exist_ok=True)
            # 抓取用户信息
            data = request_json(f'https://weibo.com/ajax/profile/info?uid={user_id}')
            user = User(data['data']['user'])
            with open(f'output{os.sep}{user_id}{os.sep}user.json', 'w', encoding='utf-8') as f:
                json.dump(user, f, ensure_ascii=False, cls=MyEncoder, indent='    ')

            # 抓取微博
            if user_id in self.config.user_mblog.id_list:
                mblog_list = list[Mblog]()
                # 抓取用户微博
                queue_list_i: int = 0
                continue_flag: bool = True
                while continue_flag:
                    # 先休息，避免总是不足页，导致总不休息
                    if queue_list_i % self.config.page_sleep_count == 0:
                        sleep(self.config.page_sleep_duration)
                    queue_list_i += 1

                    print(f'正在抓取第{queue_list_i}页')
                    data = request_json(f'https://weibo.com/ajax/statuses/mymblog?uid={user.id}&page={queue_list_i}')
                    if len(data['data']['list']) == 0:
                        continue_flag = False

                    for data_mblog in data['data']['list']:
                        mblog = Mblog(data_mblog)
                        mblog_list.append(mblog)
                        if mblog.created_at < self.config.user_mblog.since_date and not mblog.is_top:
                            continue_flag = False
                            break
                    # 每抓取一页微博就写文件
                    with open(f'output{os.sep}{user_id}{os.sep}mblog.json', 'w', encoding='utf-8') as f:
                        json.dump(mblog_list, f, ensure_ascii=False, cls=MyEncoder, indent='    ')

            # 抓取互关
            if user_id in self.config.user_mutual_follow.id_list:
                # 抓取用户互关
                begin_user = copy.deepcopy(user)
                begin_user.mblog_list = []
                queue_list: list[User] = [begin_user]
                queue_set = set[int]()
                queue_set.add(begin_user.id)
                queue_list_i = -1
                follower_request_count = 0
                # 检查互关网络中的每个用户
                while True:
                    queue_list_i += 1
                    # 是否抓取间接互关
                    if queue_list_i >= 1 and not self.config.user_mutual_follow.include_indirect:
                        break
                    if queue_list_i >= len(queue_list):
                        break
                    if queue_list_i > 100:
                        print('互关网络用户超过100')
                        break
                    # 当前用户
                    now_user = queue_list[queue_list_i]
                    # 获取关注者
                    follower_page = 0
                    # 检查关注者的关注者，确认有没有回关
                    while True:
                        # 检查休息
                        if follower_request_count % self.config.page_sleep_count == 0:
                            sleep(self.config.page_sleep_duration)
                        follower_request_count += 1

                        # 关注的每一页
                        follower_page += 1
                        print(f'处理 {now_user.id} {now_user.screen_name} 第 {follower_page} 页关注者，检查是否回关')
                        follower_data = request_json(
                            f'https://weibo.com/ajax/friendships/friends?uid={now_user.id}&page={follower_page}')
                        if follower_data['ok'] != 1 or len(follower_data['users']) == 0:
                            break
                        for user_data in follower_data['users']:
                            follow_user = User(user_data)
                            # 关注者出现过，跳过
                            if follow_user.id in queue_set:
                                print(f'{follow_user.id} {follow_user.screen_name} 出现过，跳过')
                                continue
                            # 关注者粉丝过少，不值得关注
                            if follow_user.followers_count < self.config.user_mutual_follow.min_follower:
                                print(
                                    f'{follow_user.id} {follow_user.screen_name} {follow_user.followers_count} 关注者过少，跳过')
                                continue
                            # 检查每个关注者有没有回关
                            is_re_follow = False
                            re_follow_page = 0
                            while not is_re_follow:
                                # 检查休息
                                if follower_request_count % self.config.page_sleep_count == 0:
                                    sleep(self.config.page_sleep_duration)
                                follower_request_count += 1

                                # 关注者关注的每一页
                                re_follow_page += 1
                                # print(f'获取 {follow_user.id} {follow_user.screen_name} 是否回关 {re_follow_page}')
                                re_follow_data = request_json(
                                    f'https://weibo.com/ajax/friendships/friends?'
                                    f'uid={follow_user.id}&page={re_follow_page}')
                                if re_follow_data['ok'] != 1 or len(re_follow_data['users']) == 0:
                                    break
                                for re_follow_user_data in re_follow_data['users']:
                                    if re_follow_user_data['id'] == user.id:
                                        is_re_follow = True
                                        break
                            if is_re_follow:
                                queue_list.append(follow_user)
                                queue_set.add(follow_user.id)
                                print(f'！关注网络: {follow_user.id} {follow_user.screen_name} '
                                      f'{follow_user.friends_count} {follow_user.followers_count}')
                                # 每抓取一个直接或间接互关就写文件
                                with open(f'output{os.sep}{user_id}{os.sep}mutual_follow.json', 'w',
                                          encoding='utf-8') as f:
                                    json.dump(queue_list, f, ensure_ascii=False, cls=MyEncoder, indent='    ')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
    config_file_path: str = 'config.json'
    config_simple_file_path: str = 'config_simple.json'
    if not os.path.isfile(config_file_path):
        shutil.copy(config_simple_file_path, config_file_path)
        print(f'请编辑配置文件 {config_file_path} 后再次运行')
        sys.exit()
    # 读取配置
    with open(config_file_path, encoding='utf-8') as f:
        config_data = json.loads(f.read())
    config = CrawlerConfig(config_data)
    # 创建爬虫
    crawler = Crawler(config)
    # 确保输出文件夹存在
    os.makedirs('output', exist_ok=True)
    # 抓取用户信息
    crawler.start()
