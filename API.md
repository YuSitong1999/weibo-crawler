# 微博API

## 获取用户信息（cookie）

格式

https://weibo.com/ajax/profile/info?uid={用户id数字}

示例

https://weibo.com/ajax/profile/info?uid=7772824758

## 获取微博内容

格式

https://weibo.com/ajax/statuses/mymblog?uid={用户id数字}&page={从1开始页码}

示例

https://weibo.com/ajax/statuses/mymblog?uid=7772824758&page=1

## 获取长微博

格式

https://weibo.com/ajax/statuses/longtext?id={微博字母id}

示例

https://weibo.com/ajax/statuses/longtext?id=LCzT6osOC

## 获取关注者
https://weibo.com/ajax/friendships/friends?page=1&uid=7772824758

## 获取粉丝
https://weibo.com/ajax/friendships/friends?relate=fans&page=1&uid=7772824758
