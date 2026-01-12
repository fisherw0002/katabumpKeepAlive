#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests
from datetime import datetime, timezone, timedelta

# ================= 配置区 =================
DASHBOARD_URL = 'https://dashboard.katabump.com'
SERVER_ID = os.environ.get('KATA_SERVER_ID', '201692')
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_USER_ID', '') 

def log(msg):
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')

def run():
    log(f'🚀 开始 Debug 运行 - 目标 ID: {SERVER_ID}')
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    
    try:
        # 1. 登录
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30)
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={'email': KATA_EMAIL, 'password': KATA_PASSWORD, 'remember': 'true'},
            timeout=30
        )
        if '/auth/login' in login_resp.url:
            log("❌ 登录失败，请检查账号密码")
            return

        # 2. 暴力抓取页面源码
        target_page = f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}'
        server_page = session.get(target_page, timeout=30)
        html = server_page.text

        log("="*30 + " DEBUG START " + "="*30)
        # 截取网页中间最有可能是信息区域的部分 (通常在 5000 到 8000 字符之间)
        start_pos = 5000 
        end_pos = 9000
        if len(html) > start_pos:
            log(f"--- 核心 HTML 片段 (Length: {len(html)}) ---")
            print(html[start_pos:end_pos])
        else:
            log("--- 网页内容过短，完整输出 ---")
            print(html)
        log("="*30 + " DEBUG END " + "="*30)

        # 3. 顺便执行一次续订尝试
        csrf_m = re.search(r'name=["\']csrf["\'][^>]*value=["\']([^"\']+)["\']', html)
        csrf_token = csrf_m.group(1) if csrf_m else None
        
        api_resp = session.post(
            f'{DASHBOARD_URL}/api-client/renew?id={SERVER_ID}',
            data={'csrf': csrf_token} if csrf_token else {},
            headers={'Referer': target_page},
            timeout=30, allow_redirects=False
        )
        log(f"ℹ️ 续订请求状态码: {api_resp.status_code}")

    except Exception as e:
        log(f'❌ 运行报错: {e}')

if __name__ == '__main__':
    run()
