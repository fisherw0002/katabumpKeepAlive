#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests
from datetime import datetime, timezone, timedelta

# ================= 变量加载区 (修复重点) =================
DASHBOARD_URL = 'https://dashboard.katabump.com'
# 确保从环境变量精准读取
KATA_EMAIL = os.environ.get('KATA_EMAIL', '').strip()
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '').strip()
SERVER_ID = os.environ.get('KATA_SERVER_ID', '201692').strip()

def log(msg):
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')

def run():
    log(f'🚀 开始 Debug 运行 - 目标 ID: {SERVER_ID}')
    
    if not KATA_EMAIL or not KATA_PASSWORD:
        log("❌ 错误：环境变量 KATA_EMAIL 或 KATA_PASSWORD 为空，请检查 GitHub Secrets 配置！")
        return

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    
    try:
        # 1. 模拟登录 (使用你最初成功的逻辑)
        log('🔐 正在尝试登录...')
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30)
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={'email': KATA_EMAIL, 'password': KATA_PASSWORD, 'remember': 'true'},
            headers={'Referer': f'{DASHBOARD_URL}/auth/login'},
            timeout=30,
            allow_redirects=True
        )
        
        # 验证登录是否重定向（即成功）
        if '/auth/login' in login_resp.url:
            log(f"❌ 登录失败！页面未跳转。当前 URL: {login_resp.url}")
            return
        log('✅ 登录成功')

        # 2. 暴力抓取页面源码
        target_page = f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}'
        server_page = session.get(target_page, timeout=30)
        html = server_page.text

        log("="*30 + " [DEBUG START] " + "="*30)
        # 扩大搜索范围，寻找包含 "2026" 或 "Expiry" 的片段
        # 我们直接打印网页 body 之后的一大段内容
        if len(html) > 2000:
            # 尝试定位到表格或面板所在的中间区域
            start_point = html.find('<body')
            if start_point == -1: start_point = 0
            log(f"--- 核心 HTML 源码输出 (起始位置: {start_point}) ---")
            # 打印 4000 个字符确保覆盖日期
            print(html[start_point : start_point + 5000])
        else:
            log("--- 网页内容过短，完整输出 ---")
            print(html)
        log("="*30 + " [DEBUG END] " + "="*30)

    except Exception as e:
        log(f'❌ 运行过程报错: {e}')

if __name__ == '__main__':
    run()
