import requests
import re
import urllib.parse
import json
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler
import io

# 目标URL
GAME_API_URL = 'https://comm.aci.game.qq.com/main?game=cjm&area=2&partition=&platid=1&callback=17319072866313099&sCloudApiName=ams.gameattr.role&iAmsActivityId=https%3A%2F%2Fgp.qq.com%2Fact%2Fa20190421cdkey%2Findex_pc.html'

# 请求头
HEADERS = {
    'Host': 'comm.aci.game.qq.com',
    'Referer': 'https://gp.qq.com/'
}

# 段位映射函数
def get_segment_name(score):
    if score is None:
        return "未知段位"
    try:
        score = float(score)
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
    except (ValueError, TypeError):
        return "未知段位"

# 时间戳转换函数
def convert_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return "未知时间"

# 处理单行数据
def process_single_line(line):
    line = line.strip()
    if not line:
        return None, None
    
    # 提取token信息
    access_token_match = re.search(r'access_token=([^&\s]*)', line)
    openid_match = re.search(r'openid=([^&\s]*)', line)
    
    if not access_token_match or not openid_match:
        return 'invalid', {
            'raw': line,
            'output_line': f"【格式错误】--- {line}"
        }
    
    access_token = access_token_match.group(1)
    openid = openid_match.group(1)
    
    # 发送请求获取角色数据
    cookies = {
        'acctype': 'qc',
        'openid': openid,
        'access_token': access_token,
        'appid': '1106467070',
    }
    
    try:
        response = requests.get(GAME_API_URL, headers=HEADERS, cookies=cookies, timeout=8)
        response_text = response.text
        
        # 解析响应字段
        charac_name_match = re.search(r'charac_name=([^&]*)', response_text)
        charac_name = urllib.parse.unquote(charac_name_match.group(1)) if charac_name_match else "鉴权失败"
        
        level_match = re.search(r'level=([^&]*)', response_text)
        level = urllib.parse.unquote(level_match.group(1)) if level_match else "未知等级"
        
        is_online = '是' if re.search(r'is_online=1', response_text) else '否'
        
        # TPP段位分数
        tpp_score = None
        tpp_match = re.search(r'tppseasonsquadrating=([^&]*)', response_text)
        if tpp_match:
            try:
                tpp_score = float(tpp_match.group(1))
            except (ValueError, TypeError):
                pass
        
        # 历史最高段位
        history_highest_match = re.search(r'historyhighestranktimes=([^&]*)', response_text)
        history_highest = urllib.parse.unquote(history_highest_match.group(1)) if history_highest_match else "无"
        
        # 最后登录时间
        last_login_match = re.search(r'lastlogintime=([^&]*)', response_text)
        last_login = convert_timestamp(last_login_match.group(1)) if last_login_match else "未知时间"
        
        # 构建输出数据
        result_data = {
            'charac_name': charac_name,
            'level': level,
            'segment': get_segment_name(tpp_score),
            'tpp_score': tpp_score,
            'is_online': is_online,
            'history_highest': history_highest,
            'last_login': last_login,
            'access_token': access_token,
            'openid': openid,
            'raw': line
        }
        
        # 分类判断
        category = 'normal'
        
        if charac_name == "鉴权失败":
            category = 'change_password'
        elif tpp_score == 1200.0:
            category = 'banned'
        elif is_online == '是':
            category = 'online'
        elif tpp_score is not None and 3200 <= tpp_score < 4200:
            category = 'diamond_crown'
        elif tpp_score is not None and tpp_score >= 4200:
            category = 'ace'
        elif level.isdigit() and int(level) < 10:
            category = 'level_under_10'
        
        # 构建输出行
        if category == 'change_password':
            output_line = f"名字:{charac_name}---等级:{level}---段位:{result_data['segment']}---在线状态:{is_online}---最后登录时间:{last_login}---access_token={access_token}&openid={openid}"
        elif category == 'banned':
            output_line = f"名字:{charac_name}---等级:{level}---段位分数:1200.0---在线状态:{is_online}---最后登录时间:{last_login}---access_token={access_token}&openid={openid}"
        else:
            output_line = f"名字:{charac_name}---等级:{level}---段位:{result_data['segment']}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
        
        result_data['output_line'] = output_line
        
        return category, result_data
        
    except requests.Timeout:
        return 'error', {
            'raw': line,
            'output_line': f"【请求超时】--- {line}"
        }
    except requests.RequestException as e:
        return 'error', {
            'raw': line,
            'output_line': f"【网络错误】--- {line}"
        }
    except Exception as e:
        return 'error', {
            'raw': line,
            'output_line': f"【处理异常】--- {line}"
        }

