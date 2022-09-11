import json
import requests


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        return obj.__dict__


class CrawlerConfig:
    def __init__(self, data):
        self.version: str = data['version']
        self.user_id_list: list[int] = data['user_id_list']
        self.user_agent: str = data['user_agent']
        self.cookie: str = data['cookie']


class User:
    def __init__(self, user):
        self.id: int = user['id']
        # 网名
        self.screen_name: str = user['screen_name']
        # 高清头像
        self.avatar_hd: str = user['avatar_hd']
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
            with open(f'{user.id}.json', 'w', encoding='utf-8') as f:
                json.dump(user, f, cls=MyEncoder, ensure_ascii=False)  #


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
