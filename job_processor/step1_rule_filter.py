import sqlite3
import re
import json
import os
import datetime

# ================= 1. 评分引擎 =================
class JDScoringEngine:
    def __init__(self, config_path="rule_config.json"):
        self.config_path = config_path
        self.safe_phrases = []
        self.veto_keywords = []
        self.positive_keywords = {}
        self.negative_keywords = {}
        self.title_veto_words = []
        self.title_positive_words = {}
        self.title_negative_words = {}
        self.load_config()

    def load_config(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        abs_path = os.path.join(current_dir, self.config_path)
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            self.safe_phrases = config_data.get("safe_phrases", [])
            self.veto_keywords = config_data.get("veto_keywords", [])
            self.positive_keywords = config_data.get("positive_keywords", {})
            self.negative_keywords = config_data.get("negative_keywords", {})
            self.title_veto_words = config_data.get("title_veto_words", [])
            self.title_positive_words = config_data.get("title_positive_words", {})
            self.title_negative_words = config_data.get("title_negative_words", {})
        except Exception as e:
            print(f"❌ 读取配置失败: {e}")

    def parse_publish_date(self, date_str):
        if not date_str:
            return None
        date_str = str(date_str).strip()
        today = datetime.date.today()
        
        if "今天" in date_str or "刚刚" in date_str:
            return today
            
        m1 = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if m1:
            return datetime.date(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)))
            
        m2 = re.search(r'(\d{1,2})月(\d{1,2})日', date_str)
        if m2:
            month = int(m2.group(1))
            day = int(m2.group(2))
            year = today.year if month <= today.month else today.year - 1
            try:
                return datetime.date(year, month, day)
            except ValueError:
                return None
        return None

    def evaluate_job(self, job_title, jd_text, hr_activity, publish_date):
        job_title = str(job_title) if job_title else ""
        jd_text = str(jd_text) if jd_text else ""
        hr_activity = str(hr_activity).strip() if hr_activity else ""
        publish_date = str(publish_date).strip() if publish_date else ""

        title_lower = job_title.lower()
        text_lower = jd_text.lower()
        
        result = {"status": "PASS", "total_score": 0, "matched_positive": {}, "matched_negative": {}, "reject_reason": None}
        
        # --- 1. 时间漏斗筛查 ---
        if hr_activity:
            if '半年' in hr_activity or '3月' in hr_activity:
                return {"status": "REJECT", "total_score": -999, "matched_positive": {}, "matched_negative": {}, "reject_reason": f"HR长期未活跃({hr_activity})"}
            elif '2月' in hr_activity:
                result["total_score"] -= 10
                result["matched_negative"][f"[活跃度]{hr_activity}"] = -10
            elif '1月' in hr_activity:
                result["total_score"] -= 5
                result["matched_negative"][f"[活跃度]{hr_activity}"] = -5

        if publish_date:
            parsed_date = self.parse_publish_date(publish_date)
            if parsed_date:
                delta_days = (datetime.date.today() - parsed_date).days
                if delta_days > 180:
                    return {"status": "REJECT", "total_score": -999, "matched_positive": {}, "matched_negative": {}, "reject_reason": f"发布时间超过半年({publish_date})"}
                elif delta_days > 90:
                    result["total_score"] -= 15
                    result["matched_negative"][f"[时间]{publish_date}(超3个月)"] = -15
                elif delta_days > 60:
                    result["total_score"] -= 10
                    result["matched_negative"][f"[时间]{publish_date}(超2个月)"] = -10
                elif delta_days > 30:
                    result["total_score"] -= 5
                    result["matched_negative"][f"[时间]{publish_date}(超1个月)"] = -5

        # --- 2. 标题检测 ---
        for word in self.title_veto_words:
            if word.lower() in title_lower:
                return {"status": "REJECT", "total_score": -999, "matched_positive": {}, "matched_negative": {}, "reject_reason": f"岗位名称一票否决: {word}"}
        for word, score in self.title_positive_words.items():
            if word.lower() in title_lower:
                result["total_score"] += score
                result["matched_positive"][f"[标题]{word}"] = score
        for word, score in self.title_negative_words.items():
            if word.lower() in title_lower:
                result["total_score"] += score
                result["matched_negative"][f"[标题]{word}"] = score

        # --- 3. JD 检测 (挖空安全词) ---
        jd_for_veto_check = text_lower
        sorted_safe_phrases = sorted(self.safe_phrases, key=len, reverse=True)
        for safe_phrase in sorted_safe_phrases:
            jd_for_veto_check = jd_for_veto_check.replace(safe_phrase.lower(), " ")

        for word in self.veto_keywords:
            if word.lower() in jd_for_veto_check:
                return {"status": "REJECT", "total_score": -999, "matched_positive": {}, "matched_negative": {}, "reject_reason": f"JD一票否决: {word}"}
                
        for word, score in self.positive_keywords.items():
            if word.lower() in text_lower:
                result["total_score"] += score
                result["matched_positive"][f"[JD]{word}"] = score
        for word, score in self.negative_keywords.items():
            if word.lower() in text_lower:
                result["total_score"] += score
                result["matched_negative"][f"[JD]{word}"] = score
                
        if result["total_score"] < 0:
            result["status"] = "REJECT"
            result["reject_reason"] = "综合得分低于0分"
        elif not result["matched_positive"] and not result["matched_negative"]:
            result["status"] = "REJECT"
            result["reject_reason"] = "未命中任何关键词"
            
        return result

