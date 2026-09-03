import requests
from loguru import logger

class BilibiliTask:
    def __init__(self, cookie):
        self.cookie = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.bilibili.com/',
            'Cookie': cookie
        }
        self.csrf = self._get_csrf()

    def _get_csrf(self):
        for item in self.cookie.split(';'):
            if item.strip().startswith('bili_jct'):
                return item.split('=')[1]
        return None

    def get_user_info(self):
        url = 'https://api.bilibili.com/x/web-interface/nav'
        try:
            res = requests.get(url, headers=self.headers)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return data['data']
            logger.warning(f"获取用户信息失败: {data.get('message')}")
            return None
        except Exception as e:
            logger.error(f"请求用户信息API异常: {e}")
            return None


    
    def get_dynamic_videos(self):
        # 注意：dynamic/region 接口已被 B站废弃（返回 code=-404 "啥都木有"），
        # 仅作为回退来源保留，默认投币来源已改为 ranking。
        url = 'https://api.bilibili.com/x/web-interface/dynamic/region?ps=5&rid=1'
        try:
            res = requests.get(url, headers=self.headers)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return [video['bvid'] for video in data.get('data', {}).get('archives', [])]
            logger.warning(f"动态视频接口返回非0: code={data.get('code')}, message={data.get('message')}（该接口疑似已废弃）")
            return []
        except Exception as e:
            logger.error(f"请求动态视频API异常: {e}")
            return []

    def get_ranking_videos(self):
        url = 'https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all'
        try:
            res = requests.get(url, headers=self.headers)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return [video['bvid'] for video in data.get('data', {}).get('list', [])]
            logger.warning(f"排行榜视频接口返回非0: code={data.get('code')}, message={data.get('message')}")
            return []
        except Exception as e:
            logger.error(f"请求排行榜视频API异常: {e}")
            return []

    def check_video_coin_status(self, bvid):
        url = f'https://api.bilibili.com/x/web-interface/archive/coins?bvid={bvid}'
        try:
            res = requests.get(url, headers=self.headers)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return data['data']['multiply'] > 0
            return False
        except Exception:
            return False

    def add_coin(self, bvid, num=1, select_like=1):
        if not self.csrf: return False, "Bili_jct(csrf) 未找到"
        url = 'https://api.bilibili.com/x/web-interface/coin/add'
        data = {'bvid': bvid, 'multiply': num, 'select_like': select_like, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            data = res.json()
            if data['code'] == 0:
                return True, "投币成功"
            return False, data.get('message', '投币失败')
        except Exception as e:
            return False, str(e)
            
    def share_video(self, bvid):
        if not self.csrf: return False, "Bili_jct(csrf) 未找到"
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            data = res.json()
            if data['code'] == 0:
                return True, "分享成功"
            return False, data.get('message', '分享失败')
        except Exception as e:
            return False, str(e)

    def watch_video(self, bvid):
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        data = {'bvid': bvid, 'played_time': 30, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            data = res.json()
            if data['code'] == 0:
                return True, "观看成功"
            return False, data.get('message', '观看失败')
        except Exception as e:
            return False, str(e)
            
    def live_sign(self):
        url = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign'
        try:
            res = requests.get(url, headers=self.headers)
            data = res.json()
            if data['code'] == 0:
                return True, data.get('data', {}).get('text', '直播签到成功')
            return False, data.get('message', '直播签到失败')
        except Exception as e:
            return False, str(e)

    def silver2coin(self):
        # 银瓜子兑换硬币：每日最多换 1 枚硬币（需账号有银瓜子）
        if not self.csrf:
            return False, "Bili_jct(csrf) 未找到"
        url = 'https://api.live.bilibili.com/pay/v1/Exchange/silver2coin'
        data = {'csrf': self.csrf, 'csrf_token': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            data = res.json()
            code = data.get('code')
            msg = data.get('message') or ''
            if code == 0:
                return True, "银瓜子兑换硬币成功"
            # 无银瓜子 / 今日已兑换：非失败，视为跳过
            if '不足' in msg or '已经兑换' in msg or '已兑换' in msg or '今天' in msg:
                return False, f"银瓜子不足或今日已兑换，跳过"
            logger.warning(f"银瓜子兑换返回: code={code}, msg={msg}")
            return False, msg or "银瓜子兑换失败"
        except Exception as e:
            return False, str(e)

    def get_medal_list(self):
        # 获取已佩戴的粉丝勋章列表（含每个勋章的 room_id）
        url = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/user/UserMedalList'
        headers = dict(self.headers)
        headers['Referer'] = 'https://live.bilibili.com/'
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            if data.get('code') == 0:
                medallist = data.get('data', {}).get('list', [])
                return [m.get('room_id') for m in medallist if m.get('room_id')]
            logger.warning(f"粉丝勋章列表返回非0: code={data.get('code')}, message={data.get('message')}")
            return []
        except Exception as e:
            logger.error(f"请求粉丝勋章列表异常: {e}")
            return []

    def medal_sign(self, room_id):
        if not self.csrf:
            return False, "Bili_jct(csrf) 未找到"
        url = 'https://api.vc.bilibili.com/link_setting/v1/link_setting/sign_in'
        data = {'room_id': room_id, 'csrf': self.csrf}
        headers = dict(self.headers)
        headers['Referer'] = 'https://live.bilibili.com/'
        headers['Origin'] = 'https://live.bilibili.com'
        try:
            res = requests.post(url, headers=headers, data=data)
            data = res.json()
            code = data.get('code')
            msg = data.get('message') or ''
            if code == 0:
                return True, "粉丝勋章签到成功"
            if '重复' in msg or '已' in msg or '已经' in msg:
                return True, "粉丝勋章今日已签"
            logger.warning(f"粉丝勋章签到返回: code={code}, msg={msg}")
            return False, msg or "粉丝勋章签到失败"
        except Exception as e:
            return False, str(e)

    def manga_sign(self):
        url = 'https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn'
        try:
            # 接口接受 form-urlencoded；platform 标准值为 android（iOS 亦可）
            res = requests.post(url, headers=self.headers, data={'platform': 'android'})
            data = res.json()
            code = data.get('code')
            msg = data.get('msg') or data.get('message') or ''
            # 成功：code=0；今日已签（code=1 / invalid_argument 且提示重复签到）→ 视为成功
            if code == 0 or '重复签到' in msg or code == 'invalid_argument':
                return True, "漫画签到成功"
            # 真实错误：打印以便排查
            logger.warning(f"漫画签到接口返回: code={code}, msg={msg}")
            return False, msg or '漫画签到失败'
        except Exception as e:
            return False, str(e)