# 读取请求体的辅助函数
def read_request_body(handler):
    """安全地读取请求体"""
    try:
        content_length = handler.headers.get('Content-Length')
        if content_length:
            length = int(content_length)
            # Vercel环境中需要使用handler.rfile正确读取
            return handler.rfile.read(length).decode('utf-8')
        return ''
    except Exception as e:
        print(f"读取请求体错误: {str(e)}", file=sys.stderr)
        return ''

# Vercel Serverless Handler
class handler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # 重写日志方法，输出到stderr以便在Vercel日志中查看
        print(f"{self.address_string()} - {format % args}", file=sys.stderr)
    
    def _send_cors_headers(self):
        """发送CORS响应头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()
        # 必须返回空响应体
        self.wfile.write(b'')
    
    def _send_json_response(self, data, status_code=200):
        """发送JSON响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._send_cors_headers()
        self.end_headers()
        
        # 确保所有数据都是可序列化的
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        self.wfile.write(json_str.encode('utf-8'))
    
    def do_POST(self):
        """处理POST请求"""
        try:
            # 读取请求体
            body_str = read_request_body(self)
            
            if not body_str:
                self._send_json_response({
                    'success': False,
                    'message': 'Empty request body'
                }, 400)
                return
            
            # 解析JSON
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError as e:
                self._send_json_response({
                    'success': False,
                    'message': f'Invalid JSON: {str(e)}'
                }, 400)
                return
            
            data_input = body.get('data', '')
            if not data_input:
                self._send_json_response({
                    'success': False,
                    'message': 'No data provided'
                }, 400)
                return
            
            # 解析输入数据（按行分割）
            lines = [line.strip() for line in data_input.split('\n') if line.strip()]
            total = len(lines)
            
            if total == 0:
                self._send_json_response({
                    'success': False,
                    'message': 'No valid data lines found'
                }, 400)
                return
            
            # 限制最大处理数量（Vercel免费版有10秒超时限制）
            max_lines = min(total, 30)  # 保守设置为30条，确保不超时
            lines = lines[:max_lines]
            
            # 并发处理
            results = {
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
            
            # 使用线程池并发处理
            with ThreadPoolExecutor(max_workers=3) as executor:  # 减少线程数避免资源竞争
                future_to_line = {executor.submit(process_single_line, line): line for line in lines}
                
                for future in as_completed(future_to_line):
                    category, data = future.result()
                    if category and data:
                        results[category].append(data)
            
            # 构建响应
            response = {
                'success': True,
                'total': total,
                'processed': len(lines),
                'limited': total > max_lines,
                'categories': results,
                'timestamp': datetime.now().isoformat()
            }
            
            self._send_json_response(response)
            
        except Exception as e:
            print(f"Server error: {str(e)}", file=sys.stderr)
            self._send_json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, 500)
    
    def do_GET(self):
        """处理GET请求"""
        self._send_json_response({
            'message': 'LB Data Filter API',
            'version': '1.0.0',
            'endpoints': {
                'POST /api/filter': 'Filter game account data',
                'GET /api/filter': 'API info'
            },
            'limits': {
                'max_lines_per_request': 30,
                'timeout_seconds': 10
            },
            'usage': 'Send POST request with JSON body: {"data": "access_token=xxx&openid=yyy\\n..."}'
        })
