from flask import Flask, request, jsonify
import requests
import re
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# 目标URL
TARGET_URL = 'https://comm.aci.game.qq.com/main?game=cjm&area=2&partition=&platid=1&callback=17319072866313099&sCloudApiName=ams.gameattr.role&iAmsActivityId=https%3A%2F%2Fgp.qq.com%2Fact%2Fa20190421cdkey%2Findex_pc.html'

# 请求头
HEADERS = {
    'Host': 'comm.aci.game.qq.com',
    'Referer': 'https://gp.qq.com/'
}

# 段位映射函数
def get_segment_name(score):
    if score is None:
        return "未知段位"
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

# 时间戳转换函数
def convert_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return "未知时间"

def extract_tokens(text):
    """从文本中提取所有access_token和openid"""
    lines = []
    # 匹配 access_token=xxx&openid=xxx 格式
    pattern = r'access_token=([a-zA-Z0-9_-]+)[^&]*&openid=([a-zA-Z0-9_-]+)'
    matches = re.findall(pattern, text)
    
    for access_token, openid in matches:
        lines.append(f"access_token={access_token}&openid={openid}")
    
    return lines

def process_single_line(line):
    """处理单行数据"""
    line = line.strip()
    if not line:
        return None

    # 提取token
    access_token_match = re.search(r'access_token=([^&]*)', line)
    openid_match = re.search(r'openid=([^&]*)', line)
    
    if not access_token_match or not openid_match:
        return {
            "error": "格式错误",
            "raw": line,
            "category": "invalid",
            "category_name": "格式错误",
            "output_line": f"格式错误---{line}"
        }

    access_token = access_token_match.group(1)
    openid = openid_match.group(1)
    
    cookies = {
        'acctype': 'qc',
        'openid': openid,
        'access_token': access_token,
        'appid': '1106467070',
    }
    
    try:
        resp = requests.get(TARGET_URL, headers=HEADERS, cookies=cookies, timeout=10)
        text = resp.text
        
        # 解析字段
        def get_param(key):
            match = re.search(rf'{key}=([^&]*)', text)
            return urllib.parse.unquote(match.group(1)) if match else None
        
        charac_name = get_param('charac_name') or "鉴权失败"
        level = get_param('level') or "未知等级"
        is_online = '是' if 'is_online=1' in text else '否'
        
        # 段位分数
        tpp_score = None
        tpp_match = re.search(r'tppseasonsquadrating=([^&]*)', text)
        if tpp_match:
            try:
                tpp_score = float(tpp_match.group(1))
            except:
                pass
        
        history_highest = get_param('historyhighestranktimes') or "无"
        last_login_raw = get_param('lastlogintime')
        last_login = convert_timestamp(last_login_raw) if last_login_raw else "未知时间"
        
        segment = get_segment_name(tpp_score)
        
        # 构建结果对象
        result = {
            "name": charac_name,
            "level": level,
            "segment": segment,
            "segment_score": tpp_score,
            "is_online": is_online,
            "history_highest": history_highest,
            "last_login": last_login,
            "access_token": access_token,
            "openid": openid,
            "raw": line
        }
        
        # 分类逻辑（严格按照你的Python代码）
        if charac_name == "鉴权失败":
            result["category"] = "change_password"
            result["category_name"] = "改密码"
            result["output_line"] = f"名字:{charac_name}---等级:{level}---段位:{segment}---在线状态:{is_online}---最后登录时间:{last_login}---access_token={access_token}&openid={openid}"
            
        elif tpp_score == 1200.0:
            result["category"] = "banned"
            result["category_name"] = "被封号"
            result["output_line"] = f"名字:{charac_name}---等级:{level}---段位分数:1200.0---在线状态:{is_online}---最后登录时间:{last_login}---access_token={access_token}&openid={openid}"
            
        elif is_online == '是':
            result["category"] = "online"
            result["category_name"] = "有人在线"
            result["output_line"] = f"名字:{charac_name}---等级:{level}---段位:{segment}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
            
        elif tpp_score is not None and 3200 <= tpp_score < 4200:
            result["category"] = "diamond_crown"
            result["category_name"] = "钻石-皇冠"
            result["output_line"] = f"名字:{charac_name}---等级:{level}---段位:{segment}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
            
        elif tpp_score is not None and tpp_score >= 4200:
            result["category"] = "ace"
            result["category_name"] = "王牌号"
            result["output_line"] = f"名字:{charac_name}---等级:{level}---段位:{segment}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
            
        elif level.isdigit() and int(level) < 10:
            result["category"] = "level_under_10"
            result["category_name"] = "10级以下"
            result["output_line"] = f"名字:{charac_name}---等级:{level}---段位:{segment}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
            
        else:
            result["category"] = "normal"
            result["category_name"] = "普通号"
            result["output_line"] = f"名字:{charac_name}---等级:{level}---段位:{segment}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&"
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "raw": line,
            "category": "error",
            "category_name": "请求失败",
            "output_line": f"请求失败---{line}"
        }

@app.route('/api/filter', methods=['POST'])
def filter_accounts():
    """主过滤接口"""
    data = request.get_json()
    input_text = data.get('data', '')
    
    # 提取所有token行
    lines = extract_tokens(input_text)
    
    if not lines:
        return jsonify({
            "success": False,
            "message": "未找到有效的access_token和openid",
            "total": 0,
            "processed": 0,
            "categories": {}
        })
    
    # 并发处理 (10线程)
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_line = {executor.submit(process_single_line, line): line for line in lines}
        for future in as_completed(future_to_line):
            result = future.result()
            if result:
                results.append(result)
    
    # 按分类汇总
    categories = {
        "change_password": [],
        "banned": [],
        "online": [],
        "diamond_crown": [],
        "ace": [],
        "level_under_10": [],
        "normal": [],
        "invalid": [],
        "error": []
    }
    
    for r in results:
        cat = r.get("category", "normal")
        if cat in categories:
            categories[cat].append(r)
    
    return jsonify({
        "success": True,
        "total": len(lines),
        "processed": len(results),
        "categories": categories
    })

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "API is running"})

# Vercel 入口
if __name__ == '__main__':
    app=app
