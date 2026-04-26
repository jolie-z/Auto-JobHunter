import subprocess
import yaml
import time

def fetch_job_detail(security_id, retry_count=1, on_captcha_callback=None):
    """单点爆破获取完整岗位详情，带有全自动机械臂防封抢救机制"""
    try:
        result = subprocess.run(["boss", "detail", "--", security_id], capture_output=True, text=True)
        
        if result.returncode != 0 and "__zp_stoken__" in result.stderr:
            if retry_count > 0:
                print("      🚨 警报：安全码失效！Boss 正在怀疑你是机器人！")
                if on_captcha_callback:
                    print("      🤖 正在呼叫 Mac 机械臂，全自动执行页面刷新与行为伪装...")
                    on_captcha_callback() 
                else:
                    print("      👉 请立刻看一眼你的 Edge 浏览器，随便点几下...")
                    time.sleep(20) 
                
                #print("      🔄 伪装完毕，正在强行重新提取最新通行证...")
                #subprocess.run(["boss", "login", "--cookie-source", "edge"], capture_output=True)
                
                #print("      🔄 尝试重新抓取该岗位详情...")
                return fetch_job_detail(security_id, retry_count=0, on_captcha_callback=on_captcha_callback) 
            else:
                print(f"      ❌ 抢救失败，放弃该岗位。")
                # 🌟 修复：原来是 3 个 None，现在补上第四个空字典 {}
                return None, None, None, {}

        if result.returncode != 0:
            print(f"      ❌ 获取详情失败: {result.stderr.strip()}")
            # 🌟 修复
            return None, None, None, {}

        try:
            parsed_data = yaml.safe_load(result.stdout)
        except yaml.YAMLError:
            print("      ⚠️ 详情解析异常，跳过此岗位。")
            # 🌟 修复
            return None, None, None, {}

        data_block = parsed_data.get('data', {})
        job_info = data_block.get('jobInfo', {})
        boss_info = data_block.get('bossInfo', {})
        brand_com_info = data_block.get('brandComInfo', {})
        
        full_desc = job_info.get('postDescription', '无详细描述')
        address = job_info.get('address', '地址未提供')
        real_link_id = job_info.get('encryptId', security_id) 
        
        # 新增的 7 大数据维度
        extra_info = {
            "hr_active": boss_info.get("activeTimeDesc", "未知"),
            "industry": brand_com_info.get("industryName", "未知"),
            "welfare": ", ".join(brand_com_info.get("labels", [])),
            "scale": brand_com_info.get("scaleName", "未知"),
            "degree": job_info.get("degreeName", "未知"),
            "experience": job_info.get("experienceName", "未知"),
            "hr_skills": ", ".join(job_info.get("showSkills", []))
        }
        
        return full_desc, address, real_link_id, extra_info
        
    except Exception as e:
        print(f"      ⚠️ 抓取详情时发生内部错误: {e}")
        # 🌟 修复
        return None, None, None, {}

def is_toxic_job(job_title, full_desc, row_dict, blacklist):
    """黑名单扫描引擎"""
    if not blacklist:
        return False, ""
    
    all_raw_tags = " ".join(str(v) for v in row_dict.values())
    combined_text = (str(job_title) + " " + str(full_desc) + " " + all_raw_tags).lower()
    
    for bad_word in blacklist:
        if str(bad_word).lower() in combined_text:
            return True, bad_word 
    return False, ""