# ================= 2. 数据清洗专项 =================

def is_salary_rejected(salary_str, min_k=10, max_k=25):
    if not salary_str or str(salary_str).strip() in ('', 'None', 'nan', '面议', '薪资面议'):
        return False
    salary_str = str(salary_str).lower().replace(' ', '')
    if '元/天' in salary_str or '/天' in salary_str:
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', salary_str)
        if matches:
            if float(matches[0][0]) * 22 / 1000 > max_k or float(matches[0][1]) * 22 / 1000 < min_k: return True
        return False
    if '万/年' in salary_str or '万元/年' in salary_str:
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', salary_str)
        if matches:
            if float(matches[0][0]) * 10 / 12 > max_k or float(matches[0][1]) * 10 / 12 < min_k: return True
        return False
    matches = re.search(r'(\d+(?:\.\d+)?)(千|万|k)?[-至~]+(\d+(?:\.\d+)?)(千|万|k|元)?', salary_str)
    if matches:
        min_val, min_unit, max_val, max_unit = float(matches.group(1)), matches.group(2), float(matches.group(3)), matches.group(4)
        max_sal = max_val / 1000 if max_unit == '元' or (not max_unit and max_val >= 1000) else max_val * 10 if max_unit == '万' else max_val
        min_sal = min_val * 10 if min_unit == '万' else min_val if min_unit in ('k', '千') else (min_val * 10 if max_unit == '万' and min_val < 100 else min_val if max_unit in ('k', '千') and min_val < 1000 else min_val / 1000 if (max_unit == '元' or max_val >= 1000) and min_val >= 1000 else min_val)
        if min_sal > max_k or max_sal < min_k: return True
    return False

# ================= 修订：资历拦截函数 =================
def is_experience_rejected(exp_req, jd_text, max_years=7):
    """
    向上拦截：拒绝要求 >= max_years 经验的岗位。
    保留 3-5年、5年以上、5-10年 等岗位。
    """
    # 1. 检查官方字段 (experience_req)
    if exp_req and str(exp_req).strip() not in ('', 'None', 'nan', '不限', '经验不限'):
        exp_str = str(exp_req).replace(' ', '')
        
        # 匹配 "X-Y年" (例如 "7-10年")
        range_match = re.search(r'(\d+)-(\d+)年', exp_str)
        if range_match and int(range_match.group(1)) >= max_years:
            return True
            
        # 匹配 "X年以上" / "X年及以上" (例如 "8年以上")
        up_match = re.search(r'(\d+)年(?:及)?以上', exp_str)
        if up_match and int(up_match.group(1)) >= max_years:
            return True

    # 2. 检查 JD 详情内容 (提取年限数字后与阈值比对)
    if jd_text:
        text = str(jd_text).replace(' ', '')
        for pattern in [
            r'(?:要求|需要|具备).{0,5}(\d+)年(?:及)?以上.*经验',
            r'(\d+)年(?:及)?以上(?:的)?(?:相关)?(?:工作|项目|团队管理)经验',
            r'(\d+)-(?:\d+)年(?:的)?(?:相关)?(?:工作|项目)经验',
        ]:
            m = re.search(pattern, text)
            if m and int(m.group(1)) >= max_years:
                return True
            
    return False

