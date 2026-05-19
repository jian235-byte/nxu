"""
AI智能体 - 带自动历史压缩版本
"""
import os
import json
import time
import sys

# 不使用requests，用内置的urllib
try:
    from urllib import request
    import urllib.error
except ImportError:
    import urllib.request as request
    import urllib.error

class SimpleAgent:
    """带自动历史压缩的AI智能体"""
    
    def __init__(self):
        # 直接从环境变量或硬编码配置
        self.base_url = self.get_env("LLM_BASE_URL", "http://localhost:1234/v1")
        self.model = self.get_env("LLM_MODEL", "local-model")
        self.api_key = self.get_env("LLM_API_KEY", "lm-studio")
        
        # 对话历史
        self.history = []
        self.summaries = []  # 存储压缩后的摘要
        
        # 历史管理配置
        self.max_history_rounds = 5  # 最大对话轮数
        self.max_context_tokens = 3000  # 最大上下文token数
        self.summary_threshold = 0.7  # 压缩前70%的内容
        
        print("=" * 50)
        print("🤖 AI智能体 (带自动压缩)")
        print(f"   模型: {self.model}")
        print(f"   地址: {self.base_url}")
        print(f"   自动压缩: 超过{self.max_history_rounds}轮或{self.max_context_tokens}tokens")
        print("=" * 50)
    
    def get_env(self, key, default):
        """获取环境变量"""
        try:
            if os.path.exists(".env"):
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == key:
                                return v.strip()
        except:
            pass
        
        return os.environ.get(key, default)
    
    def estimate_tokens(self, text):
        """估算token数量（更准确的方法）"""
        if not text:
            return 0
            
        # 中文字符通常算1-2个token，英文字符算0.25-0.5个
        chinese_count = 0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                chinese_count += 1
        
        english_count = len(text) - chinese_count
        
        # 更合理的估算：中文2token/字，英文1token/4字符
        chinese_tokens = chinese_count * 2
        english_tokens = english_count / 4
        
        return int(chinese_tokens + english_tokens)
    
    def get_total_tokens(self):
        """计算当前对话历史的总token数"""
        total = 0
        for msg in self.history:
            total += self.estimate_tokens(msg["content"])
        return total
    
    def get_history_rounds(self):
        """获取当前对话轮数（每轮=用户消息+助手回复）"""
        user_messages = sum(1 for msg in self.history if msg["role"] == "user")
        return user_messages
    
    def needs_compression(self):
        """检查是否需要压缩历史"""
        # 检查对话轮数
        if self.get_history_rounds() > self.max_history_rounds:
            return True
        
        # 检查token数量
        if self.get_total_tokens() > self.max_context_tokens:
            return True
        
        return False
    
    def summarize_history(self, history_part):
        """调用LLM总结历史对话"""
        print("🔍 检测到上下文过长，正在压缩历史...")
        
        # 准备总结提示词
        summary_prompt = f"""请用简洁的语言总结以下对话内容，保留重要信息、决定、和关键细节：

{json.dumps(history_part, ensure_ascii=False, indent=2)}

总结要求：
1. 用第三人称总结
2. 保留用户的主要需求、问题、偏好
3. 保留AI的重要建议、答案、结论
4. 尽量简洁，不超过200字
5. 用中文输出

对话总结："""
        
        # 构建消息
        messages = [
            {
                "role": "system", 
                "content": "你是一个高效的对话总结助手，擅长提取对话核心内容。"
            },
            {
                "role": "user", 
                "content": summary_prompt
            }
        ]
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,  # 低温度确保准确性
            "max_tokens": 300
        }
        
        try:
            result = self.make_request(
                f"{self.base_url}/chat/completions",
                data
            )
            
            if "choices" in result and result["choices"]:
                summary = result["choices"][0]["message"]["content"].strip()
                print(f"✅ 历史已压缩: {summary[:100]}...")
                return summary
            else:
                return "无法生成总结"
                
        except Exception as e:
            print(f"⚠️ 总结生成失败: {e}")
            return "历史压缩失败"
    
    def compress_history(self):
        """压缩历史记录"""
        if len(self.history) < 4:  # 至少2轮对话
            return
        
        # 计算要压缩的部分（前70%）
        compress_index = int(len(self.history) * self.summary_threshold)
        
        # 确保压缩偶数条消息（用户+助手配对）
        if compress_index % 2 != 0:
            compress_index -= 1
        
        if compress_index <= 0:
            return
        
        # 分离要压缩的部分和保留的部分
        to_compress = self.history[:compress_index]
        to_keep = self.history[compress_index:]
        
        # 生成总结
        summary = self.summarize_history(to_compress)
        
        # 创建压缩后的历史
        compressed_history = []
        
        if summary != "历史压缩失败":
            # 添加总结作为系统消息
            compressed_history.append({
                "role": "system",
                "content": f"之前的对话总结：{summary}\n\n请基于以上总结继续对话。"
            })
        else:
            # 如果总结失败，保留最后2轮对话
            to_keep = self.history[-4:] if len(self.history) >= 4 else self.history
        
        # 添加保留的历史
        compressed_history.extend(to_keep)
        
        # 更新历史
        self.history = compressed_history
        
        # 保存总结记录
        self.summaries.append({
            "timestamp": time.time(),
            "summary": summary,
            "original_rounds": len(to_compress) // 2
        })
        
        tokens_before = sum(self.estimate_tokens(msg["content"]) for msg in to_compress)
        tokens_after = self.estimate_tokens(summary) if summary else 0
        print(f"📉 压缩率: {tokens_before} → {tokens_after} tokens")
        print(f"📊 当前: {self.get_history_rounds()}轮对话, {self.get_total_tokens()}tokens")
    
    def make_request(self, url, data):
        """使用urllib发送HTTP请求"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        req = request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            raise Exception(f"HTTP请求失败: {e}")
    
    def chat(self, message):
        """聊天接口 - 带自动历史压缩"""
        # 添加到历史
        self.history.append({"role": "user", "content": message})
        
        # 检查是否需要压缩
        if self.needs_compression():
            self.compress_history()
        
        # 准备消息 - 包含总结和最近历史
        messages = [
            {"role": "system", "content": "你是一个有帮助的AI助手，请用中文回答。"}
        ]
        
        # 添加所有历史（压缩后的）
        messages.extend(self.history[-6:])  # 最多保留最近6条消息
        
        # 准备请求数据
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            start_time = time.time()
            
            # 发送请求
            result = self.make_request(
                f"{self.base_url}/chat/completions",
                data
            )
            
            if "choices" not in result or len(result["choices"]) == 0:
                reply = "❌ 未收到有效回复"
            else:
                reply = result["choices"][0]["message"]["content"]
            
            elapsed = time.time() - start_time
            
            # 添加到历史
            self.history.append({"role": "assistant", "content": reply})
            
            # 显示统计
            input_tokens = self.estimate_tokens(message)
            output_tokens = self.estimate_tokens(reply)
            
            print(f"📊 统计:")
            print(f"   耗时: {elapsed:.2f}秒")
            print(f"   Token估算: {input_tokens}→{output_tokens}")
            print(f"   历史: {self.get_history_rounds()}轮, {self.get_total_tokens()}tokens")
            print("-" * 40)
            print(f"🤖 AI: {reply}")
            
            return reply
            
        except Exception as e:
            error_msg = f"❌ 错误: {str(e)}"
            print(error_msg)
            return error_msg
    
    def clear_history(self):
        """清空对话历史"""
        self.history = []
        self.summaries = []
        print("🗑️  对话历史和压缩记录已清空")
    
    def show_summary_history(self):
        """显示压缩历史"""
        if not self.summaries:
            print("📋 暂无压缩记录")
            return
        
        print("📋 压缩历史记录:")
        for i, summary_info in enumerate(self.summaries, 1):
            time_str = time.strftime("%H:%M:%S", time.localtime(summary_info["timestamp"]))
            summary = summary_info["summary"][:80] + "..." if len(summary_info["summary"]) > 80 else summary_info["summary"]
            print(f"  {i}. [{time_str}] 压缩了{summary_info['original_rounds']}轮对话")
            print(f"     摘要: {summary}")

def main():
    """主程序"""
    # 创建智能体
    agent = SimpleAgent()
    
    # 测试连接
    print("\n🔍 测试连接中...")
    try:
        import urllib.request
        req = urllib.request.Request(f"{agent.base_url}/models")
        req.add_header("Authorization", f"Bearer {agent.api_key}")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                print("✅ 连接成功!")
    except:
        print("⚠️  无法连接到LLM服务")
        print("   请确保LM Studio正在运行")
    
    print("\n💡 命令:")
    print("   - 输入 'clear' 清空历史")
    print("   - 输入 'summary' 查看压缩记录")
    print("   - 输入 'stats' 查看当前统计")
    print("   - 输入 'compress' 手动触发压缩")
    print("   - 输入 'quit' 或 'exit' 退出")
    print("=" * 50)
    
    # 聊天循环
    while True:
        try:
            # 获取输入
            user_input = input("\n👤 你: ").strip()
            
            if not user_input:
                continue
            
            # 特殊命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 再见!")
                break
            
            if user_input.lower() in ['clear', '清空']:
                agent.clear_history()
                continue
                
            if user_input.lower() in ['summary', '摘要', '压缩记录']:
                agent.show_summary_history()
                continue
                
            if user_input.lower() in ['stats', '统计', '状态']:
                print(f"📊 当前状态:")
                print(f"   对话轮数: {agent.get_history_rounds()}轮")
                print(f"   Token总数: {agent.get_total_tokens()}")
                print(f"   是否需要压缩: {'是' if agent.needs_compression() else '否'}")
                continue
                
            if user_input.lower() in ['compress', '压缩', '手动压缩']:
                agent.compress_history()
                continue
            
            # 处理消息
            agent.chat(user_input)
            
        except KeyboardInterrupt:
            print("\n👋 程序被用户中断")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")

if __name__ == "__main__":'42'
main()