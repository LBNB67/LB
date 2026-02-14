import requests
import re
import urllib.parse
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
import os

# 目标URL
url = 'https://comm.aci.game.qq.com/main?game=cjm&area=2&partition=&platid=1&callback=17319072866313099&sCloudApiName=ams.gameattr.role&iAmsActivityId=https%3A%2F%2Fgp.qq.com%2Fact%2Fa20190421cdkey%2Findex_pc.html'
# 请求头
headers = {
	'Host': 'comm.aci.game.qq.com',
	'Referer': 'https://gp.qq.com/'
}
# 文件路径配置
input_file_path = '/storage/emulated/0/数据/数据号.txt'
output_file_path = '/storage/emulated/0/数据/数据号过滤完成.txt'
banned_file_path = '/storage/emulated/0/数据/被封号.txt'
change_password_file_path = '/storage/emulated/0/数据/改密码.txt'
online_file_path = '/storage/emulated/0/数据/有人在线.txt'
diamond_crown_file_path = '/storage/emulated/0/数据/钻石-皇冠.txt'
ace_file_path = '/storage/emulated/0/数据/王牌号.txt'
level_under_10_file_path = '/storage/emulated/0/数据/10级以下.txt'


# 段位映射函数
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


# 时间戳转换函数
def convert_timestamp(timestamp):
	try:
		return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
	except ValueError:
		return "未知时间"


def process_line(line,
				 output_files,
				 output_lock,
				 banned_lock,
				 change_pwd_lock,
				 online_lock,
				 diamond_crown_lock,
				 ace_lock,
				 level_under_10_lock):
	line = line.strip()
	if not line:
		return
	# 提取token信息
	access_token_match = re.search(r'access_token=([^&]*)', line)
	openid_match = re.search(r'openid=([^&]*)', line)

	if not access_token_match or not openid_match:
		print("无效行：", line)
		return

	access_token = access_token_match.group(1)
	openid = openid_match.group(1)
	# 发送请求获取角色数据
	cookies = {
		'acctype': 'qc',
		'openid': openid,
		'access_token': access_token,
		'appid': '1106467070',
	}
	response = requests.get(url, headers=headers, cookies=cookies)
	response_text = response.text
	# 解析响应字段
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
	# 实时输出处理信息
	print(f"[{datetime.now()}] 处理角色：{charac_name}")
	print(f"等级：{level} | 段位：{get_segment_name(int(tpp_score)) if tpp_score else '未知'} | 在线：{is_online}")
	print(f"最后登录：{last_login}\n{'-' * 20}")
	# 分类写入文件
	if charac_name == "鉴权失败":
		with change_pwd_lock:
			output_files['change_password'].write(
				f"名字:{charac_name}---等级:{level}---段位:{get_segment_name(int(tpp_score)) if tpp_score else '未知'}---在线状态:{is_online}---最后登录时间:{last_login}---access_token={access_token}&openid={openid}\n")
			output_files['change_password'].flush()
	else:
		if tpp_score == 1200.0:
			with banned_lock:
				output_files['banned'].write(
					f"名字:{charac_name}---等级:{level}---段位分数:1200.0---在线状态:{is_online}---最后登录时间:{last_login}---access_token={access_token}&openid={openid}\n")
				output_files['banned'].flush()
		elif is_online == '是':
			with online_lock:
				output_files['online'].write(
					f"名字:{charac_name}---等级:{level}---段位:{get_segment_name(int(tpp_score)) if tpp_score else '未知'}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&\n")
				output_files['online'].flush()
		else:
			if 3200 <= tpp_score < 4200:
				with diamond_crown_lock:
					output_files['diamond_crown'].write(
						f"名字:{charac_name}---等级:{level}---段位:{get_segment_name(int(tpp_score)) if tpp_score else '未知'}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&\n")
					output_files['diamond_crown'].flush()
			elif tpp_score >= 4200:
				with ace_lock:
					output_files['ace'].write(
						f"名字:{charac_name}---等级:{level}---段位:{get_segment_name(int(tpp_score)) if tpp_score else '未知'}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&\n")
					output_files['ace'].flush()
			elif level.isdigit() and int(level) < 10:
				with level_under_10_lock:
					output_files['level_under_10'].write(
						f"名字:{charac_name}---等级:{level}---段位:{get_segment_name(int(tpp_score)) if tpp_score else '未知'}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&\n")
					output_files['level_under_10'].flush()
			else:
				with output_lock:
					output_files['output'].write(
						f"名字:{charac_name}---等级:{level}---段位:{get_segment_name(int(tpp_score)) if tpp_score else '未知'}---历史印记:{history_highest}---在线状态:{is_online}---最后登录时间:{last_login}---正常_access_token={access_token}&expires_in=5184000&openid={openid}&pay_token=999&\n")
					output_files['output'].flush()


# 主程序入口
if __name__ == "__main__":
	file_paths = [
		output_file_path,
		banned_file_path,
		change_password_file_path,
		online_file_path,
		diamond_crown_file_path,
		ace_file_path,
		level_under_10_file_path
	]
	for path in file_paths:
		if not os.path.exists(path):
			open(path, 'w').close()
	# 初始化文件句柄和锁
	output_files = {
		'output': open(output_file_path, 'a+', encoding='utf-8'),
		'banned': open(banned_file_path, 'a+', encoding='utf-8'),
		'change_password': open(change_password_file_path, 'a+', encoding='utf-8'),
		'online': open(online_file_path, 'a+', encoding='utf-8'),
		'diamond_crown': open(diamond_crown_file_path, 'a+', encoding='utf-8'),
		'ace': open(ace_file_path, 'a+', encoding='utf-8'),
		'level_under_10': open(level_under_10_file_path, 'a+', encoding='utf-8')
	}
	# 创建独立锁对象
	output_lock = threading.Lock()
	banned_lock = threading.Lock()
	change_pwd_lock = threading.Lock()
	online_lock = threading.Lock()
	diamond_crown_lock = threading.Lock()
	ace_lock = threading.Lock()
	level_under_10_lock = threading.Lock()
	# 多线程处理
	with ThreadPoolExecutor(max_workers=10) as executor:
		for line in open(input_file_path, 'r', encoding='utf-8'):
			if not line.strip():
				continue
			executor.submit(process_line, line, output_files, output_lock, banned_lock, change_pwd_lock, online_lock,
							diamond_crown_lock, ace_lock, level_under_10_lock)
	# 关闭文件
	for f in output_files.values():
		f.close()
	print("所有数据处理完成！")