# ================= 3. 核心流转逻辑 =================
def run_pipeline():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    abs_db_path = os.path.join(parent_dir, "data", "job_hunter.db")
    
    allowed_cities = []
    min_salary_k = 10
    max_salary_k = 25
    experience_years_threshold = 7
    try:
        with open(os.path.join(current_dir, "rule_config.json"), 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            allowed_cities = cfg.get("allowed_cities", [])
            coarse = cfg.get("coarse_filter_rules", {})
            min_salary_k = coarse.get("min_salary_threshold_k", 10)
            max_salary_k = coarse.get("max_salary_threshold_k", 25)
            experience_years_threshold = coarse.get("experience_years_threshold", 7)
    except: pass
    
    conn = sqlite3.connect(abs_db_path)
    cursor = conn.cursor()
    
    print("🧹 [阶段一] 执行数据清洗...")
    if allowed_cities:
        city_not_like = " AND ".join([f"IFNULL(city, '') NOT LIKE '%{c}%'" for c in allowed_cities])
        address_not_like = " AND ".join([f"IFNULL(work_address, '') NOT LIKE '%{c}%'" for c in allowed_cities])
        cursor.execute(f"UPDATE raw_jobs SET process_status = '清洗淘汰', reject_reason = '工作城市不在目标范围内' WHERE process_status = '已存入数据' AND ({city_not_like}) AND ({address_not_like})")
    
    cursor.execute("UPDATE raw_jobs SET publish_date = REPLACE(publish_date, '更新于 ', '') WHERE platform = '智联招聘'")
    cursor.execute("UPDATE raw_jobs SET process_status = '清洗淘汰', reject_reason = '岗位详情为空' WHERE process_status = '已存入数据' AND (jd_text IS NULL OR TRIM(jd_text) = '')")
    cursor.execute("UPDATE raw_jobs SET process_status = '清洗淘汰', reject_reason = '经验要求不符(应届/在校)' WHERE process_status = '已存入数据' AND (experience_req LIKE '%在校%' OR experience_req LIKE '%应届%')")
    cursor.execute("UPDATE raw_jobs SET process_status = '清洗淘汰', reject_reason = '学历要求不符(高中/中专/中技)' WHERE process_status = '已存入数据' AND (education_req LIKE '%高中%' OR education_req LIKE '%中专%' OR education_req LIKE '%中技%')")
    
    # 执行资历向上拦截 (拦截 7年以上)
    cursor.execute("SELECT job_link, experience_req, jd_text FROM raw_jobs WHERE process_status = '已存入数据'")
    exp_rejects = [(lk,) for lk, exp, jd in cursor.fetchall() if is_experience_rejected(exp, jd, experience_years_threshold)]
    if exp_rejects: 
        cursor.executemany(f"UPDATE raw_jobs SET process_status = '清洗淘汰', reject_reason = '要求资历过高(≥{experience_years_threshold}年)' WHERE job_link = ?", exp_rejects)
        print(f"🚫 资历拦截：已淘汰 {len(exp_rejects)} 个要求过高的岗位。")

    # 执行薪资清洗
    cursor.execute("SELECT job_link, salary FROM raw_jobs WHERE process_status = '已存入数据'")
    salary_rejects = [(lk,) for lk, sal in cursor.fetchall() if is_salary_rejected(sal, min_salary_k, max_salary_k)]
    if salary_rejects: 
        cursor.executemany(f"UPDATE raw_jobs SET process_status = '清洗淘汰', reject_reason = '薪资区间不符(最低>{max_salary_k}k或最高<{min_salary_k}k)' WHERE job_link = ?", salary_rejects)

    cursor.execute("UPDATE raw_jobs SET process_status = '待打分' WHERE process_status = '已存入数据'")
    conn.commit()
    
    print("🤖 [阶段二] 开始执行关键词与时间联合评分...")
    engine = JDScoringEngine("rule_config.json")
    cursor.execute("SELECT job_link, job_title, jd_text, hr_activity, publish_date FROM raw_jobs WHERE process_status = '待打分'")
    
    update_data = []
    for job_link, job_title, jd_text, hr_activity, publish_date in cursor.fetchall():
        res = engine.evaluate_job(job_title, jd_text, hr_activity, publish_date)
        pos_str = ", ".join([f"{k}(+{v})" for k, v in res['matched_positive'].items()])
        neg_str = ", ".join([f"{k}({v})" for k, v in res['matched_negative'].items()])
        update_data.append(('已进行打分', res['status'], res['total_score'], pos_str, neg_str, res['reject_reason'], job_link))
    
    if update_data:
        cursor.executemany("UPDATE raw_jobs SET process_status = ?, keywords_status = ?, keywords_score = ?, positive_hits = ?, negative_hits = ?, reject_reason = ? WHERE job_link = ?", update_data)
        conn.commit()
        print(f"🎉 处理完成！本轮共对 {len(update_data)} 条岗位进行了深度打分。")

    conn.close()

if __name__ == "__main__":
    run_pipeline()