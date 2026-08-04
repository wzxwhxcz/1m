"""
实现 5 种匹配策略
"""
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter
import re

class SessionMatcher:
    def __init__(self):
        self.stored_sessions = {}  # user_id -> list of sessions
    
    def store_session(self, user_id: str, session_id: str, messages: List[Dict]):
        """存储完整会话"""
        if user_id not in self.stored_sessions:
            self.stored_sessions[user_id] = []
        
        self.stored_sessions[user_id].append({
            "session_id": session_id,
            "messages": messages,
            "timestamp": time.time(),
            "features": self._extract_features(messages)
        })
    
    def _extract_features(self, messages: List[Dict]) -> Dict:
        """提取会话特征"""
        features = {
            "imports": set(),
            "files": set(),
            "frameworks": set(),
            "first_msg_hash": None,
            "last_3_hash": None,
            "code_blocks": 0
        }
        
        all_text = ""
        for msg in messages:
            content = msg.get("content", "")
            all_text += content + " "
            
            # 提取 import 语句
            imports = re.findall(r'import .+ from [\'"](.+?)[\'"]', content)
            imports += re.findall(r'require\([\'"](.+?)[\'"]\)', content)
            features["imports"].update(imports)
            
            # 提取文件名
            files = re.findall(r'[\w-]+\.(js|jsx|py|ts|tsx|css)', content)
            features["files"].update(files)
            
            # 识别框架
            for framework in ["express", "react", "vue", "django", "flask", "pandas", "numpy"]:
                if framework in content.lower():
                    features["frameworks"].add(framework)
            
            # 统计代码块
            if "```" in content:
                features["code_blocks"] += content.count("```") // 2
        
        # 首条消息 hash
        if messages:
            features["first_msg_hash"] = hashlib.md5(
                messages[0].get("content", "").encode()
            ).hexdigest()
        
        # 最后 3 条消息 hash
        if len(messages) >= 3:
            last_3 = json.dumps([m.get("content", "") for m in messages[-3:]])
            features["last_3_hash"] = hashlib.md5(last_3.encode()).hexdigest()
        
        # 转换 set 为 list（便于 JSON 序列化）
        features["imports"] = list(features["imports"])
        features["files"] = list(features["files"])
        features["frameworks"] = list(features["frameworks"])
        
        return features
    
    def match_by_time_window(self, user_id: str, messages: List[Dict], 
                             window_seconds: int = 300) -> Tuple[str, float]:
        """策略1：时间窗口匹配"""
        if user_id not in self.stored_sessions:
            return None, 0.0
        
        current_time = time.time()
        candidates = []
        
        for session in self.stored_sessions[user_id]:
            time_diff = current_time - session["timestamp"]
            if time_diff <= window_seconds:
                # 在时间窗口内，评分基于时间接近度
                score = 1.0 - (time_diff / window_seconds)
                candidates.append((session["session_id"], score))
        
        if candidates:
            # 返回时间最近的
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0]
        
        return None, 0.0
    
    def match_by_anchor(self, user_id: str, messages: List[Dict]) -> Tuple[str, float]:
        """策略2：首尾锚点匹配"""
        if user_id not in self.stored_sessions:
            return None, 0.0
        
        features = self._extract_features(messages)
        best_match = None
        best_score = 0.0
        
        for session in self.stored_sessions[user_id]:
            score = 0.0
            
            # 首条消息匹配（权重 0.4）
            if features["first_msg_hash"] == session["features"]["first_msg_hash"]:
                score += 0.4
            
            # 最后 3 条消息匹配（权重 0.6）
            if features["last_3_hash"] and features["last_3_hash"] == session["features"]["last_3_hash"]:
                score += 0.6
            
            if score > best_score:
                best_score = score
                best_match = session["session_id"]
        
        return best_match, best_score
    
    def match_by_features(self, user_id: str, messages: List[Dict]) -> Tuple[str, float]:
        """策略3：项目特征匹配（Jaccard 相似度）"""
        if user_id not in self.stored_sessions:
            return None, 0.0
        
        features = self._extract_features(messages)
        best_match = None
        best_score = 0.0
        
        for session in self.stored_sessions[user_id]:
            stored_features = session["features"]
            
            # 计算各个特征的 Jaccard 相似度
            scores = []
            
            # imports 相似度
            imports_score = self._jaccard(
                set(features["imports"]),
                set(stored_features["imports"])
            )
            scores.append(imports_score * 0.4)  # 权重 0.4
            
            # files 相似度
            files_score = self._jaccard(
                set(features["files"]),
                set(stored_features["files"])
            )
            scores.append(files_score * 0.3)  # 权重 0.3
            
            # frameworks 相似度
            frameworks_score = self._jaccard(
                set(features["frameworks"]),
                set(stored_features["frameworks"])
            )
            scores.append(frameworks_score * 0.3)  # 权重 0.3
            
            total_score = sum(scores)
            
            if total_score > best_score:
                best_score = total_score
                best_match = session["session_id"]
        
        return best_match, best_score
    
    def match_by_vector(self, user_id: str, messages: List[Dict]) -> Tuple[str, float]:
        """策略4：语义向量匹配（简化版：用词频向量代替）"""
        if user_id not in self.stored_sessions:
            return None, 0.0
        
        # 构建当前消息的词频向量
        current_vector = self._build_word_vector(messages)
        
        best_match = None
        best_score = 0.0
        
        for session in self.stored_sessions[user_id]:
            stored_vector = self._build_word_vector(session["messages"])
            
            # 计算余弦相似度
            score = self._cosine_similarity(current_vector, stored_vector)
            
            if score > best_score:
                best_score = score
                best_match = session["session_id"]
        
        return best_match, best_score
    
    def match_by_hybrid(self, user_id: str, messages: List[Dict]) -> Tuple[str, float]:
        """策略5：混合评分"""
        if user_id not in self.stored_sessions:
            return None, 0.0
        
        # 获取各策略的评分
        time_match, time_score = self.match_by_time_window(user_id, messages)
        anchor_match, anchor_score = self.match_by_anchor(user_id, messages)
        feature_match, feature_score = self.match_by_features(user_id, messages)
        vector_match, vector_score = self.match_by_vector(user_id, messages)
        
        # 加权合并
        weights = {
            "time": 0.2,
            "anchor": 0.3,
            "feature": 0.3,
            "vector": 0.2
        }
        
        # 统计每个 session_id 的得分
        scores_by_session = {}
        
        for match, score, weight in [
            (time_match, time_score, weights["time"]),
            (anchor_match, anchor_score, weights["anchor"]),
            (feature_match, feature_score, weights["feature"]),
            (vector_match, vector_score, weights["vector"])
        ]:
            if match:
                scores_by_session[match] = scores_by_session.get(match, 0) + score * weight
        
        if scores_by_session:
            best_match = max(scores_by_session.items(), key=lambda x: x[1])
            return best_match
        
        return None, 0.0
    
    # 辅助方法
    def _jaccard(self, set1: set, set2: set) -> float:
        """Jaccard 相似度"""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def _build_word_vector(self, messages: List[Dict]) -> Counter:
        """构建词频向量"""
        words = []
        for msg in messages:
            content = msg.get("content", "").lower()
            # 简单分词（移除标点）
            content = re.sub(r'[^\w\s]', ' ', content)
            words.extend(content.split())
        return Counter(words)
    
    def _cosine_similarity(self, vec1: Counter, vec2: Counter) -> float:
        """余弦相似度"""
        # 找到共同的词
        common = set(vec1.keys()) & set(vec2.keys())
        
        if not common:
            return 0.0
        
        # 计算点积
        dot_product = sum(vec1[word] * vec2[word] for word in common)
        
        # 计算模长
        mag1 = sum(v**2 for v in vec1.values()) ** 0.5
        mag2 = sum(v**2 for v in vec2.values()) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)

def main():
    """测试匹配器"""
    matcher = SessionMatcher()
    
    # 存储一个会话
    messages = [
        {"role": "user", "content": "How do I use express and jsonwebtoken?"},
        {"role": "assistant", "content": "Here's how to use JWT with Express..."}
    ]
    
    matcher.store_session("user_1", "session_1", messages)
    
    # 测试匹配
    compressed = [
        {"role": "user", "content": "How do I use express?"}
    ]
    
    match_id, score = matcher.match_by_features("user_1", compressed)
    print(f"匹配结果: {match_id}, 得分: {score:.2f}")

if __name__ == "__main__":
    main()
