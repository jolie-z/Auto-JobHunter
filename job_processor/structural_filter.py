import json
import os
import re

class StructuralFilterEngine:
    def __init__(self, config_path="rule_config.json"):
        self.config_path = config_path
        self.reject_titles = []
        self.reject_experience = []
        self.reject_education = []
        self.load_config()

    def load_config(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        abs_path = os.path.join(current_dir, self.config_path)
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            rules = config_data.get("coarse_filter_rules", {})
            self.reject_titles = rules.get("reject_titles", [])
            self.reject_experience = rules.get("reject_experience", [])
            self.reject_education = rules.get("reject_education", [])
        except Exception as e:
            print(f"⚠️ 读取粗筛配置失败: {e}")

    def is_obvious_garbage(self, job_title, experience_req, education_req) -> tuple[bool, str]:
        """
        判断是否为明显的垃圾岗位
        返回: (是否是垃圾岗位, 淘汰原因)
        """
        title = str(job_title).lower() if job_title else ""
        exp = str(experience_req) if experience_req else ""
        edu = str(education_req) if education_req else ""

        # 1. 标题粗筛
        for word in self.reject_titles:
            if word.lower() in title:
                return True, f"标题包含排除词: {word}"

        # 2. 经验粗筛
        for word in self.reject_experience:
            if word in exp:
                return True, f"经验要求不符: {word}"

        # 3. 学历粗筛
        for word in self.reject_education:
            if word in edu:
                return True, f"学历要求不符: {word}"

        return False, ""
