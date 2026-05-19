# test_model.py
import urllib.request
import json



url = "http://localhost:1234/v1/models" 
try:
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer lm-studio")
    
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode())
        print("✅ 可用的模型：")
        for model in data.get("data", []):

            print(f"  - {model.get('id')}")
            
        if data.get("data"):
            print(f"\n💡 建议在.env文件中设置：")
            print(f"   LLM_MODEL={data['data'][0].get('id')}")
except Exception as e:
    print(f"❌ 错误：{e}")