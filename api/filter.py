# api/filter.py
import requests
import re
import urllib.parse
from datetime import datetime
import json
from http.server import BaseHTTPRequestHandler
import sys
import io

# 目标URL（保持不变）
url = 'https://comm.aci.game.qq.com/main?game=cjm&area=2&partition=&platid=1&callback=17319072866313099&sCloudApiName=ams.gameattr.role&iAmsActivityId=https%3A%2F%2Fgp.qq.com%2Fact%2Fa20190421cdkey%2Findex_pc.html'
headers = {
    'Host': 'comm.aci.game.qq.com',
    'Referer': 'https://gp.qq.com/'
}

# 段位映射
def get_segment_name(score):
    if score < 1000:
        return "未定级"
    elif 1000 <= score < 1600:
        return "热血青铜"
    elif 1600 <= score < 2200:
        return "不屈白银"
    elif 2200 <= score < 2700:
        return "英勇黄金"
    elif 2700 <= score < 3200:
        return "坚韧铂金"
    elif 3200 <= score < 3700:
        return "不朽星钻"
    elif 3700 <= score < 4200:
        return "荣耀皇冠"
    elif score >= 4200:
        return "超级王牌"
    else:
        return "未知段位"

def convert_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return "未知时间"

def process_line(line):
    """处理单行数据，返回 (分类key, 输出字符串) 或 None（无效行）"""
    line = line.strip()
    if not line:
        return None
    access_token_match = re.search(r'access_token=([^&]*)', line)
    openid_match = re.search(r'openid=([^&]*)', line)
    if not access_token_match or not openid_match:
        # 格式错误行，放入 invalid 分类
        return ('invalid', line)

    access_token = access_token_match.group(1)
    openid = openid_match.group(1)
    cookies = {
        'acctype': 'qc',
        'openid': openid,
        'access_token': access_token,
        'appid': '1106467070',
    }

    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response_text = response.text
    except Exception as e:
        # 请求失败，放入 error 分类
        return ('error', f"请求异常: {line} - {str(e)}")

    # 解析响应
    charac_name = re.search(r'charac_name=([^&]*)', response_text)
    charac_name = urllib.parse.unquote(charac_name.group(1)) if charac_name else "鉴权失败"
    level = re.search(r'level=([^&]*)', response_text)
    level = urllib.parse.unquote(level.group(1)) if level else "未知等级"
    is_online = '是' if re.search(r'is_online=1', response_text) else '否'
    tpp_score = None
    tpp_match = re.search(r'tppseasonsquadrating=([^&]*)', response_text)
    if tpp_match:
        try:
            tpp_score = float(tpp_match.group(1))
        except:
            pass
    history_highest = re.search(r'historyhighestranktimes=([^&]*)', response_text)
    history_highest = urllib.parse.unquote(history_highest.group(1)) if history_highest else "无"
    last_login = re.search(r'lastlogintime=([^&]*)', response_text)
    last_login = convert_timestamp(last_login.group(1)) if last_login else "未知时间"

    # 构建输出行（与原脚本一致）
    base_output = f"名字:{charac_name}---等级:{level}---段位:{get_segment_name(int(tpp_score)) if tpp_score else '未知'}---在线状态:{is_online}---最后登录时间:{last_login}---"
    token_part = f"access_token={access_token}&openid={openid}"
    if charac_name == "鉴权失败":
        output_line = base_output + token_part
        return ('change_password', output_line)

    if tpp_score == 1200.0:
        output_line = base_output + token_part
        return ('banned', output_line)
    if is_online == '是':
        output_line = base_output + f"历史印记:{history_highest}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
        return ('online', output_line)
    if 3200 <= tpp_score < 4200:
        output_line = base_output + f"历史印记:{history_highest}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
        return ('diamond_crown', output_line)
    if tpp_score >= 4200:
        output_line = base_output + f"历史印记:{history_highest}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
        return ('ace', output_line)
    if level.isdigit() and int(level) < 10:
        output_line = base_output + f"历史印记:{history_highest}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
        return ('level_under_10', output_line)
    # 普通号
    output_line = base_output + f"历史印记:{history_highest}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
    return ('normal', output_line)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
            raw_text = data.get('data', '')
        except:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'message': 'Invalid JSON'}).encode())
            return

        lines = raw_text.splitlines()
        total = len(lines)
        processed = 0
        categories = {
            'change_password': [],
            'banned': [],
            'online': [],
            'diamond_crown': [],
            'ace': [],
            'level_under_10': [],
            'normal': [],
            'invalid': [],
            'error': []
        }

        for line in lines:
            result = process_line(line)
            if result:
                cat, output = result
                categories[cat].append({'raw': line, 'output_line': output})
                processed += 1

        response = {
            'success': True,
            'total': total,
            'processed': processed,
            'categories': categories
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        # 处理预检请求（如果需要CORS）
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
