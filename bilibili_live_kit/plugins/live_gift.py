import logging
import re
from time import time, sleep

from . import API_LIVE_GET_ROOM_INFO, \
    API_LIVE_ROOM, \
    API_LIVE_GIFT_PLAYER_BAG, \
    API_LIVE_GIFT_BAG_SEND, \
    HEART_DELTA
from .passport import BiliBiliPassport
from ..utils import build_report


class BiliBiliLiveGift:
    def __init__(self, passport: BiliBiliPassport):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.passport = passport
        self.session = passport.session

    def get_room_info(self, room_id):
        meta_info = self.get_room_meta_info(room_id)
        if not meta_info:
            return
        payload = {'roomid': meta_info['room_id']}
        rasp = self.session.post(API_LIVE_GET_ROOM_INFO, data=payload)
        payload = rasp.json()
        if payload['code'] == 0:
            payload['data'].update({'danmu_rnd': meta_info['danmu_rnd']})
            return payload['data']
        self.logger.info('get room info failed: %(msg)s', payload)

    def get_room_meta_info(self, room_id):
        if not room_id:
            return
        rasp = self.session.get(API_LIVE_ROOM % room_id)
        pattern = r'var ROOMID = (\d+);\n.*var DANMU_RND = (\d+);'
        matches = re.search(pattern, rasp.text)
        if matches:
            return {'room_id': matches.group(1), 'danmu_rnd': matches.group(2)}

    def get_gift_meta_info(self):
        rasp = self.session.get(API_LIVE_GIFT_PLAYER_BAG)
        items = rasp.json()['data']
        if not len(items):
            return
        room_id = self.passport.get_room_id()
        room_info = self.get_room_info(room_id)
        if not room_info:
            return
        return {'room_info': room_info, 'gift_items': items}

    def send_gift(self, gift_info, room_info, danmu_rnd):
        token = self.session.cookies.get('LIVE_LOGIN_DATA', domain='.bilibili.com', path='/')
        payload = dict(
            roomid=room_info['ROOMID'],
            ruid=room_info['MASTERID'],
            giftId=gift_info['gift_id'],
            num=gift_info['gift_num'],
            Bag_id=gift_info['id'],
            coinType='silver',
            timestamp=int(time()),
            rnd=danmu_rnd,
            token=token
        )
        rasp = self.session.post(API_LIVE_GIFT_BAG_SEND, data=payload)
        return rasp.json()['code'] == 0

    def print_gift_report(self, gift_info, room_info):
        items = (
            '---------------------------------------',
            ('Bag ID', gift_info['id']),
            ('Gift Name', gift_info['gift_name']),
            ('Gift Price', gift_info['gift_price']),
            ('Gift Number', gift_info['gift_num']),
            ('Gift Expireat', gift_info['expireat']),
            ('Sent Room ID', room_info['ROOMID']),
            '---------------------------------------',
        )
        self.logger.info('\n%s', build_report(items))


def send_gift(passport: BiliBiliPassport):
    while True:
        if not passport.login():
            continue
        gift = BiliBiliLiveGift(passport)
        meta_info = gift.get_gift_meta_info()
        if not meta_info:
            continue
        room_info = meta_info['room_info']
        danmu_rnd = room_info['danmu_rnd']
        for gift_info in meta_info['gift_items']:
            if gift_info['expireat'] != '今日':
                continue
            if gift.send_gift(gift_info, room_info, danmu_rnd):
                gift.print_gift_report(gift_info, room_info)
        sleep(HEART_DELTA.total_seconds())
